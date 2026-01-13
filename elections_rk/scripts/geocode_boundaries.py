"""
A3: ГЕОКОДИНГ С КЕШЕМ
=====================
Геокодирует адреса через OSM Nominatim с кешем и throttling.

Архитектурные решения:
- Формат адреса: "Казахстан, <Область>, <Город>, <Улица>, <Дом>"
- Кеш: SQLite для персистентности
- Throttling: 1 запрос/сек (Nominatim policy)
- Fallback: центр участка (школа) если дом не найден
- Садоводства: геокодим как целое (без домов)

Выход: data/boundaries/geocoded/coordinates.json + cache.sqlite
"""

import json
import sqlite3
import time
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
PARSED_DIR = PROJECT_ROOT / "data" / "boundaries" / "parsed"
OUTPUT_DIR = PROJECT_ROOT / "data" / "boundaries" / "geocoded"
CACHE_DB = OUTPUT_DIR / "geocode_cache.sqlite"

# Настройки геокодинга
USER_AGENT = "elections_rk_boundary_builder/1.0"
TIMEOUT = 10
THROTTLE_DELAY = 1.1  # секунды между запросами (Nominatim policy: 1 req/sec)
MAX_RETRIES = 3

# Алиасы городов для Nominatim (OSM часто хранит официальные/казахские названия)
CITY_QUERY_ALIASES = {
    "Усть-Каменогорск": "Өскемен",
    "Усть-Каменогорска": "Өскемен",
    "Нур-Султан": "Астана",
    "Нур-Султана": "Астана",
}


def normalize_city_for_query(city: str) -> str:
    city = (city or "").strip()
    return CITY_QUERY_ALIASES.get(city, city)


@dataclass
class GeoPoint:
    """Координаты точки"""
    lat: float
    lon: float
    address_query: str
    source: str  # "nominatim", "cache", "fallback"


