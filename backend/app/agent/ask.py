import asyncio
import difflib
import re
import time
from collections.abc import AsyncIterator, Sequence

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.agent.qa import _format_loc, _strip_inline_refs
from app.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.rag.retrieve import RetrievedChunk, retrieve
from app.services import files as files_service
from app.services import sources as sources_service

logger = get_logger("app.ask")

MAX_ITERATIONS = 10
_READ_FILE_CHAR_LIMIT = 4000
_REQUEST_TIMEOUT = 60  # seconds per OpenAI call
_RUN_TIMEOUT = 150  # seconds for the whole agent run

# Shown back to the model when it calls a tool with invalid arguments, so it can self-correct.
_TOOL_USAGE = {
    "search_sources": "search_sources requires a 'query' string.",
    "search_draft": "search_draft requires a 'query' string.",
    "read_file": "read_file requires a 'path' string.",
    "write_file": "write_file requires 'path' and 'content' (the full new file content).",
    "edit_file": (
        "edit_file requires 'path' and 'old_string' (an exact snippet currently in the file); "
        "'new_string' is the replacement (omit it to delete the snippet)."
    ),
}

ASK_SYSTEM = (
    "You are a research assistant embedded in an academic writing tool. You help the user with "
    "their uploaded sources (papers and datasets) and their current LaTeX draft.\n\n"
    "You can always access the user's sources and draft through your tools. NEVER tell the user "
    "you cannot access their papers, files, or content — use the tools instead.\n\n"
    "Tools:\n"
    "- search_sources and search_draft find relevant passages (they return numbered results). "
    "Use a descriptive query with the key terms/topic of the source (e.g. its title or subject), "
    "not generic words like 'related work'. You may reword once or twice, but do NOT keep repeating "
    "near-identical searches — after a couple of tries, work with what you have.\n"
    "- list_sources and list_files enumerate what the user has.\n"
    "- read_file reads a draft file in full.\n"
    "- get_references returns verified BibTeX entries and \\cite keys for the user's paper sources; "
    "use it whenever you need to cite a source or build references.bib.\n\n"
    "Important: the uploaded sources (papers and datasets) are NOT draft files. Read their content "
    "ONLY through search_sources; read_file and list_files (and, in Agent mode, write_file and "
    "edit_file) operate on the user's own draft files such as main.tex — never on sources.\n\n"
    "Environment: the draft is compiled with Tectonic using the classic BibTeX workflow — cite with "
    "\\cite, and keep a .bib file plus \\bibliographystyle and \\bibliography in the root document. "
    "biblatex/biber are NOT supported. If you use a natbib bibliography style such as plainnat, also "
    "add \\usepackage{natbib} to the preamble and do not combine it with the cite package.\n\n"
    "How to answer:\n"
    "- For greetings or questions about who you are or what you can do, answer directly without "
    "using tools.\n"
    "- For ANY question about the user's papers, sources, datasets, or draft (including broad ones "
    "like 'what do my papers talk about?'), you MUST call the appropriate tool(s) first — start "
    "with list_sources and/or search_sources — and answer using ONLY what the tools return. Cite "
    "supporting passages inline with their bracketed numbers, e.g. [1]. Use only the bracketed "
    "numbers from tool results; ignore any other bracketed numbers inside the text.\n"
    "- Only if the tools genuinely surface nothing relevant, say you don't have enough information "
    "in the user's sources or draft. Never use outside knowledge for research questions, and never "
    "invent citations."
)

