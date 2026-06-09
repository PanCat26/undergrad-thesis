"""Best-effort citation metadata for uploaded papers.

Given a paper's filename and extracted text, detect an arXiv id or DOI, fetch the
authoritative record from arXiv/Crossref, and build a ready-to-use BibTeX entry. This keeps
generated bibliographies grounded in real metadata instead of the model's memory. Every public
function is best-effort and never raises — a lookup miss simply yields no reference.
"""
import re
from xml.etree import ElementTree

import httpx

from app.core.logging import get_logger

logger = get_logger("app.metadata")

# arXiv ids look like 2010.11929 (optionally with a vN suffix); they are also commonly the filename.
_ARXIV_RE = re.compile(r"arxiv[:\s/]*\s*(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
_ARXIV_BARE_RE = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)")
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE)

_ARXIV_API = "http://export.arxiv.org/api/query"
_CROSSREF_API = "https://api.crossref.org/works/"
_ATOM = "{http://www.w3.org/2005/Atom}"
_USER_AGENT = "thesis-research-tool/1.0 (citation metadata lookup)"

# Skipped when deriving a cite key's title word, so keys read like "vaswani2017attention".
_STOPWORDS = {
    "the", "a", "an", "on", "of", "for", "and", "to", "in", "with", "using",
    "via", "is", "are", "from", "by", "at", "as", "into", "over",
}

# Authoritative metadata, normalized across providers.
#   {"title": str, "authors": [(family, given), ...], "year": str,
#    "venue": str | None, "entry_type": "article" | "inproceedings", "doi": str | None}


def detect_arxiv_id(filename: str, text: str) -> str | None:
    """Find an arXiv id, preferring the filename (uploads are often named by their id)."""
    match = _ARXIV_BARE_RE.search(filename)
    if match:
        return match.group(1)
    match = _ARXIV_RE.search(text)
    return match.group(1) if match else None


def detect_doi(text: str) -> str | None:
    match = _DOI_RE.search(text)
    if not match:
        return None
    # Extraction often glues trailing punctuation onto the DOI; trim the common offenders.
    return match.group(0).rstrip(".,);:").strip()


def _format_author(author: tuple[str, str]) -> str:
    family, given = author
    return f"{family}, {given}".strip().rstrip(",") if given else family


def _cite_key(meta: dict) -> str:
    authors = meta.get("authors") or []
    family = authors[0][0] if authors else (meta.get("title") or "ref").split(" ")[0]
    title_word = ""
    for word in re.findall(r"[A-Za-z]+", meta.get("title") or ""):
        if len(word) > 2 and word.lower() not in _STOPWORDS:
            title_word = word.lower()
            break
    key = re.sub(r"[^a-z0-9]", "", family.lower()) + (meta.get("year") or "") + title_word
    return key or "ref"


def build_entry(meta: dict) -> tuple[str, str]:
    """Render normalized metadata into (cite_key, bibtex_entry)."""
    key = _cite_key(meta)
    authors = " and ".join(_format_author(a) for a in meta.get("authors") or []) or "Unknown"
    fields: list[tuple[str, str | None]] = [
        ("title", meta.get("title")),
        ("author", authors),
    ]
    if meta.get("entry_type") == "inproceedings" and meta.get("venue"):
        fields.append(("booktitle", meta["venue"]))
    elif meta.get("venue"):
        fields.append(("journal", meta["venue"]))
    fields.append(("year", meta.get("year")))
    fields.append(("doi", meta.get("doi")))
    body = ",\n".join(f"  {name}={{{value}}}" for name, value in fields if value)
    return key, f"@{meta.get('entry_type', 'article')}{{{key},\n{body}\n}}"


async def _fetch_arxiv(arxiv_id: str, timeout: float) -> dict | None:
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": _USER_AGENT}) as client:
        resp = await client.get(_ARXIV_API, params={"id_list": arxiv_id, "max_results": 1})
        resp.raise_for_status()
    entry = ElementTree.fromstring(resp.text).find(f"{_ATOM}entry")
    if entry is None:
        return None
    title = re.sub(r"\s+", " ", (entry.findtext(f"{_ATOM}title") or "").strip())
    if not title or title.lower() == "error":  # arXiv returns an "Error" entry for unknown ids
        return None
    published = entry.findtext(f"{_ATOM}published") or ""
    authors = []
    for author in entry.findall(f"{_ATOM}author"):
        name = (author.findtext(f"{_ATOM}name") or "").strip()
        if name:
            parts = name.split()
            authors.append((parts[-1], " ".join(parts[:-1])))
    return {
        "title": title,
        "authors": authors,
        "year": published[:4] if published[:4].isdigit() else "",
        "venue": f"arXiv preprint arXiv:{arxiv_id}",
        "entry_type": "article",
        "doi": None,
    }


async def _fetch_crossref(doi: str, timeout: float) -> dict | None:
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": _USER_AGENT}) as client:
        resp = await client.get(_CROSSREF_API + doi)
        resp.raise_for_status()
    message = resp.json().get("message", {})
    titles = message.get("title") or []
    title = titles[0].strip() if titles else ""
    if not title:
        return None
    authors = [
        (a["family"].strip(), (a.get("given") or "").strip())
        for a in message.get("author") or []
        if a.get("family")
    ]
    year = ""
    for field in ("published-print", "published-online", "issued", "created"):
        parts = (message.get(field) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break
    containers = message.get("container-title") or []
    is_proceedings = message.get("type") == "proceedings-article"
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "venue": containers[0] if containers else None,
        "entry_type": "inproceedings" if is_proceedings else "article",
        "doi": doi,
    }


async def fetch_citation(
    filename: str, text: str, *, timeout: float = 10.0
) -> tuple[str, str] | None:
    """Return (cite_key, bibtex) for a paper, or None if no authoritative record was found.

    Best-effort and exception-safe: network errors, parse failures, and misses all yield None so
    ingestion is never blocked by citation lookup.
    """
    try:
        meta: dict | None = None
        arxiv_id = detect_arxiv_id(filename, text)
        if arxiv_id:
            meta = await _fetch_arxiv(arxiv_id, timeout)
        if meta is None:
            doi = detect_doi(text)
            if doi:
                meta = await _fetch_crossref(doi, timeout)
        if meta is None or not meta.get("title"):
            return None
        return build_entry(meta)
    except Exception:  # noqa: BLE001 — citation lookup must never break ingestion
        logger.warning("citation lookup failed for %s", filename, exc_info=True)
        return None
