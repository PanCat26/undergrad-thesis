"""Run the eval suite for ONE model and emit the thesis tables.

  # API models — run now (needs OPENAI_API_KEY for the agent, ANTHROPIC_API_KEY for the judge):
  python -m eval.run_eval --model gpt-4.1-mini
  python -m eval.run_eval --model gpt-5.4-mini

  # Local Qwen variants — start the matching vLLM server first (see serving/serve_vllm.md):
  python -m eval.run_eval --model qwen3-8b-sft

  # Offline wiring check (no API/keys): canned answers through the deterministic scorers + Tectonic:
  python -m eval.run_eval --dry-run

Each run writes results/<model>.json, then (re)builds results/results_table.md and
results/deployability.md across every model evaluated so far — so the comparison table fills in
as you evaluate each of the 5 models.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from pathlib import Path

from eval import models
from eval.harness.runner import RunResult, run_task
from eval.scorers import latex as latex_scorer
from eval.scorers import tool_use as tool_use_scorer

HERE = Path(__file__).parent
RESULTS = HERE / "results"
DEFAULT_TASKS = HERE / "tasks" / "eval_set.jsonl"


def _load_tasks(path: Path, limit: int | None) -> list[dict]:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[:limit] if limit else rows


def _canned(task: dict) -> RunResult:
    """A fake run for --dry-run: plausible content/trace so the deterministic scorers exercise."""
    r = RunResult(task_id=task["id"], category=task["category"])
    r.content = task.get("gold_answer") or "I don't have enough information in your sources to answer that."
    r.content = r.content + " [1]" if task["category"] in {"lookup", "synthesis"} else r.content
    tool = (task.get("expected_tools") or ["search_sources"])[0]
    r.tool_trace = [{"name": tool, "args": {"query": task["question"]} if "search" in tool else {"path": "main.tex", "content": ""}}]
    if task["category"] == "latex":
        # Echo the original main.tex unchanged — exercises compile without guessing the fix.
        main = next((f["content"] for f in task["draft_files"] if f["path"] == "main.tex"), "")
        r.proposed_edits = {"main.tex": main}
    r.latency_s, r.ttft_s, r.output_tokens = 1.0, 0.2, 50
    return r


def _aggregate(scored: list[dict]) -> dict:
    def mean(vals):
        vals = [v for v in vals if isinstance(v, (int, float))]
        return round(statistics.mean(vals), 4) if vals else None

    qa = [s for s in scored if s["category"] in {"lookup", "synthesis"}]
    abst = [s for s in scored if s["category"] == "abstention"]
    tex = [s for s in scored if s["category"] == "latex"]
    compiled = [s["latex"]["compiled"] for s in tex if s.get("latex", {}).get("compiled") is not None]

    return {
        "n": len(scored),
        "tool_appropriate": mean(s["tool_use"]["appropriate"] for s in scored),
        "arg_valid": mean(s["tool_use"]["arg_valid"] for s in scored),
        "faithfulness": mean(s.get("grounding", {}).get("faithfulness") for s in qa),
        "citation": mean(s.get("grounding", {}).get("citation") for s in qa),
        "abstention_acc": mean(s.get("abstention", {}).get("correct") for s in abst),
        "compile_rate": (round(sum(compiled) / len(compiled), 4) if compiled else None),
        "compile_n_scored": len(compiled),
        "quality_1_5": mean(s.get("quality", {}).get("score_1_5") for s in qa),
        "avg_tokens_per_sec": mean(s["perf"]["tokens_per_sec"] for s in scored),
        "avg_ttft_s": mean(s["perf"]["ttft_s"] for s in scored),
        "errors": sum(1 for s in scored if s.get("error")),
    }


def _score_one(task: dict, result: RunResult, use_judge: bool, judge) -> dict:
    entry = {
        "id": result.task_id,
        "category": result.category,
        "error": result.error,
        "tool_use": tool_use_scorer.score_tool_use(task, result),
        "perf": {"tokens_per_sec": result.tokens_per_sec, "ttft_s": result.ttft_s, "latency_s": result.latency_s},
    }
    if result.category == "latex":
        entry["latex"] = latex_scorer.score_latex(task, result)
    if use_judge and result.category in {"lookup", "synthesis"}:
        from eval.scorers import grounding, quality

        entry["grounding"] = grounding.score_grounding(task, result, judge)
        entry["quality"] = quality.score_quality(task, result, judge)
    if use_judge and result.category == "abstention":
        from eval.scorers import abstention

        entry["abstention"] = abstention.score_abstention(task, result, judge)
    return entry


async def _run_live(tasks: list[dict], spec) -> list[RunResult]:
    results = []
    for i, task in enumerate(tasks, 1):
        print(f"  [{i}/{len(tasks)}] {task['id']} ({task['category']})", flush=True)
        results.append(await run_task(task, spec))
    return results


def _write_tables() -> None:
    rows = []
    for name in models.COMPARISON:
        path = RESULTS / f"{name}.json"
        if path.exists():
            rows.append((name, json.loads(path.read_text(encoding="utf-8"))["aggregate"]))
    if not rows:
        return

    def cell(v):
        return "n/a" if v is None else (f"{v}")

    headers = ["model", "tool_appropriate", "arg_valid", "faithfulness", "citation",
               "abstention_acc", "compile_rate", "quality_1_5"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for name, agg in rows:
        lines.append("| " + " | ".join([name, *[cell(agg.get(h)) for h in headers[1:]]]) + " |")
    (RESULTS / "results_table.md").write_text(
        "# Quality results (one row per model evaluated)\n\n" + "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    dep = ["| model | avg_tokens_per_sec | avg_ttft_s | on_disk_size_GB |", "|---|---|---|---|"]
    for name, agg in rows:
        size = "—" if name.startswith("gpt-") else "(fill from `ls -la *.gguf` / merged dir)"
        dep.append(f"| {name} | {cell(agg.get('avg_tokens_per_sec'))} | {cell(agg.get('avg_ttft_s'))} | {size} |")
    (RESULTS / "deployability.md").write_text(
        "# Deployability (local models). $/task for API models is billed usage.\n\n"
        + "\n".join(dep) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {RESULTS/'results_table.md'} and {RESULTS/'deployability.md'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default=None, help=f"one of: {', '.join(models.REGISTRY)}")
    ap.add_argument("--tasks", default=str(DEFAULT_TASKS))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="canned answers, deterministic scorers only, no API")
    ap.add_argument("--no-judge", action="store_true", help="skip the Claude judge metrics")
    args = ap.parse_args()

    tasks = _load_tasks(Path(args.tasks), args.limit)
    RESULTS.mkdir(parents=True, exist_ok=True)
    use_judge = not (args.dry_run or args.no_judge)
    judge = None
    if use_judge:
        from eval.scorers.judge import get_judge

        judge = get_judge()

    if args.dry_run:
        spec_name = "dry-run"
        results = [_canned(t) for t in tasks]
    else:
        spec = models.get(args.model)
        spec_name = spec.name
        print(f"Running {spec_name} ({spec.model}) on {len(tasks)} tasks...")
        results = asyncio.run(_run_live(tasks, spec))

    scored = [_score_one(t, r, use_judge, judge) for t, r in zip(tasks, results)]
    aggregate = _aggregate(scored)
    print("\nAggregate:", json.dumps(aggregate, indent=2))

    if not args.dry_run:
        out = RESULTS / f"{spec_name}.json"
        out.write_text(json.dumps({"model": spec_name, "aggregate": aggregate, "tasks": scored}, indent=2), encoding="utf-8")
        print(f"Wrote {out}")
        _write_tables()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
