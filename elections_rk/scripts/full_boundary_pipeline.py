"""
ПОЛНЫЙ PIPELINE: DOCX → GeoJSON
================================
Объединяет все этапы (A1-A5) в один скрипт.

Использование:
    python scripts/full_boundary_pipeline.py [--full]

Опции:
    --full    Полный режим (все участки, все дома)
    (без)     Тестовый режим (5 участков, 10 домов)
"""

import sys
import json
from pathlib import Path

# Импорты из других скриптов
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scan_boundaries_docx import scan_all_docx
from parse_boundaries import parse_file, dataclass_to_dict, EXTRACTED_DIR, DEFAULT_REGION, DEFAULT_CITY
from geocode_boundaries import GeocodingCache, GeocodingService, geocode_precincts, CACHE_DB
from build_polygons import build_all_polygons
from generate_geojson import generate_geojson, load_precinct_metadata

# Пути
PARSED_DIR = PROJECT_ROOT / "data" / "boundaries" / "parsed"
GEOCODED_DIR = PROJECT_ROOT / "data" / "boundaries" / "geocoded"
POLYGONS_DIR = PROJECT_ROOT / "data" / "boundaries" / "polygons"
OUTPUT_DIR = PROJECT_ROOT / "data" / "boundaries"


def run_full_pipeline(full_mode: bool = False):
    """
    Запускает полный pipeline DOCX → GeoJSON.
    """
    print("=" * 70)
    print("🚀 ПОЛНЫЙ PIPELINE: DOCX → GeoJSON")
    print("=" * 70)
    
    if full_mode:
        print("⚠️  ПОЛНЫЙ РЕЖИМ: все участки, все дома")
        print("   ⏱️  Это займёт несколько часов (геокодинг ~70K адресов)")
        max_precincts = None
        max_houses = None
    else:
        print("🧪 ТЕСТОВЫЙ РЕЖИМ: 5 участков, 10 домов")
        max_precincts = 5
        max_houses = 10
    
    print()
    
    # ═══════════════════════════════════════════════════════════════════
    # ЭТАП A1: DOCX → ТЕКСТ
    # ═══════════════════════════════════════════════════════════════════
    print("─" * 70)
    print("📄 ЭТАП A1: Извлечение текста из DOCX")
    print("─" * 70)
    
    results = scan_all_docx()
    total_precincts = sum(r.get("precincts", 0) for r in results if "precincts" in r)
    print(f"   ✅ Извлечено {total_precincts} участков из {len(results)} файлов")
    
    # ═══════════════════════════════════════════════════════════════════
    # ЭТАП A2: ТЕКСТ → СТРУКТУРА
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("🔧 ЭТАП A2: Парсинг структуры участков")
    print("─" * 70)
    
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    
    txt_files = sorted(EXTRACTED_DIR.glob("*.txt"), key=lambda p: p.stat().st_size, reverse=True)
    all_precincts = []
    
    for txt_file in txt_files:
        precincts = parse_file(txt_file, DEFAULT_REGION, DEFAULT_CITY)
        if precincts:
            all_precincts.extend(precincts)
    
    # Сохраняем
    precincts_file = PARSED_DIR / "precincts.json"
    with open(precincts_file, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {"total_precincts": len(all_precincts)},
            "precincts": [dataclass_to_dict(p) for p in all_precincts]
        }, f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ Распарсено {len(all_precincts)} участков")
    
    # ═══════════════════════════════════════════════════════════════════
    # ЭТАП A3: ГЕОКОДИНГ
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("🌍 ЭТАП A3: Геокодинг адресов")
    print("─" * 70)
    
    GEOCODED_DIR.mkdir(parents=True, exist_ok=True)
    
    cache = GeocodingCache(CACHE_DB)
    service = GeocodingService(cache)
    
    print(f"   💾 Кеш: {cache.stats()['cached_addresses']} адресов")
    
    # Конвертируем dataclass → dict для geocode_precincts
    precincts_dict = [dataclass_to_dict(p) for p in all_precincts]
    
    geocoded_results = geocode_precincts(
        service,
        precincts_dict,
        max_precincts=max_precincts,
        max_houses_per_precinct=max_houses
    )
    
    # Сохраняем
    geocoded_file = GEOCODED_DIR / "coordinates.json"
    with open(geocoded_file, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "total_precincts": len(geocoded_results),
                "test_mode": not full_mode,
                "stats": service.stats
            },
            "precincts": geocoded_results
        }, f, ensure_ascii=False, indent=2)
    
    total_houses = sum(len(p["houses"]) for p in geocoded_results.values())
    print(f"   ✅ Геокодировано {len(geocoded_results)} участков, {total_houses} домов")
    
    # ═══════════════════════════════════════════════════════════════════
    # ЭТАП A4: ПОСТРОЕНИЕ ПОЛИГОНОВ
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("🔷 ЭТАП A4: Построение полигонов")
    print("─" * 70)
    
    POLYGONS_DIR.mkdir(parents=True, exist_ok=True)
    
    polygons, stats = build_all_polygons({
        "precincts": geocoded_results
    })
    
    # Сохраняем
    polygons_file = POLYGONS_DIR / "precincts_polygons.json"
    with open(polygons_file, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {"total_polygons": len(polygons), "stats": stats},
            "precincts": polygons
        }, f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ Построено {stats['with_polygon']} полигонов")
    
    # ═══════════════════════════════════════════════════════════════════
    # ЭТАП A5: ГЕНЕРАЦИЯ GeoJSON
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "─" * 70)
    print("📍 ЭТАП A5: Генерация GeoJSON")
    print("─" * 70)
    
    metadata = load_precinct_metadata()
    geojson = generate_geojson({"precincts": polygons}, metadata)
    
    # Сохраняем
    output_file = OUTPUT_DIR / "ust_kamenogorsk_precincts.geojson"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ GeoJSON: {len(geojson['features'])} features")
    print(f"   💾 Файл: {output_file}")
    print(f"   📦 Размер: {output_file.stat().st_size:,} байт")
    
    # ═══════════════════════════════════════════════════════════════════
    # ИТОГОВАЯ СТАТИСТИКА
    # ═══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("📊 ИТОГОВАЯ СТАТИСТИКА:")
    print("=" * 70)
    print(f"   📄 Файлов DOCX обработано: {len(results)}")
    print(f"   🏛️  Участков в DOCX: {total_precincts}")
    print(f"   🔧 Участков распарсено: {len(all_precincts)}")
    print(f"   🌍 Участков геокодировано: {len(geocoded_results)}")
    print(f"   🏠 Домов геокодировано: {total_houses}")
    print(f"   🔷 Полигонов построено: {stats['with_polygon']}")
    print(f"   📍 Features в GeoJSON: {len(geojson['features'])}")
    print()
    print(f"   💾 GeoJSON готов: {output_file}")
    print("=" * 70)
    
    return 0


def main():
    full_mode = "--full" in sys.argv
    return run_full_pipeline(full_mode)


if __name__ == "__main__":
    raise SystemExit(main())
