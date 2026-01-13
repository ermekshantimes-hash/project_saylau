"""
A4: ТОЧКИ → ПОЛИГОН
===================
Строит полигоны участков из геокодированных точек.

Алгоритм:
1. Собираем все точки участка (центр + дома + сады)
2. Строим convex hull (выпуклую оболочку)
3. Если точек мало (<3) — делаем buffer вокруг центра
4. Упрощаем полигон для оптимизации

Выход: data/boundaries/polygons/precincts_polygons.json
"""

import json
from pathlib import Path
from typing import Optional
from shapely.geometry import Point, MultiPoint, Polygon, mapping
from shapely.ops import unary_union
from shapely import concave_hull

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
GEOCODED_DIR = PROJECT_ROOT / "data" / "boundaries" / "geocoded"
OUTPUT_DIR = PROJECT_ROOT / "data" / "boundaries" / "polygons"

# Параметры построения полигонов
MIN_POINTS_FOR_HULL = 3
BUFFER_RADIUS_DEGREES = 0.002  # ~200 метров в градусах (для центра участка)
SIMPLIFY_TOLERANCE = 0.0001   # Упрощение полигона


def collect_points(precinct_data: dict) -> list[tuple[float, float]]:
    """
    Собирает все точки участка (центр + дома + сады).
    Возвращает список (lon, lat) — Shapely использует x=lon, y=lat.
    """
    points = []
    
    # Центр
    if precinct_data.get("center"):
        c = precinct_data["center"]
        points.append((c["lon"], c["lat"]))
    
    # Дома
    for house in precinct_data.get("houses", []):
        points.append((house["lon"], house["lat"]))
    
    # Сады
    for garden in precinct_data.get("gardens", []):
        points.append((garden["lon"], garden["lat"]))
    
    # Убираем дубликаты
    return list(set(points))


def build_polygon(points: list[tuple[float, float]], precinct_key: str) -> Optional[dict]:
    """
    Строит полигон из точек.
    
    Алгоритм:
    - Если точек >= 3: convex hull
    - Если точек < 3: buffer вокруг центра
    - Если точек 0: None
    """
    if not points:
        return None
    
    if len(points) == 1:
        # Одна точка — делаем круг
        center = Point(points[0])
        polygon = center.buffer(BUFFER_RADIUS_DEGREES)
        source = "buffer_single"
    
    elif len(points) == 2:
        # Две точки — делаем buffer вокруг линии
        from shapely.geometry import LineString
        line = LineString(points)
        polygon = line.buffer(BUFFER_RADIUS_DEGREES / 2)
        source = "buffer_line"
    
    else:
        # 3+ точки — convex hull
        mp = MultiPoint(points)
        polygon = mp.convex_hull
        
        # Если получилась линия/точка — делаем buffer
        if polygon.geom_type in ("Point", "LineString"):
            polygon = polygon.buffer(BUFFER_RADIUS_DEGREES / 2)
            source = "buffer_degenerate"
        else:
            source = "convex_hull"
    
    # Упрощаем для оптимизации
    polygon = polygon.simplify(SIMPLIFY_TOLERANCE)
    
    # Конвертируем в GeoJSON-совместимый формат
    geom = mapping(polygon)
    
    return {
        "geometry": geom,
        "points_count": len(points),
        "source": source,
        "area_deg2": polygon.area,
        "centroid": {
            "lon": polygon.centroid.x,
            "lat": polygon.centroid.y
        }
    }


def build_all_polygons(geocoded_data: dict) -> dict:
    """
    Строит полигоны для всех участков.
    """
    precincts = geocoded_data.get("precincts", {})
    results = {}
    
    stats = {
        "total": 0,
        "with_polygon": 0,
        "convex_hull": 0,
        "buffer": 0,
        "no_points": 0
    }
    
    for precinct_key, precinct_data in precincts.items():
        stats["total"] += 1
        
        points = collect_points(precinct_data)
        polygon_data = build_polygon(points, str(precinct_key))
        
        if polygon_data:
            stats["with_polygon"] += 1
            if "convex" in polygon_data["source"]:
                stats["convex_hull"] += 1
            else:
                stats["buffer"] += 1
            
            results[str(precinct_key)] = {
                "precinct_key": precinct_data.get("precinct_key", str(precinct_key)),
                "precinct_id": int(precinct_data.get("precinct_id") or 0),
                "region": precinct_data.get("region", ""),
                "city": precinct_data.get("city", ""),
                "polygon": polygon_data["geometry"],
                "centroid": polygon_data["centroid"],
                "points_count": polygon_data["points_count"],
                "source": polygon_data["source"],
                "area_deg2": polygon_data["area_deg2"]
            }
        else:
            stats["no_points"] += 1
    
    return results, stats


def main():
    print("=" * 60)
    print("🔷 A4: ПОСТРОЕНИЕ ПОЛИГОНОВ")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Загружаем геокодированные данные
    geocoded_file = GEOCODED_DIR / "coordinates.json"
    if not geocoded_file.exists():
        print(f"❌ Файл не найден: {geocoded_file}")
        print("   Сначала запустите: python scripts/geocode_boundaries.py")
        return 1
    
    with open(geocoded_file, "r", encoding="utf-8") as f:
        geocoded_data = json.load(f)
    
    metadata = geocoded_data.get("metadata", {})
    print(f"📄 Загружено участков: {metadata.get('total_precincts', 0)}")
    print(f"   Тестовый режим: {metadata.get('test_mode', False)}")
    
    # Строим полигоны
    print("\n🔄 Построение полигонов...")
    
    polygons, stats = build_all_polygons(geocoded_data)
    
    # Сохраняем
    output_path = OUTPUT_DIR / "precincts_polygons.json"
    output_data = {
        "metadata": {
            "total_polygons": len(polygons),
            "stats": stats
        },
        "precincts": polygons
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    # Статистика
    print("\n" + "=" * 60)
    print("📊 СТАТИСТИКА:")
    print("=" * 60)
    print(f"   Всего участков: {stats['total']}")
    print(f"   С полигонами: {stats['with_polygon']}")
    print(f"   Convex hull: {stats['convex_hull']}")
    print(f"   Buffer (мало точек): {stats['buffer']}")
    print(f"   Без точек: {stats['no_points']}")
    print(f"\n   💾 Результат: {output_path}")
    
    # Пример
    if polygons:
        first_key = list(polygons.keys())[0]
        example = polygons[first_key]
        print(f"\n📋 Пример участка {first_key}:")
        print(f"   Тип: {example['source']}")
        print(f"   Точек: {example['points_count']}")
        print(f"   Центроид: {example['centroid']['lat']:.6f}, {example['centroid']['lon']:.6f}")
        print(f"   Тип геометрии: {example['polygon']['type']}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
