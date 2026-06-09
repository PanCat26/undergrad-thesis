import re
from collections.abc import AsyncIterator, Sequence

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.rag.retrieve import RetrievedChunk

SYSTEM_PROMPT = (
    "You are a research assistant embedded in an academic writing tool. You help the user with "
    "their uploaded sources (papers and datasets) and their current LaTeX draft.\n\n"
    "How to respond:\n"
    "- For greetings, small talk, or questions about who you are or what you can do, reply "
    "naturally and briefly without citing anything.\n"
    "- For questions about the user's sources or draft, answer using ONLY the numbered context "
    "below, and cite the parts you use inline with bracketed numbers like [1]. The context is "
    "drawn from the user's sources and current draft.\n"
    "- If the user asks a research or factual question and the context does not contain the "
    "answer, say you don't have enough information in the provided sources or draft. Never use "
    "outside knowledge for such questions, and never invent citations."
)

_CITATION_RE = re.compile(r"\[(\d+)\]")
# Reference markers that appear inside the source text itself (a paper's own
# bibliography numbers, e.g. "[31]" or "[12, 14]") — removed so they don't get
# confused with our context citation labels.
_INLINE_REF_RE = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")


def used_citation_indices(text: str) -> set[int]:
    """Citation numbers the model actually referenced in its answer."""
    return {int(match) for match in _CITATION_RE.findall(text)}


def _strip_inline_refs(text: str) -> str:
    return _INLINE_REF_RE.sub("", text)


def _format_loc(loc: dict) -> str:
    if loc.get("page"):
        return f"page {loc['page']}"
    return ""


def build_citations(chunks: Sequence[RetrievedChunk]) -> list[dict]:
    citations = []
    for index, chunk in enumerate(chunks, start=1):
        citations.append(
            {
                "index": index,
                "kind": chunk.kind,
                "filename": chunk.filename,
                "loc": chunk.loc,
                "source_id": chunk.source_id,
                "file_id": chunk.file_id,
            }
        )
    return citations


def _build_context(chunks: Sequence[RetrievedChunk]) -> str:
    if not chunks:
        return "(no relevant context was found in the user's sources or draft)"
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        loc = _format_loc(chunk.loc)
        header = f"[{index}] {chunk.filename}" + (f" — {loc}" if loc else "")
        blocks.append(f"{header}\n{_strip_inline_refs(chunk.text)}")
    return "\n\n".join(blocks)


async def stream_answer(
    query: str,
    chunks: Sequence[RetrievedChunk],
    history: Sequence[tuple[str, str]],
    source_names: Sequence[str] = (),
) -> AsyncIterator[str]:
    """Stream the answer token-by-token. `history` is (role, content) pairs."""
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    inventory = "; ".join(source_names) if source_names else "(none uploaded yet)"
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"The user's project currently contains these sources: {inventory}.\n\n"
        f"Cite only with the bracketed labels of the context blocks below (e.g. [1], [2]); "
        f"ignore any other bracketed numbers that may appear inside the text.\n\n"
        f"Context:\n{_build_context(chunks)}"
    )
    messages: list = [SystemMessage(content=system)]
    for role, content in history:
        messages.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
    messages.append(HumanMessage(content=query))

    async for chunk in llm.astream(messages):
        text = chunk.content
        if text:
            yield text if isinstance(text, str) else str(text)
