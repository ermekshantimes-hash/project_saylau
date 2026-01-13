"""
A5: ГЕНЕРАЦИЯ GeoJSON
=====================
Создаёт финальный GeoJSON файл для Leaflet.

Формат:
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "precinct_id": 15,
        "level": "precinct",
        "center_name": "Школа №24",
        "center_lat": 49.123,
        "center_lon": 82.456
      },
      "geometry": { "type": "Polygon", "coordinates": [...] }
    }
  ]
}

Выход: data/boundaries/ust_kamenogorsk_precincts.geojson
"""

import json
from pathlib import Path

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
POLYGONS_DIR = PROJECT_ROOT / "data" / "boundaries" / "polygons"
PARSED_DIR = PROJECT_ROOT / "data" / "boundaries" / "parsed"
OUTPUT_DIR = PROJECT_ROOT / "data" / "boundaries"


def load_precinct_metadata() -> dict:
    """
    Загружает метаданные участков (названия школ и т.п.)
    """
    precincts_file = PARSED_DIR / "precincts.json"
    if not precincts_file.exists():
        return {}
    
    with open(precincts_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Строим словарь по precinct_key (fallback на precinct_id для старых данных)
    metadata = {}
    for p in data.get("precincts", []):
        key = p.get("precinct_key")
        if not key:
            pid = p.get("precinct_id")
            key = str(pid) if pid is not None else None
        if key:
            metadata[str(key)] = {
                "center_name": p.get("center_name", ""),
                "center_address": p.get("center_address", ""),
                "center_phone": p.get("center_phone", ""),
                "region": p.get("region", ""),
                "city": p.get("city", "")
            }
    
    return metadata


def generate_geojson(polygons_data: dict, metadata: dict) -> dict:
    """
    Генерирует GeoJSON FeatureCollection.
    """
    features = []
    
    precincts = polygons_data.get("precincts", {})
    
    for precinct_key, polygon_data in precincts.items():
        # Получаем метаданные
        meta = metadata.get(str(precinct_key), {})
        precinct_id_value = polygon_data.get("precinct_id")
        if precinct_id_value is None:
            # fallback для старого формата ключей
            try:
                precinct_id_value = int(str(precinct_key))
            except ValueError:
                precinct_id_value = 0
        
        feature = {
            "type": "Feature",
            "properties": {
                "precinct_key": str(precinct_key),
                "precinct_id": int(precinct_id_value),
                "level": "precinct",
                "center_name": meta.get("center_name", ""),
                "center_address": meta.get("center_address", ""),
                "center_phone": meta.get("center_phone", ""),
                "region": meta.get("region", polygon_data.get("region", "")),
                "city": meta.get("city", polygon_data.get("city", "")),
                "center_lat": polygon_data.get("centroid", {}).get("lat"),
                "center_lon": polygon_data.get("centroid", {}).get("lon"),
                "points_count": polygon_data.get("points_count", 0),
                "polygon_source": polygon_data.get("source", "")
            },
            "geometry": polygon_data.get("polygon")
        }
        
        features.append(feature)
    
    # Сортируем стабильно: регион, город, номер участка
    features.sort(
        key=lambda f: (
            f["properties"].get("region", ""),
            f["properties"].get("city", ""),
            f["properties"].get("precinct_id", 0),
            f["properties"].get("precinct_key", ""),
        )
    )
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def main():
    print("=" * 60)
    print("📍 A5: ГЕНЕРАЦИЯ GeoJSON")
    print("=" * 60)
    
    # Загружаем полигоны
    polygons_file = POLYGONS_DIR / "precincts_polygons.json"
    if not polygons_file.exists():
        print(f"❌ Файл не найден: {polygons_file}")
        print("   Сначала запустите: python scripts/build_polygons.py")
        return 1
    
    with open(polygons_file, "r", encoding="utf-8") as f:
        polygons_data = json.load(f)
    
    print(f"📄 Загружено полигонов: {len(polygons_data.get('precincts', {}))}")
    
    # Загружаем метаданные
    metadata = load_precinct_metadata()
    print(f"📋 Метаданные участков: {len(metadata)}")
    
    # Генерируем GeoJSON
    print("\n🔄 Генерация GeoJSON...")
    
    geojson = generate_geojson(polygons_data, metadata)
    
    # Сохраняем
    output_path = OUTPUT_DIR / "ust_kamenogorsk_precincts.geojson"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    
    # Статистика
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТ:")
    print("=" * 60)
    print(f"   Features: {len(geojson['features'])}")
    print(f"   💾 Файл: {output_path}")
    print(f"   Размер: {output_path.stat().st_size:,} байт")
    
    # Пример feature
    if geojson["features"]:
        example = geojson["features"][0]
        props = example["properties"]
        print(f"\n📋 Пример Feature:")
        print(f"   precinct_id: {props['precinct_id']}")
        print(f"   center_name: {props['center_name']}")
        print(f"   center_lat/lon: {props['center_lat']}, {props['center_lon']}")
        print(f"   geometry type: {example['geometry']['type']}")
    
    print(f"\n✅ GeoJSON готов для использования в Leaflet!")
    print(f"   Подключение: L.geoJSON(data).addTo(map)")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