AGENT_EXTRA = (
    "\n\nYou are in Agent mode: you can edit the user's draft files. Choosing the right tool "
    "matters:\n"
    "- write_file(path, content): creates a new file, or replaces a file's ENTIRE contents. Use it "
    "for a brand-new file, an EMPTY file, or to lay down a full document/scaffold. content must be "
    "the complete file text.\n"
    "- edit_file(path, old_string, new_string): changes part of a file that ALREADY has content, "
    "leaving the rest untouched. To insert, set old_string to an exact existing snippet (e.g. "
    "'\\end{document}') and new_string to that snippet plus your additions.\n"
    "Rules:\n"
    "- If a file is empty or new, use write_file — do NOT try to edit_file an empty file.\n"
    "- If a file already has content and you only want to add to or change part of it, use "
    "edit_file — do NOT call write_file with only the new part, because that deletes everything "
    "else.\n"
    "- If edit_file reports the snippet wasn't found, read the file again, then use an exact "
    "existing snippet, or use write_file if the file is empty.\n"
    "Always make changes through these tools (never paste file contents as chat text), read a file "
    "before editing it, and finish with a one-sentence summary of what you changed.\n"
    "Crucially: actually CARRY OUT the changes the user asked for by calling write_file/edit_file — "
    "do not end your turn having only searched or read. Never tell the user you added, wrote, or "
    "changed something unless you actually called write_file or edit_file to do it.\n\n"
    "Keep the WHOLE project consistent, not just the file you are editing — a LaTeX project compiles "
    "as one document:\n"
    "- Document-level commands (\\documentclass, \\usepackage, \\begin{document}, \\end{document}, "
    "\\bibliographystyle, \\bibliography) belong ONLY in the root document (e.g. main.tex), exactly "
    "once each. A file that is \\input or \\include'd must contain only its section content; putting "
    "these commands in it duplicates them when the root compiles (e.g. two \\bibliography commands "
    "break the bibliography). Before adding a bibliography, read the root file and reuse the one it "
    "already has.\n"
    "- To cite sources or build references.bib, FIRST call get_references and copy its BibTeX "
    "entries and \\cite keys verbatim — never invent titles, authors, years, or keys from memory. "
    "Only paper sources are citable: never \\cite a dataset or add it to references.bib (mention "
    "datasets descriptively in the text instead). If get_references reports a paper has no verified "
    "metadata, do not fabricate a reference — tell the user it couldn't be retrieved.\n"
    "- Citations must be consistent across files: every \\cite{key} must have a BibTeX entry "
    "@type{key, ...} under the IDENTICAL key in the .bib file, and vice versa — no \\cite without an "
    "entry, no unused entries. Use the same key on both sides; never cite one key and define a "
    "different one."
)


def _ref_key(fields: dict) -> tuple:
    loc = fields.get("loc") or {}
    return (fields.get("kind"), fields.get("source_id") or fields.get("file_id"), loc.get("page"))


def _register(registry: list[dict], **fields: object) -> int:
    """Register a citation, reusing the index if the same source+page is already present."""
    key = _ref_key(fields)
    for existing in registry:
        if _ref_key(existing) == key:
            return existing["index"]
    index = len(registry) + 1
    registry.append({"index": index, **fields})
    return index


def _finalize(text: str, registry: list[dict]) -> tuple[str, list[dict]]:
    """Renumber the answer's citations to a clean, contiguous 1..K in order of appearance,
    dropping markers that don't map to a retrieved source."""
    by_index = {c["index"]: c for c in registry}
    key_to_number: dict[tuple, int] = {}
    citations: list[dict] = []

    def replace(match: re.Match) -> str:
        citation = by_index.get(int(match.group(1)))
        if citation is None:
            return ""  # a stray number that isn't one of our sources
        key = _ref_key(citation)
        if key not in key_to_number:
            number = len(citations) + 1
            key_to_number[key] = number
            citations.append({**citation, "index": number})
        return f"[{key_to_number[key]}]"

    cleaned = re.sub(r"\[(\d+)\]", replace, text)
    cleaned = re.sub(r" +([.,;:])", r"\1", cleaned)  # tidy spacing left by dropped markers
    return cleaned, citations


def _format_chunks(chunks: Sequence[RetrievedChunk], registry: list[dict]) -> str:
    if not chunks:
        return "No relevant passages were found."
    blocks = []
    for chunk in chunks:
        index = _register(
            registry,
            kind=chunk.kind,
            filename=chunk.filename,
            loc=chunk.loc,
            source_id=chunk.source_id,
            file_id=chunk.file_id,
        )
        loc = _format_loc(chunk.loc)
        header = f"[{index}] {chunk.filename}" + (f" ({loc})" if loc else "")
        blocks.append(f"{header}: {_strip_inline_refs(chunk.text)}")
    return "\n\n".join(blocks)


def _tool_summary(name: str, args: dict) -> str:
    if name == "search_sources":
        return f'Searched sources: "{args.get("query", "")}"'
    if name == "search_draft":
        return f'Searched draft: "{args.get("query", "")}"'
    if name == "list_sources":
        return "Listed sources"
    if name == "list_files":
        return "Listed draft files"
    if name == "read_file":
        return f"Read {args.get('path', '')}"
    if name == "get_references":
        return "Looked up references"
    if name == "write_file":
        return f"Wrote {args.get('path', '')}"
    if name == "edit_file":
        return f"Edited {args.get('path', '')}"
    return name