class GeocodingCache:
    """SQLite кеш для геокодированных адресов"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    address_query TEXT PRIMARY KEY,
                    lat REAL,
                    lon REAL,
                    raw_response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_address 
                ON geocode_cache(address_query)
            """)
    
    def get(self, address: str) -> Optional[Tuple[float, float]]:
        """Получить координаты из кеша"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT lat, lon FROM geocode_cache WHERE address_query = ?",
                (address,)
            ).fetchone()
            if row:
                return (row[0], row[1])
        return None
    
    def put(self, address: str, lat: float, lon: float, raw_response: str = ""):
        """Сохранить координаты в кеш"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO geocode_cache 
                (address_query, lat, lon, raw_response) VALUES (?, ?, ?, ?)
            """, (address, lat, lon, raw_response))
    
    def stats(self) -> dict:
        """Статистика кеша"""
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM geocode_cache").fetchone()[0]
        return {"cached_addresses": count}


class GeocodingService:
    """Сервис геокодинга с кешем и throttling"""
    
    def __init__(self, cache: GeocodingCache):
        self.cache = cache
        self.geolocator = Nominatim(user_agent=USER_AGENT, timeout=TIMEOUT)
        self.last_request_time = 0
        self.stats = {
            "cache_hits": 0,
            "nominatim_requests": 0,
            "nominatim_success": 0,
            "nominatim_failed": 0,
            "fallbacks": 0
        }
    
    def _throttle(self):
        """Соблюдаем Nominatim rate limit"""
        elapsed = time.time() - self.last_request_time
        if elapsed < THROTTLE_DELAY:
            time.sleep(THROTTLE_DELAY - elapsed)
        self.last_request_time = time.time()
    
    def _geocode_nominatim(self, query: str) -> Optional[Tuple[float, float]]:
        """Запрос к Nominatim"""
        self._throttle()
        self.stats["nominatim_requests"] += 1
        
        for attempt in range(MAX_RETRIES):
            try:
                location = self.geolocator.geocode(query)
                if location:
                    self.stats["nominatim_success"] += 1
                    return (location.latitude, location.longitude)
                return None
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    self.stats["nominatim_failed"] += 1
                    return None
        return None
    
    def geocode(self, query: str) -> Optional[GeoPoint]:
        """
        Геокодирует адрес. Сначала проверяет кеш.
        """
        # Проверяем кеш
        cached = self.cache.get(query)
        if cached:
            self.stats["cache_hits"] += 1
            return GeoPoint(
                lat=cached[0],
                lon=cached[1],
                address_query=query,
                source="cache"
            )
        
        # Запрос к Nominatim
        coords = self._geocode_nominatim(query)
        if coords:
            self.cache.put(query, coords[0], coords[1])
            return GeoPoint(
                lat=coords[0],
                lon=coords[1],
                address_query=query,
                source="nominatim"
            )
        
        return None
    
    def geocode_with_fallback(
        self, 
        primary_query: str, 
        fallback_query: Optional[str] = None
    ) -> Optional[GeoPoint]:
        """
        Геокодирует с fallback на альтернативный запрос.
        """
        result = self.geocode(primary_query)
        if result:
            return result
        
        if fallback_query:
            self.stats["fallbacks"] += 1
            result = self.geocode(fallback_query)
            if result:
                result.source = "fallback"
                return result
        
        return None


def build_address_query(
    region: str,
    city: str,
    street_type: str,
    street_name: str,
    house: Optional[str] = None
) -> str:
    """
    Формирует адрес для геокодинга.
    Формат: "Казахстан, <Область>, <Город>, <Улица>, <Дом>"
    """
    # Нормализация типа улицы
    street_type_map = {
        "улице": "улица",
        "улицы": "улица",
        "проспекту": "проспект",
        "проспекта": "проспект",
        "переулку": "переулок",
        "переулка": "переулок",
        "шоссе": "шоссе",
        "бульвару": "бульвар",
        "набережной": "набережная",
        "микрорайону": "микрорайон",
        "разрезу": ""  # Для разрезов не добавляем тип
    }
    
    normalized_type = street_type_map.get(street_type.lower(), street_type)
    
    # Собираем адрес (регион часто в русской форме, что снижает hit-rate в OSM)
    city_q = normalize_city_for_query(city)
    parts = ["Казахстан", city_q]
    
    if normalized_type:
        parts.append(f"{normalized_type} {street_name}")
    else:
        parts.append(street_name)
    
    if house:
        parts.append(house)
    
    return ", ".join(parts)


def build_center_query(region: str, city: str, center_address: str) -> str:
    """
    Формирует запрос для центра участка (школы).
    """
    city_q = normalize_city_for_query(city)
    if not center_address:
        return f"Казахстан, {city_q}"
    
    # Парсим адрес центра: "Проспект имени Каныша Сатпаева, 26/1"
    parts = center_address.split(",")
    if len(parts) >= 2:
        street = parts[0].strip()
        house = parts[1].strip()
        return f"Казахстан, {city_q}, {street}, {house}"
    else:
        return f"Казахстан, {city_q}, {center_address}"


def geocode_precincts(
    service: GeocodingService,
    precincts: list[dict],
    max_precincts: Optional[int] = None,
    max_houses_per_precinct: Optional[int] = None
) -> dict:
    """
    Геокодирует участки.
    Возвращает структуру с координатами.
    """
    results = {}
    
    precincts_to_process = precincts[:max_precincts] if max_precincts else precincts
    
    for i, precinct in enumerate(precincts_to_process):
        precinct_id = precinct["precinct_id"]
        region = precinct["region"]
        city = precinct["city"]
        city_q = normalize_city_for_query(city)
        precinct_key = precinct.get("precinct_key") or f"{region}|{city}|{int(precinct_id)}"
        
        print(
            f"\r   Участок {i+1}/{len(precincts_to_process)}: {city} №{precinct_id}",
            end="",
            flush=True,
        )
        
        precinct_result = {
            "precinct_key": precinct_key,
            "precinct_id": precinct_id,
            "region": region,
            "city": city,
            "center": None,
            "houses": [],
            "gardens": []
        }
        
        # 1. Геокодим центр участка (школу) — ОБЯЗАТЕЛЬНО
        center_query = build_center_query(region, city, precinct.get("center_address", ""))
        center_point = service.geocode(center_query)
        if center_point:
            precinct_result["center"] = {
                "lat": center_point.lat,
                "lon": center_point.lon,
                "query": center_query,
                "source": center_point.source
            }
        
        # 2. Геокодим дома по улицам
        street_blocks = precinct.get("street_blocks", [])
        for block in street_blocks:
            street_type = block.get("street_type", "")
            street_name = block.get("street_name", "")
            houses = block.get("houses", [])
            
            # Ограничиваем количество домов для тестирования
            houses_to_process = houses[:max_houses_per_precinct] if max_houses_per_precinct else houses
            
            for house in houses_to_process:
                query = build_address_query(region, city, street_type, street_name, house)
                fallback = build_address_query(region, city, street_type, street_name)
                
                point = service.geocode_with_fallback(query, fallback)
                if point:
                    precinct_result["houses"].append({
                        "lat": point.lat,
                        "lon": point.lon,
                        "street": f"{street_type} {street_name}",
                        "house": house,
                        "source": point.source
                    })
        
        # 3. Геокодим садоводства (как одну точку)
        for garden in precinct.get("gardens", []):
            query = f"Казахстан, {city_q}, СТ {garden}"
            point = service.geocode(query)
            if point:
                precinct_result["gardens"].append({
                    "lat": point.lat,
                    "lon": point.lon,
                    "name": garden,
                    "source": point.source
                })
        
        results[precinct_key] = precinct_result
    
    print()  # Новая строка после progress
    return results


def main():
    print("=" * 60)
    print("🌍 A3: ГЕОКОДИНГ С КЕШЕМ")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Загружаем распарсенные участки
    precincts_file = PARSED_DIR / "precincts.json"
    if not precincts_file.exists():
        print(f"❌ Файл не найден: {precincts_file}")
        print("   Сначала запустите: python scripts/parse_boundaries.py")
        return 1
    
    with open(precincts_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    precincts = data.get("precincts", [])
    print(f"📄 Загружено участков: {len(precincts)}")
    
    # Инициализируем кеш и сервис
    cache = GeocodingCache(CACHE_DB)
    service = GeocodingService(cache)
    
    print(f"💾 Кеш: {cache.stats()['cached_addresses']} адресов")
    
    # ТЕСТОВЫЙ РЕЖИМ: ограничиваем для проверки
    # Для полного геокодинга установите None
    TEST_MODE = True
    if TEST_MODE:
        max_precincts = 5
        max_houses = 10
        print(f"\n⚠️  ТЕСТОВЫЙ РЕЖИМ: {max_precincts} участков, {max_houses} домов/участок")
    else:
        max_precincts = None
        max_houses = None
        print(f"\n🚀 ПОЛНЫЙ РЕЖИМ: все участки")
    
    print("\n🔄 Геокодинг...")
    
    results = geocode_precincts(
        service,
        precincts,
        max_precincts=max_precincts,
        max_houses_per_precinct=max_houses
    )
    
    # Сохраняем результат
    output_path = OUTPUT_DIR / "coordinates.json"
    output_data = {
        "metadata": {
            "total_precincts": len(results),
            "test_mode": TEST_MODE,
            "stats": service.stats,
            "cache_stats": cache.stats()
        },
        "precincts": results
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    # Статистика
    print("\n" + "=" * 60)
    print("📊 СТАТИСТИКА:")
    print("=" * 60)
    
    total_centers = sum(1 for p in results.values() if p["center"])
    total_houses = sum(len(p["houses"]) for p in results.values())
    total_gardens = sum(len(p["gardens"]) for p in results.values())
    
    print(f"   Участков обработано: {len(results)}")
    print(f"   Центров найдено: {total_centers}")
    print(f"   Домов геокодировано: {total_houses}")
    print(f"   Садоводств: {total_gardens}")
    print()
    print(f"   Cache hits: {service.stats['cache_hits']}")
    print(f"   Nominatim запросов: {service.stats['nominatim_requests']}")
    print(f"   Успешных: {service.stats['nominatim_success']}")
    print(f"   Неудачных: {service.stats['nominatim_failed']}")
    print(f"   Fallback: {service.stats['fallbacks']}")
    print(f"\n   💾 Результат: {output_path}")
    
    # Пример
    if results:
        first_key = list(results.keys())[0]
        example = results[first_key]
        print(f"\n📋 Пример участка {first_key}:")
        if example["center"]:
            c = example["center"]
            print(f"   Центр: {c['lat']:.6f}, {c['lon']:.6f}")
        print(f"   Домов: {len(example['houses'])}")
        if example["houses"]:
            h = example["houses"][0]
            print(f"   Первый дом: {h['street']} {h['house']} → {h['lat']:.6f}, {h['lon']:.6f}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
