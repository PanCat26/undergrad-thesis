"""Assemble the QLoRA SFT training set for Evidentia.

Mixes six public datasets into ONE chat-format file (`out/train.jsonl` + `out/val.jsonl`), each
record `{"messages": [...], "tools": [...]}` in OpenAI/Qwen tools format so TRL's SFTTrainer can
apply Qwen3's chat template directly.

Slices (proportions match the thesis plan):
  tool use      40%  Salesforce/xlam-function-calling-60k + glaiveai/glaive-function-calling-v2
  grounding     30%  hotpot_qa (supporting facts -> [n] citation targets)
  abstention    15%  rajpurkar/squad_v2 (unanswerable half -> refusals; answerable -> controls)
  scientific    10%  allenai/qasper (QA grounded in paper evidence)
  latex          5%  synthetic write_file/edit_file trajectories over small LaTeX docs

Design notes
- The function-calling slices (xLAM, Glaive) keep their OWN tool schemas — they build general
  tool-calling competence, which transfers to Evidentia's tools at inference.
- The grounding/abstention/scientific slices are rewritten into Evidentia's OWN agent trajectory:
  user question -> assistant calls `search_sources` -> tool returns chunks formatted with [n] ->
  assistant answers citing [n] (or abstains). This is what teaches the app's behaviour.
- The LaTeX slice is SYNTHESIZED as write_file/edit_file trajectories (deliberate: peS2o is
  cleaned prose, not LaTeX source, and synthetic edits teach the agentic editing the eval scores).
  Documented deviation from "public-only"; it is 5% of the mix.

All slices read each dataset's TRAIN split; the eval set (`eval/tasks/build_eval_set.py`) pulls
from the VALIDATION splits, so there is no train/test leakage.

Usage
  python -m data.build_dataset --selftest                 # no network: validate converters
  python -m data.build_dataset --total 1000 --limit 50    # tiny smoke build
  python -m data.build_dataset --total 16000              # full build
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from data.schema import AGENTIC_TOOLS, QA_TOOLS, allowed_args, required_args

OUT_DIR = Path(__file__).parent / "out"

# slice -> fraction of the total
PROPORTIONS = {
    "xlam": 0.25,
    "glaive": 0.15,
    "hotpot": 0.30,
    "squad": 0.15,
    "qasper": 0.10,
    "latex": 0.05,
}

# The single search_sources tool the grounded trajectories expose to the model.
_SEARCH_TOOLS = [t for t in QA_TOOLS if t["function"]["name"] == "search_sources"]
_ABSTENTION = "I don't have enough information in your sources to answer that."


# --------------------------------------------------------------------------- message builders
def _user(content: str) -> dict:
    return {"role": "user", "content": content}


def _assistant(content: str) -> dict:
    return {"role": "assistant", "content": content}


def _tool_call(call_id: str, name: str, args: dict) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
            }
        ],
    }


def _tool_result(call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _balanced_json_objects(text: str) -> list[dict]:
    """Yield every top-level brace-balanced {...} in `text` that parses as a JSON object.

    Used to pull function definitions / call payloads out of Glaive's flat transcript, where the
    JSON nests arbitrarily deep (so a fixed-depth regex misses them)."""
    objects: list[dict] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    obj = json.loads(text[start : i + 1])
                    if isinstance(obj, dict):
                        objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = -1
    return objects


def _format_chunks(chunks: list[str]) -> str:
    """Mirror backend `_format_chunks`: numbered [n] blocks the model learns to cite."""
    if not chunks:
        return "No relevant passages were found."
    return "\n\n".join(f"[{i}] {text}" for i, text in enumerate(chunks, 1))


def _search_trajectory(question: str, chunks: list[str], answer: str) -> dict:
    """A canonical grounded trajectory: ask -> search_sources -> chunks -> cited answer."""
    cid = "call_1"
    return {
        "messages": [
            _user(question),
            _tool_call(cid, "search_sources", {"query": question}),
            _tool_result(cid, _format_chunks(chunks)),
            _assistant(answer),
        ],
        "tools": _SEARCH_TOOLS,
    }


# --------------------------------------------------------------------------- converters
def convert_xlam(ex: dict) -> dict | None:
    """xLAM keeps its own tools; teaches general function-calling format."""
    try:
        tools = ex["tools"] if isinstance(ex["tools"], list) else json.loads(ex["tools"])
        answers = ex["answers"] if isinstance(ex["answers"], list) else json.loads(ex["answers"])
    except (KeyError, json.JSONDecodeError, TypeError):
        return None
    if not answers:
        return None
    calls = [
        {
            "id": f"call_{i}",
            "type": "function",
            "function": {
                "name": a["name"],
                "arguments": json.dumps(a.get("arguments", {}), ensure_ascii=False),
            },
        }
        for i, a in enumerate(answers, 1)
        if a.get("name")
    ]
    if not calls:
        return None
    tool_schemas = [{"type": "function", "function": t} for t in tools]
    return {
        "messages": [_user(ex["query"]), {"role": "assistant", "content": "", "tool_calls": calls}],
        "tools": tool_schemas,
    }


def convert_glaive(ex: dict) -> dict | None:
    """Parse Glaive's flat `system`+`chat` transcript into messages + its own tools."""
    import re

    system = ex.get("system", "") or ""
    chat = ex.get("chat", "") or ""
    # Tool defs live as one-JSON-per-block after the preamble in `system` (arbitrarily nested).
    tools = [
        {"type": "function", "function": fn}
        for fn in _balanced_json_objects(system)
        if "name" in fn and "parameters" in fn
    ]
    if not tools:
        return None

    messages: list[dict] = []
    n = 0
    for turn in re.split(r"\n(?=USER:|ASSISTANT:|FUNCTION RESPONSE:)", chat.strip()):
        turn = turn.strip()
        if turn.startswith("USER:"):
            messages.append(_user(turn[len("USER:") :].strip()))
        elif turn.startswith("ASSISTANT:"):
            body = turn[len("ASSISTANT:") :].strip().replace("<|endoftext|>", "").strip()
            if "<functioncall>" in body:
                tail = body.split("<functioncall>", 1)[1]
                payloads = _balanced_json_objects(tail)
                payload = next((p for p in payloads if p.get("name")), None)
                if payload:
                    n += 1
                    args = payload.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    messages.append(_tool_call(f"call_{n}", payload["name"], args))
                    continue
            messages.append(_assistant(body))
        elif turn.startswith("FUNCTION RESPONSE:"):
            content = turn[len("FUNCTION RESPONSE:") :].strip()
            cid = f"call_{n}" if n else "call_1"
            messages.append(_tool_result(cid, content))
    # Need at least one user turn and one assistant tool call to be useful.
    if not any(m["role"] == "user" for m in messages) or not any(
        m.get("tool_calls") for m in messages
    ):
        return None
    return {"messages": messages, "tools": tools}