async def _load_file_content(project_id, path: str) -> str | None:
    async with get_sessionmaker()() as session:
        items = await files_service.list_files(session, project_id)
    match = next((f for f in items if f.path == path), None)
    return match.content if match else None


def _make_diff(path: str, old: str, new: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""
        )
    )


def _build_tools(project_id, registry: list[dict], edits: dict, mode: str) -> list:
    @tool
    async def search_sources(query: str) -> str:
        """Search the user's uploaded sources (papers and datasets) for passages relevant to the
        query. Returns numbered results that should be cited."""
        chunks = await retrieve(project_id, query, types=["source"])
        return _format_chunks(chunks, registry)

    @tool
    async def search_draft(query: str) -> str:
        """Search the user's current LaTeX draft for passages relevant to the query. Returns
        numbered results that should be cited."""
        chunks = await retrieve(project_id, query, types=["draft"])
        return _format_chunks(chunks, registry)

    @tool
    async def list_sources() -> str:
        """List all of the user's uploaded sources (filename and type)."""
        async with get_sessionmaker()() as session:
            items = await sources_service.list_sources(session, project_id)
        if not items:
            return "The user has not uploaded any sources yet."
        return "Sources:\n" + "\n".join(f"- {s.filename} ({s.kind})" for s in items)

    @tool
    async def list_files() -> str:
        """List the files in the user's current LaTeX draft."""
        async with get_sessionmaker()() as session:
            items = await files_service.list_files(session, project_id)
        if not items:
            return "The draft has no files."
        return "Draft files:\n" + "\n".join(f"- {f.path}" for f in items)

    @tool
    async def read_file(path: str) -> str:
        """Read the full content of a file in the user's draft by its path (e.g. 'main.tex')."""
        async with get_sessionmaker()() as session:
            items = await files_service.list_files(session, project_id)
            match = next((f for f in items if f.path == path), None)
            if match is None:
                return (
                    f"No draft file named '{path}'. If '{path}' is an uploaded source, use "
                    "search_sources to read it — read_file only opens the user's own draft files."
                )
            content = match.content
        index = _register(registry, kind="draft", filename=path, loc={}, file_id=str(match.id))
        return f"[{index}] {path} (draft):\n{_strip_inline_refs(content)[:_READ_FILE_CHAR_LIMIT]}"

    @tool
    async def get_references() -> str:
        """Return verified BibTeX entries (and their \\cite keys) for the user's paper sources, for
        citing them and for building references.bib. Use the entries and keys VERBATIM — never
        invent bibliographic details. Datasets are not citable references."""
        async with get_sessionmaker()() as session:
            items = await sources_service.list_sources(session, project_id)
        if not items:
            return "The user has not uploaded any sources yet."
        cited = [s for s in items if s.kind == "paper" and s.bibtex]
        without = [s for s in items if s.kind == "paper" and not s.bibtex]
        datasets = [s for s in items if s.kind == "dataset"]
        sections: list[str] = []
        if cited:
            entries = "\n\n".join(s.bibtex for s in cited)
            mapping = "\n".join(f"- {s.filename} -> \\cite{{{s.cite_key}}}" for s in cited)
            sections.append(
                "Verified references — put these entries in references.bib and cite with the keys "
                f"shown, both verbatim:\n\n{entries}\n\nFilename to citation key:\n{mapping}"
            )
        if datasets:
            sections.append(
                "These are datasets, not papers — do NOT add them to references.bib or \\cite them; "
                "refer to them descriptively in the text instead:\n"
                + "\n".join(f"- {s.filename}" for s in datasets)
            )
        if without:
            sections.append(
                "These papers have no verified citation metadata (no arXiv id or DOI was found) — do "
                "NOT fabricate a reference for them; tell the user a citation could not be retrieved:\n"
                + "\n".join(f"- {s.filename}" for s in without)
            )
        return "\n\n".join(sections)

    tools = [search_sources, search_draft, list_sources, list_files, read_file, get_references]
    if mode != "agentic":
        return tools

    @tool
    async def write_file(path: str, content: str) -> str:
        """Propose creating a new draft file, or overwriting an existing one, with the given full
        content. The change is shown to the user for approval before being applied."""
        if path not in edits["original"]:
            edits["original"][path] = await _load_file_content(project_id, path) or ""
        edits["working"][path] = content
        return f"Proposed writing {path}. It will be shown to the user for approval."

    @tool
    async def edit_file(path: str, old_string: str, new_string: str = "") -> str:
        """Propose replacing an exact text snippet in a draft file. old_string must appear in the
        file; new_string is the replacement (empty deletes the snippet). The change is shown to the
        user for approval before being applied."""
        if path not in edits["original"]:
            existing = await _load_file_content(project_id, path)
            if existing is None:
                return f"No draft file named '{path}'. Use write_file to create it."
            edits["original"][path] = existing
            edits["working"][path] = existing
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


