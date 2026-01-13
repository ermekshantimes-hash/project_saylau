"""
A1: DOCX → ТЕКСТ
================
Сканирует все DOCX файлы из data/boundaries/ и извлекает чистый текст.

Ключевые решения (зафиксировано):
- Участок начинается с "Избирательный участок № X"
- Участок заканчивается перед "Избирательный участок № X+1"
- Центр участка (школа) — обязательно сохраняем

Выход: data/boundaries/extracted/*.txt
"""

import os
import sys
from pathlib import Path
from docx import Document

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
BOUNDARIES_DIR = PROJECT_ROOT / "data" / "boundaries"
OUTPUT_DIR = BOUNDARIES_DIR / "extracted"


def extract_text_from_docx(docx_path: Path) -> str:
    """
    Извлекает весь текст из DOCX файла.
    Каждый параграф — отдельная строка.
    Использует python-docx для корректной работы с форматированием.
    """
    doc = Document(docx_path)
    paragraphs = []
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:  # Пропускаем пустые
            paragraphs.append(text)
    
    return "\n".join(paragraphs)


def scan_all_docx():
    """
    Сканирует все DOCX в data/boundaries/ и сохраняет текст.
    Возвращает список результатов обработки.
    """
    # Создаём папку для выходных файлов
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Находим все DOCX
    docx_files = sorted(BOUNDARIES_DIR.glob("*.docx"))
    
    if not docx_files:
        print(f"❌ DOCX файлы не найдены в {BOUNDARIES_DIR}")
        return []
    
    print(f"📂 Найдено {len(docx_files)} файл(ов)")
    print("=" * 60)
    
    results = []
    
    for docx_path in docx_files:
        print(f"\n📄 Обработка: {docx_path.name}")
        
        try:
            # Извлекаем текст
            text = extract_text_from_docx(docx_path)
            
            # Сохраняем
            output_name = docx_path.stem + ".txt"
            output_path = OUTPUT_DIR / output_name
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            
            # Статистика
            lines = text.split("\n")
            precincts = [l for l in lines if "Избирательный участок №" in l]
            centers = [l for l in lines if any(kw in l.lower() for kw in ["школа", "гимназия", "лицей", "колледж", "университет", "детский сад"])]
            boundaries = [l for l in lines if "В границах" in l]
            gardens = [l for l in lines if "адоводчес" in l.lower() or "СТ " in l or "СНТ " in l]
            
            print(f"   ✅ Строк: {len(lines)}")
            print(f"   📍 Участков: {len(precincts)}")
            print(f"   🏫 Центров (школы и т.п.): {len(centers)}")
            print(f"   📐 Блоков границ: {len(boundaries)}")
            print(f"   🌳 Садоводств: {len(gardens)}")
            print(f"   💾 → {output_path.name}")
            
            results.append({
                "source": docx_path.name,
                "output": output_name,
                "lines": len(lines),
                "precincts": len(precincts),
                "centers": len(centers),
                "boundaries": len(boundaries),
                "gardens": len(gardens)
            })
            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            results.append({
                "source": docx_path.name,
                "error": str(e)
            })
    
    return results


def main():
    print("=" * 60)
    print("🔍 A1: СКАНИРОВАНИЕ DOCX → ТЕКСТ")
    print("=" * 60)
    
    results = scan_all_docx()
    
    if not results:
        return 1
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("📊 ИТОГО:")
    print("=" * 60)
    
    total_lines = 0
    total_precincts = 0
    total_gardens = 0
    errors = 0
    
    for r in results:
        if "error" in r:
            errors += 1
        else:
            total_lines += r["lines"]
            total_precincts += r["precincts"]
            total_gardens += r.get("gardens", 0)
    
    print(f"   Файлов обработано: {len(results)}")
    print(f"   Строк извлечено: {total_lines:,}")
    print(f"   Участков найдено: {total_precincts:,}")
    print(f"   Садоводств: {total_gardens}")
    print(f"   Ошибок: {errors}")
    print(f"\n   📁 Результат: {OUTPUT_DIR}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