def convert_hotpot(ex: dict) -> dict | None:
    """HotpotQA -> grounded multi-hop trajectory; supporting titles become the cited [n]."""
    ctx = ex.get("context", {})
    titles = ctx.get("title", [])
    sentences = ctx.get("sentences", [])
    if not titles or len(titles) != len(sentences):
        return None
    chunks = [f"{t}: {' '.join(s)}".strip() for t, s in zip(titles, sentences)]
    support_titles = set(ex.get("supporting_facts", {}).get("title", []))
    cited = [i for i, t in enumerate(titles, 1) if t in support_titles] or [1]
    answer = ex.get("answer", "").strip()
    if not answer:
        return None
    marks = "".join(f"[{i}]" for i in cited)
    return _search_trajectory(ex["question"], chunks, f"{answer} {marks}".strip())


def convert_squad(ex: dict) -> dict | None:
    """SQuAD v2 -> single-source trajectory; unanswerable -> abstention, answerable -> [1]."""
    question = ex.get("question", "").strip()
    context = ex.get("context", "").strip()
    if not question or not context:
        return None
    texts = ex.get("answers", {}).get("text", [])
    if texts:  # answerable control
        answer = f"{texts[0].strip()} [1]"
    else:  # unanswerable -> teach abstention
        answer = _ABSTENTION
    return _search_trajectory(question, [context], answer)


def convert_qasper(ex: dict) -> list[dict]:
    """QASPER -> one grounded trajectory per answerable question with extractive evidence.

    QASPER stores one paper per row with a parallel `qas` structure. We pull (question, evidence,
    answer) triples defensively and skip anything malformed or unanswerable-without-evidence.
    """
    out: list[dict] = []
    qas = ex.get("qas", {})
    questions = qas.get("question", [])
    answers_per_q = qas.get("answers", [])
    if not questions or len(questions) != len(answers_per_q):
        return out
    for question, ans_group in zip(questions, answers_per_q):
        answer_list = (ans_group or {}).get("answer", [])
        for ans in answer_list:
            evidence = [e for e in ans.get("evidence", []) if e and e.strip()]
            free = (ans.get("free_form_answer") or "").strip()
            extractive = [s for s in ans.get("extractive_spans", []) if s and s.strip()]
            text = free or ("; ".join(extractive) if extractive else "")
            if not evidence or not text or ans.get("unanswerable"):
                continue
            out.append(_search_trajectory(question.strip(), evidence[:4], f"{text} [1]"))
            break  # one trajectory per question is plenty
    return out


# ---- synthetic LaTeX edit/write trajectories (agentic mode) -------------------------------
_LATEX_TOOLS = [
    t for t in AGENTIC_TOOLS if t["function"]["name"] in {"read_file", "write_file", "edit_file"}
]