async def run_agent(
    project_id,
    query: str,
    history: Sequence[tuple[str, str]],
    source_names: Sequence[str] = (),
    mode: str = "qa",
) -> AsyncIterator[dict]:
    """Run the agent. In 'agentic' mode it can also propose draft edits (emitted as proposed_edit
    events after the final answer). Yields tool_call, token, final, and proposed_edit events."""
    settings = get_settings()
    registry: list[dict] = []
    edits: dict = {"original": {}, "working": {}}
    tools = _build_tools(project_id, registry, edits, mode)
    tools_by_name = {t.name: t for t in tools}
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
        timeout=_REQUEST_TIMEOUT,
    ).bind_tools(tools)

    async def execute_tool(call: dict) -> str:
        tool = tools_by_name.get(call["name"])
        if tool is None:
            return f"Unknown tool '{call['name']}'."
        try:
            return str(await tool.ainvoke(call.get("args", {})))
        except Exception as exc:  # noqa: BLE001 — feed a clear, actionable error back to the model
            logger.warning("tool %s failed: %s", call["name"], exc)
            hint = _TOOL_USAGE.get(call["name"], "")
            return f"That {call['name']} call was invalid ({exc.__class__.__name__}). {hint}".strip()

    inventory = "; ".join(source_names) if source_names else "(none uploaded yet)"
    system = ASK_SYSTEM + (AGENT_EXTRA if mode == "agentic" else "")
    messages: list = [
        SystemMessage(content=f"{system}\n\nThe user's project currently contains these sources: {inventory}.")
    ]
    for role, content in history:
        messages.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
    messages.append(HumanMessage(content=query))

    answer_parts: list[str] = []
    answered = False
    started = time.monotonic()
    for _ in range(MAX_ITERATIONS):
        if time.monotonic() - started > _RUN_TIMEOUT:
            logger.warning("agent run exceeded the %ss budget", _RUN_TIMEOUT)
            break

        gathered = None
        async for chunk in llm.astream(messages):
            if chunk.content:
                text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                answer_parts.append(text)
                yield {"type": "token", "text": text}
            gathered = chunk if gathered is None else gathered + chunk

        messages.append(gathered)
        tool_calls = getattr(gathered, "tool_calls", None) or []
        if not tool_calls:
            answered = True
            break

        for call in tool_calls:
            yield {"type": "tool_call", "summary": _tool_summary(call["name"], call.get("args", {}))}
        # Run this turn's tool calls concurrently, then append results in order.
        results = await asyncio.gather(*(execute_tool(call) for call in tool_calls))
        for call, result in zip(tool_calls, results):
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))

    # If the run ended on tool calls without a closing message, ask for a short summary
    # (no tools) so the user always gets a textual answer.
    if not answered and not "".join(answer_parts).strip():
        plain = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=_REQUEST_TIMEOUT,
        )
        messages.append(
            HumanMessage(content="Briefly summarize for the user what you did, in 1-3 sentences.")
        )
        async for chunk in plain.astream(messages):
            if chunk.content:
                text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                answer_parts.append(text)
                yield {"type": "token", "text": text}

    full = "".join(answer_parts).strip() or "I wasn't able to produce an answer for that."
    # Renumber citations cleanly; the frontend swaps the streamed text for this final version.
    cleaned, citations = _finalize(full, registry)
    yield {"type": "final", "content": cleaned, "citations": citations}

    # One proposed edit per changed file (original vs final working copy).
    for path, new_content in edits["working"].items():
        original = edits["original"].get(path, "")
        if new_content != original:
            yield {
                "type": "proposed_edit",
                "path": path,
                "diff": _make_diff(path, original, new_content),
                "content": new_content,
            }
