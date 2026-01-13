"""
A2: ТЕКСТ → СТРУКТУРА УЧАСТКА
=============================
Парсит извлечённый текст и создаёт структурированные данные по каждому участку.

Архитектурные решения (зафиксировано):
- Участок начинается: "Избирательный участок № X"
- Участок заканчивается: перед "Избирательный участок № X+1"
- Центр участка (школа) — ОБЯЗАТЕЛЬНО сохраняем
- Садоводства — включаем как отдельную сущность (не геокодим дома)
- Формат адреса: "Казахстан, <Область>, <Город>, <Улица>, <Дом>"

Выход: data/boundaries/parsed/precincts.json
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
EXTRACTED_DIR = PROJECT_ROOT / "data" / "boundaries" / "extracted"
OUTPUT_DIR = PROJECT_ROOT / "data" / "boundaries" / "parsed"

# Регулярки
RE_PRECINCT_HEADER = re.compile(
    r"Избирательный\s*участок\s*№\s*(\d+)",
    re.IGNORECASE
)

RE_STREET_BLOCK = re.compile(
    r"(?:№\s*)?([\d\s,/\-а-яёА-ЯЁa-zA-Z]+)\s+по\s+(улице|проспекту|переулку|шоссе|бульвару|набережной|микрорайону|разрезу)\s+([^;№]+?)(?=[;№]|$)",
    re.IGNORECASE
)

RE_BOUNDARIES_MARKER = re.compile(
    r"В\s+границах\s+домов?\s*:?\s*",
    re.IGNORECASE
)

RE_GARDENS = re.compile(
    r"Садоводческ\w+\s+товарищества?\s*:\s*([^\.]+)",
    re.IGNORECASE
)

RE_CENTER_KEYWORDS = [
    "школа", "гимназия", "лицей", "колледж", "университет",
    "детский сад", "ДК", "дом культуры", "клуб", "библиотека",
    "акимат", "КГУ", "ТОО", "центр"
]

# Город по умолчанию (для Усть-Каменогорска)
DEFAULT_REGION = "Восточно-Казахстанская область"
DEFAULT_CITY = "Усть-Каменогорск"


def _clean_location_name(value: str) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    value = re.sub(r"[\.;,\)\]\}\"]+$", "", value).strip()
    return value


def infer_region_city(full_text: str, fallback_region: str, fallback_city: str) -> tuple[str, str]:
    """Пытается определить регион/город из текста.

    В исходных документах часто встречается "... акимата города <Город>".
    Регион/область может встречаться в форме родительного падежа.
    """
    text = full_text or ""

    city = None
    region = None

    # Город: "акимата города <...>" (самый надёжный маркер)
    m = re.search(r"акимат[а-я\s]*города\s+([^\n,;]+)", text, re.IGNORECASE)
    if m:
        city = _clean_location_name(m.group(1))
        # Часто в документах это родительный падеж: "города Усть-Каменогорска"
        if len(city) > 4:
            if city.endswith("а"):
                city = city[:-1]
            elif city.endswith("ы"):
                city = city[:-1] + "а"
            elif city.endswith("и"):
                city = city[:-1] + "а"

    # Альтернативы: "г. <...>" или "город <...>" (менее надёжно)
    if not city:
        m = re.search(r"\bг\.?\s*([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z\-\s]+)", text)
        if m:
            city = _clean_location_name(m.group(1))

    # Регион/область
    m = re.search(r"([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z\-\s]+?\s+област[ьи])", text, re.IGNORECASE)
    if m:
        region_raw = _clean_location_name(m.group(1))
        # Отсекаем ложные срабатывания (обычно регион в тексте пишется с заглавной буквы)
        if not re.search(r"[А-ЯЁ]", region_raw):
            region_raw = ""
        # Нормализация простых окончаний
        region_norm = region_raw
        region_norm = re.sub(r"\bобласти$", "область", region_norm, flags=re.IGNORECASE)
        region_norm = re.sub(r"ской\s+область$", "ская область", region_norm, flags=re.IGNORECASE)
        region_norm = re.sub(r"ой\s+область$", "ая область", region_norm, flags=re.IGNORECASE)
        region = region_norm or None

    return (region or fallback_region), (city or fallback_city)


def make_precinct_key(region: str, city: str, precinct_id: int) -> str:
    region = _clean_location_name(region)
    city = _clean_location_name(city)
    return f"{region}|{city}|{int(precinct_id)}"


@dataclass
class StreetBlock:
    """Блок адресов по одной улице"""
    street_type: str  # улица, проспект, переулок...
    street_name: str
    houses: list[str]  # список номеров домов


@dataclass
class Precinct:
    """Избирательный участок"""
    precinct_key: str
    precinct_id: int
    region: str
    city: str
    center_address: str  # Адрес центра (школа и т.п.)
    center_name: str     # Название центра
    center_phone: Optional[str]
    street_blocks: list[StreetBlock]
    gardens: list[str]   # Садоводческие товарищества
    raw_text: str        # Исходный текст для отладки


def extract_center_info(text: str) -> tuple[str, str, Optional[str]]:
    """
    Извлекает информацию о центре участка (школа и т.п.)
    Возвращает: (адрес, название, телефон)
    """
    lines = text.split("\n")
    center_line = ""
    
    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in RE_CENTER_KEYWORDS):
            center_line = line
            break
    
    if not center_line:
        # Берём первую строку после заголовка
        for line in lines:
            if not RE_PRECINCT_HEADER.search(line) and line.strip():
                center_line = line
                break
    
    # Извлекаем телефон
    phone_match = re.search(r"телефон\s*([\d\-]+)", center_line, re.IGNORECASE)
    phone = phone_match.group(1) if phone_match else None
    
    # Извлекаем адрес (до первой запятой или КГУ/ТОО)
    address = ""
    name = ""
    
    # Паттерн: "Улица X, Y, название учреждения"
    addr_match = re.match(
        r"^([^,]+,\s*[\d/а-яА-Я]+)",
        center_line
    )
    if addr_match:
        address = addr_match.group(1).strip()
    
    # Название — всё между адресом и телефоном
    name_match = re.search(
        r"(?:коммунальное\s+государственное\s+учреждение|КГУ|ТОО|здание)\s*[«\"]?([^»\"]+)[»\"]?",
        center_line,
        re.IGNORECASE
    )
    if name_match:
        name = name_match.group(1).strip()
    
    return address, name, phone


def parse_houses(houses_str: str) -> list[str]:
    """
    Парсит строку с номерами домов.
    Примеры: "1, 2, 3/1, 4а, 5-1, 6/1-1"
    """
    # Убираем "№" и лишние пробелы
    houses_str = re.sub(r"№\s*", "", houses_str)
    
    # Разбиваем по запятым
    parts = [p.strip() for p in houses_str.split(",")]
    
    houses = []
    for part in parts:
        if not part:
            continue
        # Убираем лишние пробелы внутри
        part = re.sub(r"\s+", "", part)
        # Валидация: должен содержать хотя бы одну цифру
        if re.search(r"\d", part):
            houses.append(part)
    
    return houses


def parse_street_blocks(text: str) -> list[StreetBlock]:
    """
    Извлекает блоки адресов из текста участка.
    Формат: "№ 1, 2, 3 по улице Ленина; № 4, 5 по проспекту Мира"
    """
    blocks = []
    
    # Ищем маркер границ
    boundaries_match = RE_BOUNDARIES_MARKER.search(text)
    if not boundaries_match:
        return blocks
    
    # Берём текст после маркера
    text_after = text[boundaries_match.end():]
    
    # Ищем все блоки "номера по улице/проспекту/переулку"
    # Улучшенный паттерн
    pattern = re.compile(
        r"(?:№\s*)?([\d\s,/\-а-яёА-ЯЁa-zA-Z\.]+?)\s+по\s+(улице|проспекту|переулку|шоссе|бульвару|набережной|микрорайону|разрезу)\s+([А-Яа-яЁё\w\s\-\.]+?)(?=;|№|по\s+улице|по\s+проспекту|по\s+переулку|Садоводческ|$)",
        re.IGNORECASE
    )
    
    for match in pattern.finditer(text_after):
        houses_str = match.group(1)
        street_type = match.group(2).lower()
        street_name = match.group(3).strip()
        
        # Убираем trailing punctuation
        street_name = re.sub(r"[,;\.]+$", "", street_name).strip()
        
        houses = parse_houses(houses_str)
        
        if houses and street_name:
            blocks.append(StreetBlock(
                street_type=street_type,
                street_name=street_name,
                houses=houses
            ))
    
    return blocks


def parse_gardens(text: str) -> list[str]:
    """
    Извлекает садоводческие товарищества.
    """
    gardens = []
    
    match = RE_GARDENS.search(text)
    if match:
        gardens_str = match.group(1)
        # Разбиваем по запятым, убираем кавычки
        parts = re.split(r"[,;]", gardens_str)
        for part in parts:
            name = re.sub(r"[«»\"\']", "", part).strip()
            if name:
                gardens.append(name)
    
    return gardens


def split_into_precincts(full_text: str) -> list[tuple[int, str]]:
    """
    Разбивает полный текст на блоки по участкам.
    Возвращает список (номер_участка, текст_участка).
    """
    # Находим все заголовки участков
    matches = list(RE_PRECINCT_HEADER.finditer(full_text))
    
    if not matches:
        return []
    
    precincts = []
    
    for i, match in enumerate(matches):
        precinct_id = int(match.group(1))
        start = match.start()
        
        # Конец — начало следующего участка или конец текста
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(full_text)
        
        text = full_text[start:end].strip()
        precincts.append((precinct_id, text))
    
    return precincts


def parse_precinct(precinct_id: int, text: str, region: str, city: str) -> Precinct:
    """
    Парсит один участок.
    """
    precinct_key = make_precinct_key(region, city, precinct_id)
    center_address, center_name, center_phone = extract_center_info(text)
    street_blocks = parse_street_blocks(text)
    gardens = parse_gardens(text)
    
    return Precinct(
        precinct_key=precinct_key,
        precinct_id=precinct_id,
        region=region,
        city=city,
        center_address=center_address,
        center_name=center_name,
        center_phone=center_phone,
        street_blocks=street_blocks,
        gardens=gardens,
        raw_text=text[:500]  # Первые 500 символов для отладки
    )


def parse_file(file_path: Path, region: str, city: str) -> list[Precinct]:
    """
    Парсит один файл с границами.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # Пытаемся определить регион/город из содержимого файла
    region, city = infer_region_city(full_text, region, city)
    
    raw_precincts = split_into_precincts(full_text)
    
    precincts = []
    for precinct_id, text in raw_precincts:
        precinct = parse_precinct(precinct_id, text, region, city)
        precincts.append(precinct)
    
    return precincts