_LATEX_SECTIONS = [
    ("Introduction", "This paper investigates %s and its implications."),
    ("Related Work", "Prior studies have examined %s from several angles."),
    ("Methodology", "We describe our approach to %s in detail."),
    ("Results", "Our experiments on %s yield the following findings."),
    ("Conclusion", "We summarize our contributions on %s and outline future work."),
]
_LATEX_TOPICS = [
    "retrieval-augmented generation", "graph neural networks", "differential privacy",
    "speech recognition", "protein folding", "reinforcement learning", "model quantization",
    "semantic parsing", "time-series forecasting", "federated learning",
]


def synth_latex(rng: random.Random) -> dict:
    """Generate a write_file (new section file) or edit_file (insert before \\end{document})."""
    topic = rng.choice(_LATEX_TOPICS)
    title, body_tmpl = rng.choice(_LATEX_SECTIONS)
    body = body_tmpl % topic
    if rng.random() < 0.5:
        # write_file: a brand-new section fragment (no document-level commands).
        path = f"{title.lower().replace(' ', '_')}.tex"
        content = f"\\section{{{title}}}\n{body}\n"
        return {
            "messages": [
                _user(f"Create a {title.lower()} section file about {topic}."),
                _tool_call("call_1", "write_file", {"path": path, "content": content}),
                _tool_result("call_1", f"Proposed writing {path}."),
                _assistant(f"I created {path} with a {title.lower()} section on {topic}."),
            ],
            "tools": _LATEX_TOOLS,
        }
    # edit_file: insert a section just before \end{document} in main.tex.
    main = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{Overview}\nA short overview.\n\\end{document}\n"
    )
    insertion = f"\\section{{{title}}}\n{body}\n\\end{{document}}"
    return {
        "messages": [
            _user(f"Add a {title.lower()} section about {topic} to main.tex."),
            _tool_call("call_1", "read_file", {"path": "main.tex"}),
            _tool_result("call_1", f"[1] main.tex (draft):\n{main}"),
            _tool_call(
                "call_2",
                "edit_file",
                {"path": "main.tex", "old_string": "\\end{document}", "new_string": insertion},
            ),
            _tool_result("call_2", "Proposed edit to main.tex."),
            _assistant(f"I added a {title.lower()} section on {topic} before the end of the document."),
        ],
        "tools": _LATEX_TOOLS,
    }


# --------------------------------------------------------------------------- validation
def validate_record(rec: dict) -> list[str]:
    """Return a list of problems with a record (empty == valid)."""
    problems: list[str] = []
    if "messages" not in rec or not rec["messages"]:
        problems.append("no messages")
        return problems
    tool_names = {t["function"]["name"] for t in rec.get("tools", [])}
    for m in rec["messages"]:
        if m["role"] not in {"user", "assistant", "tool", "system"}:
            problems.append(f"bad role {m['role']}")
        for call in m.get("tool_calls", []):
            fn = call["function"]
            try:
                args = json.loads(fn["arguments"])
            except json.JSONDecodeError:
                problems.append(f"{fn['name']}: arguments not valid JSON")
                continue
            # For Evidentia-schema calls, check required/allowed args.
            if fn["name"] in {t["function"]["name"] for t in QA_TOOLS} or fn["name"] in {
                "write_file",
                "edit_file",
            }:
                missing = [a for a in required_args(fn["name"]) if a not in args]
                extra = [a for a in args if a not in allowed_args(fn["name"])]
                if missing:
                    problems.append(f"{fn['name']}: missing {missing}")
                if extra:
                    problems.append(f"{fn['name']}: unexpected {extra}")
            if fn["name"] not in tool_names and rec.get("tools"):
                problems.append(f"{fn['name']}: not in this record's tools")
    return problems


