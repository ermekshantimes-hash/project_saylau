import json
import math
import re
import sys
import zipfile
from pathlib import Path


def _extract_docx_text(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path, "r") as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")

    # Keep it dependency-free: pull visible text from <w:t> nodes.
    # Add newlines for paragraph-like boundaries.
    xml = xml.replace("</w:p>", "</w:p>\n")
    parts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, flags=re.DOTALL)
    text = "".join(parts)

    # Basic de-escaping for common XML entities.
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )

    # Normalize whitespace but preserve paragraph breaks.
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_precinct_sections(text: str) -> list[dict]:
    # Split by precinct header.
    # Note: docs often contain extra spaces and line breaks.
    pattern = re.compile(r"Избирательный\s+участок\s*№\s*(\d+)", flags=re.IGNORECASE)

    matches = list(pattern.finditer(text))
    if not matches:
        return []

    sections: list[dict] = []
    for i, m in enumerate(matches):
        precinct_number = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        # Try to carve out a short polling-place line (before the boundary description).
        # If it fails, keep the first line(s) anyway.
        boundary_idx = None
        for token in ["В границах", "В  границах", "Вграницах"]:
            idx = block.find(token)
            if idx != -1:
                boundary_idx = idx
                break

        header_part = block if boundary_idx is None else block[:boundary_idx]
        header_part = header_part.strip()

        # Take up to 2 lines (docs may be wrapped in weird ways).
        header_lines = [ln.strip(" .") for ln in header_part.splitlines() if ln.strip()]
        polling_place = " ".join(header_lines[:2]).strip()

        # Full description for popup.
        description = re.sub(r"\s+", " ", block).strip()

        sections.append(
            {
                "precinct_number": precinct_number,
                "polling_place": polling_place,
                "description": description,
            }
        )

    return sections


def _jitter_latlon(base_lat: float, base_lon: float, n: int) -> tuple[float, float]:
    # Deterministic tiny jitter so points don't overlap.
    # ~0.02 degrees is a couple km; keep it smaller.
    angle = (n * 137.508) % 360  # golden angle
    r = 0.002 + (n % 25) * 0.00015
    lat = base_lat + r * math.cos(math.radians(angle))
    lon = base_lon + r * math.sin(math.radians(angle))
    return lat, lon


def convert_docx_to_geojson(*, docx_path: Path, output_path: Path) -> dict:
    text = _extract_docx_text(docx_path)
    sections = _parse_precinct_sections(text)

    # This specific file is about Ust-Kamenogorsk / Oskemen.
    # IMPORTANT: the DOCX has no coordinates; these are demo points near city center.
    base_lat, base_lon = 49.9795, 82.6176

    features: list[dict] = []
    for item in sections:
        precinct_number = int(item["precinct_number"])
        lat, lon = _jitter_latlon(base_lat, base_lon, precinct_number)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "source_file": docx_path.name,
                    "precinct_number": precinct_number,
                    "polling_place": item.get("polling_place") or "",
                    "description": item.get("description") or "",
                    "geometry_note": "DEMO_POINT_ONLY (DOCX contains addresses, no coordinates)",
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            "Usage: python scripts/convert_boundaries_docx_to_geojson.py <input.docx> <output.geojson>",
            file=sys.stderr,
        )
        return 2

    docx_path = Path(argv[1]).resolve()
    output_path = Path(argv[2]).resolve()

    if not docx_path.exists():
        print(f"Input not found: {docx_path}", file=sys.stderr)
        return 2

    geojson = convert_docx_to_geojson(docx_path=docx_path, output_path=output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote: {output_path}")
    print(f"Features: {len(geojson.get('features', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
