from app.rag.chunk import chunk_segments
from app.rag.extract import extract_segments, kind_for_ext


def test_kind_for_ext() -> None:
    assert kind_for_ext(".pdf") == "paper"
    assert kind_for_ext(".tex") == "paper"
    assert kind_for_ext(".csv") == "dataset"
    assert kind_for_ext(".json") == "dataset"


def test_extract_tex() -> None:
    segments = extract_segments(b"\\section{Intro}\nhello world", ".tex")
    assert segments and "hello world" in segments[0][0]


def test_extract_csv_includes_columns() -> None:
    segments = extract_segments(b"a,b\n1,2\n3,4", ".csv")
    assert segments and "Columns: a, b" in segments[0][0]


def test_extract_json() -> None:
    segments = extract_segments(b'{"x": 1}', ".json")
    assert segments and '"x"' in segments[0][0]


def test_chunk_segments_carries_loc() -> None:
    text = "sentence number. " * 400
    chunks = chunk_segments([(text, {"page": 1})])
    assert len(chunks) >= 2
    assert all(chunk["loc"] == {"page": 1} for chunk in chunks)
