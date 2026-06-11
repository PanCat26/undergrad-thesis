"""Run one eval task through Evidentia's real agent loop and capture everything the scorers need.

Reuses the **production** ``_run_tool_loop`` from ``backend/app/agent/ask.py`` (the same loop the
live app runs), but with eval tools over the task's bundled context and the model pointed at
whichever variant is under test. LaTeX tasks run in ``agentic`` mode (write/edit tools); all others
in ``qa`` mode.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.ask import AGENT_EXTRA, ASK_SYSTEM, _run_tool_loop
from app.agent.llm import LlmConfig
from eval.harness.tools import TaskContext, build_eval_tools

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover - tiktoken optional
    _ENC = None


def _count_tokens(text: str) -> int:
    if _ENC is not None:
        return len(_ENC.encode(text))
    return max(1, len(text) // 4)  # rough fallback


@dataclass
class RunResult:
    task_id: str
    category: str
    content: str = ""
    citations: list[dict] = field(default_factory=list)
    tool_trace: list[dict] = field(default_factory=list)  # [{name, args}]
    proposed_edits: dict[str, str] = field(default_factory=dict)  # path -> new content
    latency_s: float = 0.0
    ttft_s: float | None = None
    output_tokens: int = 0
    error: str | None = None

    @property
    def tokens_per_sec(self) -> float:
        gen = self.latency_s - (self.ttft_s or 0.0)
        return self.output_tokens / gen if gen > 0 else 0.0


async def run_task(task: dict, spec) -> RunResult:
    """Execute `task` against the model described by `spec` (an eval.models.ModelSpec)."""
    mode = "agentic" if task["category"] == "latex" else "qa"
    ctx = TaskContext(sources=task.get("sources", []), draft_files=task.get("draft_files", []))
    registry: list[dict] = []
    edits: dict = {"original": {}, "working": {}}
    trace: list[dict] = []
    tools = build_eval_tools(ctx, registry, edits, mode)

    inventory = "; ".join(s["filename"] for s in ctx.sources) or "(none uploaded yet)"
    system = ASK_SYSTEM + (AGENT_EXTRA if mode == "agentic" else "")
    messages: list = [
        SystemMessage(content=f"{system}\n\nThe user's project currently contains these sources: {inventory}."),
        HumanMessage(content=task["question"]),
    ]

    config = LlmConfig(model=spec.model, base_url=spec.base_url, api_key=spec.api_key)
    result = RunResult(task_id=task["id"], category=task["category"])
    streamed: list[str] = []
    started = time.monotonic()
    try:
        async for event in _run_tool_loop(
            messages, tools, config, registry=registry, edits=edits,
            temperature=spec.temperature, trace=trace,
        ):
            etype = event["type"]
            if etype == "token":
                if result.ttft_s is None:
                    result.ttft_s = time.monotonic() - started
                streamed.append(event["text"])
            elif etype == "final":
                result.content = event["content"]
                result.citations = event["citations"]
            elif etype == "proposed_edit":
                result.proposed_edits[event["path"]] = event["content"]
    except Exception as exc:  # noqa: BLE001 — record the failure, keep the sweep going
        result.error = f"{exc.__class__.__name__}: {exc}"
    result.latency_s = time.monotonic() - started
    result.tool_trace = trace
    result.output_tokens = _count_tokens("".join(streamed) or result.content)
    return result