# --------------------------------------------------------------------------- selftest fixtures
def _selftest() -> int:
    fixtures = {
        "xlam": convert_xlam(
            {
                "query": "What is the weather in Paris and the time in Tokyo?",
                "tools": json.dumps(
                    [
                        {"name": "get_weather", "description": "w", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}},
                        {"name": "get_time", "description": "t", "parameters": {"type": "object", "properties": {"tz": {"type": "string"}}, "required": ["tz"]}},
                    ]
                ),
                "answers": json.dumps(
                    [
                        {"name": "get_weather", "arguments": {"city": "Paris"}},
                        {"name": "get_time", "arguments": {"tz": "Asia/Tokyo"}},
                    ]
                ),
            }
        ),
        "glaive": convert_glaive(
            {
                "system": 'SYSTEM: You are helpful with access to functions -\n{"name": "send_email", "description": "send", "parameters": {"type": "object", "properties": {"to": {"type": "string"}}, "required": ["to"]}}',
                "chat": 'USER: Email bob\n\n\nASSISTANT: Sure <functioncall> {"name": "send_email", "arguments": {"to": "bob@example.com"}} <|endoftext|>\n\n\nFUNCTION RESPONSE: {"status": "sent"}\n\n\nASSISTANT: Done, I sent it. <|endoftext|>',
            }
        ),
        "hotpot": convert_hotpot(
            {
                "question": "Which magazine was started first, A or B?",
                "answer": "A",
                "context": {"title": ["A", "B"], "sentences": [["A began in 1900."], ["B began in 1950."]]},
                "supporting_facts": {"title": ["A", "B"], "sent_id": [0, 0]},
            }
        ),
        "squad_yes": convert_squad(
            {"question": "Who wrote it?", "context": "It was written by Ada.", "answers": {"text": ["Ada"]}}
        ),
        "squad_no": convert_squad(
            {"question": "What is the price?", "context": "The book is about history.", "answers": {"text": []}}
        ),
        "qasper": (
            convert_qasper(
                {
                    "qas": {
                        "question": ["What dataset is used?"],
                        "answers": [
                            {"answer": [{"free_form_answer": "We use SQuAD.", "evidence": ["Experiments run on SQuAD."], "extractive_spans": [], "unanswerable": False}]}
                        ],
                    }
                }
            )
            or [None]
        )[0],
        "latex": synth_latex(random.Random(0)),
    }
    ok = True
    for name, rec in fixtures.items():
        if rec is None:
            print(f"  [FAIL] {name}: converter returned None")
            ok = False
            continue
        problems = validate_record(rec)
        status = "ok" if not problems else f"PROBLEMS: {problems}"
        print(f"  [{'ok' if not problems else 'FAIL'}] {name}: {status}")
        ok = ok and not problems
    # Show one rendered trajectory for eyeballing.
    print("\nSample (squad unanswerable):")
    print(json.dumps(fixtures["squad_no"], indent=2)[:900])
    return 0 if ok else 1


# --------------------------------------------------------------------------- build
def _load_split(name: str, limit: int | None):
    """Lazy import of `datasets` so --selftest needs no heavy deps."""
    from datasets import load_dataset

    spec = {
        "xlam": ("Salesforce/xlam-function-calling-60k", None, "train"),
        "glaive": ("glaiveai/glaive-function-calling-v2", None, "train"),
        "hotpot": ("hotpotqa/hotpot_qa", "distractor", "train"),
        "squad": ("rajpurkar/squad_v2", None, "train"),
        "qasper": ("allenai/qasper", None, "train"),
    }[name]
    path, config, split = spec
    if limit:
        split = f"{split}[:{limit}]"
    return load_dataset(path, config, split=split)


def _build_slice(name: str, target: int, limit: int | None, rng: random.Random) -> list[dict]:
    if name == "latex":
        return [synth_latex(rng) for _ in range(target)]
    converter = {
        "xlam": convert_xlam,
        "glaive": convert_glaive,
        "hotpot": convert_hotpot,
        "squad": convert_squad,
    }.get(name)
    records: list[dict] = []
    ds = _load_split(name, limit or target * 3)
    if name == "qasper":
        for ex in ds:
            for rec in convert_qasper(ex):
                if not validate_record(rec):
                    records.append(rec)
                if len(records) >= target:
                    break
            if len(records) >= target:
                break
        return records
    for ex in ds:
        rec = converter(ex)
        if rec and not validate_record(rec):
            records.append(rec)
        if len(records) >= target:
            break
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="validate converters offline, no network")
    ap.add_argument("--total", type=int, default=16000, help="approx total training examples")
    ap.add_argument("--limit", type=int, default=None, help="cap rows scanned per dataset (smoke runs)")
    ap.add_argument("--val-frac", type=float, default=0.02)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    if args.selftest:
        print("Running converter selftests...\n")
        return _selftest()

    rng = random.Random(args.seed)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_records: list[dict] = []
    for name, frac in PROPORTIONS.items():
        target = round(args.total * frac)
        print(f"Building slice '{name}' (target {target})...")
        recs = _build_slice(name, target, args.limit, rng)
        print(f"  -> {len(recs)} records")
        for r in recs:
            r["_slice"] = name
        all_records.extend(recs)

    rng.shuffle(all_records)
    n_val = max(1, round(len(all_records) * args.val_frac))
    val, train = all_records[:n_val], all_records[n_val:]

    def _dump(path: Path, rows: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    _dump(OUT_DIR / "train.jsonl", train)
    _dump(OUT_DIR / "val.jsonl", val)
    counts: dict[str, int] = {}
    for r in train:
        counts[r["_slice"]] = counts.get(r["_slice"], 0) + 1
    print(f"\nWrote {len(train)} train / {len(val)} val to {OUT_DIR}")
    print("Train slice mix:", {k: f"{v} ({v / len(train):.0%})" for k, v in counts.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
