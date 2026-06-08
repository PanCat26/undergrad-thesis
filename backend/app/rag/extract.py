import csv
import io
import json

import docx
from pypdf import PdfReader

PAPER_EXTS = {".pdf", ".docx", ".tex"}
DATASET_EXTS = {".csv", ".json"}
ALLOWED_EXTS = PAPER_EXTS | DATASET_EXTS

# Datasets are flattened to text for embedding; cap how much to keep it bounded.
_CSV_MAX_ROWS = 200
_JSON_MAX_CHARS = 50_000

# A segment is a piece of text plus location metadata used later for citations.
Segment = tuple[str, dict]


def kind_for_ext(ext: str) -> str:
    return "dataset" if ext.lower() in DATASET_EXTS else "paper"


def _extract_pdf(data: bytes) -> list[Segment]:
    reader = PdfReader(io.BytesIO(data))
    segments: list[Segment] = []
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            segments.append((text, {"page": index + 1}))
    return segments


def _extract_docx(data: bytes) -> list[Segment]:
    document = docx.Document(io.BytesIO(data))
    text = "\n".join(p.text for p in document.paragraphs if p.text.strip())
    return [(text, {})] if text.strip() else []


def _extract_text(data: bytes) -> list[Segment]:
    text = data.decode("utf-8", errors="replace")
    return [(text, {})] if text.strip() else []


def _extract_csv(data: bytes) -> list[Segment]:
    rows = list(csv.reader(io.StringIO(data.decode("utf-8", errors="replace"))))
    if not rows:
        return []
    header = rows[0]
    lines = [f"Columns: {', '.join(header)}"]
    for row in rows[1 : _CSV_MAX_ROWS + 1]:
        lines.append(", ".join(row))
    return [("\n".join(lines), {})]


def _extract_json(data: bytes) -> list[Segment]:
    try:
        parsed = json.loads(data.decode("utf-8", errors="replace"))
        text = json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        text = data.decode("utf-8", errors="replace")
    return [(text[:_JSON_MAX_CHARS], {})] if text.strip() else []


def extract_segments(data: bytes, ext: str) -> list[Segment]:
    ext = ext.lower()
    if ext == ".pdf":
        return _extract_pdf(data)
    if ext == ".docx":
        return _extract_docx(data)
    if ext == ".tex":
        return _extract_text(data)
    if ext == ".csv":
        return _extract_csv(data)
    if ext == ".json":
        return _extract_json(data)
    return []
