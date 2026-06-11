"""Eval tool backends — Evidentia's agent tools, backed by a task's bundled context.

These re-create the exact tools bound in ``backend/app/agent/ask.py`` (``_build_tools``) — same
names, descriptions, and argument shapes — but serve the task's own sources/draft instead of
Qdrant + Postgres. Retrieval is **BM25** over the task's bundled chunks: deterministic, offline,
and identical for every model, so the only variable in the comparison is the model.

Source of truth for the tool surface is ``ask.py``; if a tool changes there, mirror it here. We
reuse ``ask.py``'s own ``_format_chunks`` / ``_register`` and ``RetrievedChunk`` so chunk
formatting and citation registration are byte-for-byte identical to production.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from langchain_core.tools import tool
from rank_bm25 import BM25Okapi

from app.agent.ask import _READ_FILE_CHAR_LIMIT, _format_chunks, _register
from app.rag.retrieve import RetrievedChunk

_TOP_K = 8  # matches settings.rag_top_k default


def _tok(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


@dataclass
class TaskContext:
    """The bundled world a single eval task runs against."""

    sources: list[dict]  # {filename, kind, cite_key?, bibtex?, chunks:[{text, loc}]}
    draft_files: list[dict]  # {path, content}
    # Flattened (chunk, source) candidates for BM25, built in __post_init__.
    _source_chunks: list[tuple[dict, dict]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        for src in self.sources:
            for chunk in src.get("chunks", []):
                self._source_chunks.append((chunk, src))

    def file(self, path: str) -> dict | None:
        return next((f for f in self.draft_files if f["path"] == path), None)


def _bm25_top(query: str, corpus: list[str], k: int) -> list[int]:
    if not corpus:
        return []
    bm25 = BM25Okapi([_tok(t) for t in corpus])
    scores = bm25.get_scores(_tok(query))
    ranked = sorted(range(len(corpus)), key=lambda i: scores[i], reverse=True)
    return ranked[:k]


def build_eval_tools(ctx: TaskContext, registry: list[dict], edits: dict, mode: str) -> list:
    """Return the agent's tools, closed over the task context. Mirrors ask.py._build_tools."""

    @tool
    def search_sources(query: str) -> str:
        """Search the user's uploaded sources (papers and datasets) for passages relevant to the
        query. Returns numbered results that should be cited."""
        corpus = [c["text"] for c, _ in ctx._source_chunks]
        hits = _bm25_top(query, corpus, _TOP_K)
        chunks = [
            RetrievedChunk(
                kind="source",
                text=ctx._source_chunks[i][0]["text"],
                score=1.0,
                loc=ctx._source_chunks[i][0].get("loc", {}),
                filename=ctx._source_chunks[i][1]["filename"],
                source_id=ctx._source_chunks[i][1]["filename"],
            )
            for i in hits
        ]
        return _format_chunks(chunks, registry)

    @tool
    def search_draft(query: str) -> str:
        """Search the user's current LaTeX draft for passages relevant to the query. Returns
        numbered results that should be cited."""
        corpus = [f["content"] for f in ctx.draft_files]
        hits = _bm25_top(query, corpus, _TOP_K)
        chunks = [
            RetrievedChunk(
                kind="draft",
                text=ctx.draft_files[i]["content"],
                score=1.0,
                loc={},
                filename=ctx.draft_files[i]["path"],
                file_id=ctx.draft_files[i]["path"],
            )
            for i in hits
        ]
        return _format_chunks(chunks, registry)

    @tool
    def list_sources() -> str:
        """List all of the user's uploaded sources (filename and type)."""
        if not ctx.sources:
            return "The user has not uploaded any sources yet."
        return "Sources:\n" + "\n".join(f"- {s['filename']} ({s.get('kind', 'paper')})" for s in ctx.sources)

    @tool
    def list_files() -> str:
        """List the files in the user's current LaTeX draft."""
        if not ctx.draft_files:
            return "The draft has no files."
        return "Draft files:\n" + "\n".join(f"- {f['path']}" for f in ctx.draft_files)

    @tool
    def read_file(path: str) -> str:
        """Read the full content of a file in the user's draft by its path (e.g. 'main.tex')."""
        match = ctx.file(path)
        if match is None:
            return (
                f"No draft file named '{path}'. If '{path}' is an uploaded source, use "
                "search_sources to read it — read_file only opens the user's own draft files."
            )
        index = _register(registry, kind="draft", filename=path, loc={}, file_id=path)
        return f"[{index}] {path} (draft):\n{match['content'][:_READ_FILE_CHAR_LIMIT]}"

    @tool
    def get_references() -> str:
        """Return verified BibTeX entries (and their \\cite keys) for the user's paper sources, for
        citing them and for building references.bib. Use the entries and keys VERBATIM — never
        invent bibliographic details. Datasets are not citable references."""
        if not ctx.sources:
            return "The user has not uploaded any sources yet."
        cited = [s for s in ctx.sources if s.get("kind") == "paper" and s.get("bibtex")]
        datasets = [s for s in ctx.sources if s.get("kind") == "dataset"]
        without = [s for s in ctx.sources if s.get("kind") == "paper" and not s.get("bibtex")]
        sections: list[str] = []
        if cited:
            entries = "\n\n".join(s["bibtex"] for s in cited)
            mapping = "\n".join(f"- {s['filename']} -> \\cite{{{s['cite_key']}}}" for s in cited)
            sections.append(
                "Verified references — put these entries in references.bib and cite with the keys "
                f"shown, both verbatim:\n\n{entries}\n\nFilename to citation key:\n{mapping}"
            )
        if datasets:
            sections.append(
                "These are datasets, not papers — do NOT add them to references.bib or \\cite them:\n"
                + "\n".join(f"- {s['filename']}" for s in datasets)
            )
        if without:
            sections.append(
                "These papers have no verified citation metadata — do NOT fabricate a reference:\n"
                + "\n".join(f"- {s['filename']}" for s in without)
            )
        return "\n\n".join(sections)

    tools = [search_sources, search_draft, list_sources, list_files, read_file, get_references]
    if mode != "agentic":
        return tools

    @tool
    def write_file(path: str, content: str) -> str:
        """Propose creating a new draft file, or overwriting an existing one, with the given full
        content. The change is shown to the user for approval before being applied."""
        if path not in edits["original"]:
            existing = ctx.file(path)
            edits["original"][path] = existing["content"] if existing else ""
        edits["working"][path] = content
        return f"Proposed writing {path}. It will be shown to the user for approval."

    @tool
    def edit_file(path: str, old_string: str, new_string: str = "") -> str:
        """Propose replacing an exact text snippet in a draft file. old_string must appear in the
        file; new_string is the replacement (empty deletes the snippet). The change is shown to the
        user for approval before being applied."""
        if path not in edits["original"]:
            existing = ctx.file(path)
            if existing is None:
                return f"No draft file named '{path}'. Use write_file to create it."
            edits["original"][path] = existing["content"]
            edits["working"][path] = existing["content"]
        current = edits["working"].get(path, edits["original"].get(path, ""))
        if not current.strip():
            return f"{path} is empty, so there is nothing to replace — use write_file to create its full content."
        if old_string not in current:
            return (
                f"Could not find that exact snippet in {path}. Read the file again and use an exact "
                "existing snippet, or use write_file to replace the whole file."
            )
        edits["working"][path] = current.replace(old_string, new_string, 1)
        return f"Proposed edit to {path}. It will be shown to the user for approval."

    return [*tools, write_file, edit_file]
