import pytest

from app.rag import metadata
from app.rag.metadata import build_entry, detect_arxiv_id, detect_doi, fetch_citation


def test_detect_arxiv_id_prefers_filename() -> None:
    assert detect_arxiv_id("2010.11929v2.pdf", "unrelated text") == "2010.11929"


def test_detect_arxiv_id_from_text() -> None:
    assert detect_arxiv_id("paper.pdf", "Published as arXiv:1706.03762 at NeurIPS") == "1706.03762"


def test_detect_arxiv_id_none() -> None:
    assert detect_arxiv_id("notes.pdf", "no identifiers in here") is None


def test_detect_doi_strips_trailing_punctuation() -> None:
    assert detect_doi("see https://doi.org/10.1109/CVPR.2016.90.") == "10.1109/CVPR.2016.90"


def test_build_entry_key_and_fields() -> None:
    key, entry = build_entry(
        {
            "title": "Attention is All You Need",
            "authors": [("Vaswani", "Ashish"), ("Shazeer", "Noam")],
            "year": "2017",
            "venue": "arXiv preprint arXiv:1706.03762",
            "entry_type": "article",
            "doi": None,
        }
    )
    assert key == "vaswani2017attention"
    assert entry.startswith("@article{vaswani2017attention,")
    assert "author={Vaswani, Ashish and Shazeer, Noam}" in entry
    assert "year={2017}" in entry
    assert "journal={arXiv preprint arXiv:1706.03762}" in entry
    assert "doi=" not in entry  # None fields are omitted


def test_build_entry_inproceedings_uses_booktitle() -> None:
    _, entry = build_entry(
        {
            "title": "Deep Residual Learning for Image Recognition",
            "authors": [("He", "Kaiming")],
            "year": "2016",
            "venue": "CVPR",
            "entry_type": "inproceedings",
            "doi": "10.1109/CVPR.2016.90",
        }
    )
    assert "booktitle={CVPR}" in entry
    assert "journal=" not in entry
    assert "doi={10.1109/CVPR.2016.90}" in entry


async def test_fetch_citation_falls_back_to_crossref(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_arxiv(arxiv_id: str, timeout: float) -> None:
        return None

    seen: dict = {}

    async def fake_crossref(doi: str, timeout: float) -> dict:
        seen["doi"] = doi
        return {
            "title": "Some Paper",
            "authors": [("Doe", "Jane")],
            "year": "2020",
            "venue": None,
            "entry_type": "article",
            "doi": doi,
        }

    monkeypatch.setattr(metadata, "_fetch_arxiv", no_arxiv)
    monkeypatch.setattr(metadata, "_fetch_crossref", fake_crossref)

    result = await fetch_citation("paper.pdf", "available at doi 10.1234/abc.def now")
    assert result is not None
    key, entry = result
    assert seen["doi"] == "10.1234/abc.def"
    assert key == "doe2020some"
    assert entry.startswith("@article{doe2020some,")


async def test_fetch_citation_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(arxiv_id: str, timeout: float) -> dict:
        raise RuntimeError("network down")

    monkeypatch.setattr(metadata, "_fetch_arxiv", boom)
    assert await fetch_citation("2010.11929.pdf", "") is None
