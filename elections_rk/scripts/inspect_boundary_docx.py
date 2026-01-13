import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def extract_docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    texts = [t.text for t in root.findall(".//w:t", NS) if t.text]
    return "\n".join(texts)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: inspect_boundary_docx.py <path-to-docx>")
        return 2

    path = sys.argv[1]
    text = extract_docx_text(path)

    print("=== HEAD (1200 chars) ===")
    print(text[:1200])

    pat = re.compile(r"\b\d{1,3}[\.,]\d{3,}\b")
    matches = list(pat.finditer(text))
    print("\n=== decimal-like matches ===")
    print("count", len(matches))
    for m in matches[:30]:
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 30)
        ctx = text[start:end].replace("\n", " ")
        print("-", ctx)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
