"""Build the frozen 80-task eval set (`eval_set.jsonl`): 20 each of lookup, synthesis,
abstention, latex.

Pulled from the **validation** splits of the same public datasets the training set draws from
(so there's no train/test leakage), plus the authored LaTeX tasks in `latex_tasks.json`:

  lookup     20  squad_v2 (answerable)            single source -> retrieve + cite [1]
  synthesis  20  hotpot_qa (distractor)           multiple sources -> combine + cite
  abstention 20  squad_v2 (10 unanswerable + 10 answerable controls)
  latex      20  latex_tasks.json                 edit a draft so it still compiles

Usage
  python -m eval.tasks.build_eval_set --check        # validate an existing eval_set.jsonl, offline
  python -m eval.tasks.build_eval_set                 # build (needs `datasets` + network)
  python -m eval.tasks.build_eval_set --per-category 5   # smaller set for a quick smoke run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "eval_set.jsonl"
LATEX_SEED = HERE / "latex_tasks.json"

CATEGORIES = ("lookup", "synthesis", "abstention", "latex")


def _src(filename: str, text: str, kind: str = "paper") -> dict:
    return {"filename": filename, "kind": kind, "chunks": [{"text": text, "loc": {}}]}


def build_latex(per_category: int) -> list[dict]:
    seeds = json.loads(LATEX_SEED.read_text(encoding="utf-8"))
    tasks = []
    for s in seeds[:per_category]:
        draft = [{"path": "main.tex", "content": s["main"]}]
        draft += s.get("extra_files", [])
        tasks.append(
            {
                "id": s["id"],
                "category": "latex",
                "question": s["instruction"],
                "sources": [],
                "draft_files": draft,
                "expected_tools": ["edit_file", "write_file"],
                "gold_answer": s["instruction"],
                "answerable": True,
            }
        )
    return tasks


def build_from_hf(per_category: int) -> list[dict]:
    from datasets import load_dataset

    tasks: list[dict] = []

    # --- squad_v2 validation: lookup (answerable) + abstention (unanswerable + controls) ---
    squad = load_dataset("rajpurkar/squad_v2", split="validation")
    answerable, unanswerable = [], []
    for ex in squad:
        (answerable if ex["answers"]["text"] else unanswerable).append(ex)
        if len(answerable) >= per_category * 2 and len(unanswerable) >= per_category // 2:
            break

    for i, ex in enumerate(answerable[:per_category]):
        tasks.append(
            {
                "id": f"lk-{i:02d}",
                "category": "lookup",
                "question": ex["question"],
                "sources": [_src(f"doc_lk_{i:02d}.txt", ex["context"])],
                "draft_files": [],
                "expected_tools": ["search_sources"],
                "gold_answer": ex["answers"]["text"][0],
                "answerable": True,
            }
        )

    half = per_category // 2
    abst = [(ex, False) for ex in unanswerable[:half]]
    abst += [(ex, True) for ex in answerable[per_category : per_category + (per_category - half)]]
    for i, (ex, ans) in enumerate(abst):
        tasks.append(
            {
                "id": f"ab-{i:02d}",
                "category": "abstention",
                "question": ex["question"],
                "sources": [_src(f"doc_ab_{i:02d}.txt", ex["context"])],
                "draft_files": [],
                "expected_tools": ["search_sources"],
                "gold_answer": ex["answers"]["text"][0] if ans and ex["answers"]["text"] else "",
                "answerable": ans,
            }
        )

    # --- hotpot_qa validation: synthesis (multi-source) ---
    hotpot = load_dataset("hotpotqa/hotpot_qa", "distractor", split="validation")
    count = 0
    for ex in hotpot:
        ctx = ex.get("context", {})
        titles, sents = ctx.get("title", []), ctx.get("sentences", [])
        if not titles or len(titles) != len(sents):
            continue
        sources = [_src(f"{t}.txt", " ".join(s)) for t, s in zip(titles, sents)]
        tasks.append(
            {
                "id": f"sy-{count:02d}",
                "category": "synthesis",
                "question": ex["question"],
                "sources": sources,
                "draft_files": [],
                "expected_tools": ["search_sources"],
                "gold_answer": ex["answer"],
                "answerable": True,
            }
        )
        count += 1
        if count >= per_category:
            break

    return tasks


REQUIRED = {"id", "category", "question", "sources", "draft_files", "expected_tools", "gold_answer", "answerable"}


def check(path: Path) -> int:
    if not path.exists():
        print(f"[FAIL] {path} does not exist — run the builder first.")
        return 1
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    ok = True
    for r in rows:
        missing = REQUIRED - set(r)
        if missing:
            print(f"[FAIL] {r.get('id', '?')}: missing {missing}")
            ok = False
        if r.get("category") in counts:
            counts[r["category"]] += 1
        if r["category"] != "latex" and not r["sources"]:
            print(f"[FAIL] {r['id']}: non-latex task has no sources")
            ok = False
        if r["category"] == "latex" and not any(f["path"] == "main.tex" for f in r["draft_files"]):
            print(f"[FAIL] {r['id']}: latex task has no main.tex")
            ok = False
    print(f"{len(rows)} tasks: {counts}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate existing eval_set.jsonl offline")
    ap.add_argument("--per-category", type=int, default=20)
    args = ap.parse_args()

    if args.check:
        return check(OUT)

    tasks = build_from_hf(args.per_category) + build_latex(args.per_category)
    with OUT.open("w", encoding="utf-8") as fh:
        for t in tasks:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"Wrote {len(tasks)} tasks to {OUT}")
    return check(OUT)


if __name__ == "__main__":
    raise SystemExit(main())