def dataclass_to_dict(obj):
    """Конвертирует dataclass в dict рекурсивно"""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: dataclass_to_dict(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]
    else:
        return obj


def main():
    print("=" * 60)
    print("🔧 A2: ПАРСИНГ СТРУКТУРЫ УЧАСТКОВ")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Находим главный файл с Усть-Каменогорском (534KB)
    txt_files = sorted(EXTRACTED_DIR.glob("*.txt"), key=lambda p: p.stat().st_size, reverse=True)
    
    if not txt_files:
        print("❌ Текстовые файлы не найдены в", EXTRACTED_DIR)
        return 1
    
    all_precincts = []
    
    for txt_file in txt_files:
        print(f"\n📄 Обработка: {txt_file.name}")

        # Определяем регион/город по содержимому файла (с fallback на defaults)
        region = DEFAULT_REGION
        city = DEFAULT_CITY
        
        precincts = parse_file(txt_file, region, city)
        
        if not precincts:
            print(f"   ⚠️  Участки не найдены")
            continue
        
        # Статистика
        total_houses = sum(
            len(block.houses)
            for p in precincts
            for block in p.street_blocks
        )
        total_streets = sum(len(p.street_blocks) for p in precincts)
        total_gardens = sum(len(p.gardens) for p in precincts)
        
        print(f"   ✅ Участков: {len(precincts)}")
        print(f"   🏠 Блоков улиц: {total_streets}")
        print(f"   🏘️  Домов: {total_houses:,}")
        print(f"   🌳 Садоводств: {total_gardens}")
        
        all_precincts.extend(precincts)
    
    # Сохраняем результат
    output_path = OUTPUT_DIR / "precincts.json"

    regions = sorted({p.region for p in all_precincts})
    cities = sorted({p.city for p in all_precincts})
    
    output_data = {
        "metadata": {
            "total_precincts": len(all_precincts),
            "regions": regions,
            "cities": cities,
            "source_files": [f.name for f in txt_files]
        },
        "precincts": [dataclass_to_dict(p) for p in all_precincts]
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("📊 ИТОГО:")
    print("=" * 60)
    print(f"   Участков: {len(all_precincts)}")
    print(f"   💾 Сохранено: {output_path}")
    
    # Показываем пример
    if all_precincts:
        example = all_precincts[0]
        print(f"\n📋 Пример участка №{example.precinct_id}:")
        print(f"   Центр: {example.center_name}")
        print(f"   Адрес: {example.center_address}")
        print(f"   Блоков улиц: {len(example.street_blocks)}")
        if example.street_blocks:
            sb = example.street_blocks[0]
            print(f"   Первый блок: {sb.street_type} {sb.street_name} — {len(sb.houses)} домов")
        if example.gardens:
            print(f"   Садоводства: {example.gardens[:3]}...")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
