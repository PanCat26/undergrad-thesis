# Evidentia: fine-tuning + evaluation

This directory holds the experiment that compares **5 models** on Evidentia's job (a grounded,
tool-using, LaTeX-editing research agent):

1. `gpt-4.1-mini` (API) · 2. `gpt-5.4-mini` (API) · 3. Qwen3-8B base · 4. Qwen3-8B QLoRA-SFT
(merged) · 5. Qwen3-8B SFT + 4-bit GGUF.

The goal is to measure how close a fine-tuned small local model gets to the closed API 
models on this narrow task. The directory is self-contained and kept out of the application's
dependency tree. The evaluation **reuses the application's real agent loop, tool schemas, system
prompts, and Tectonic compile** from `../backend`, so the experiment measures the real agent — only
the model varies.

```
data/       assemble the QLoRA training set from public datasets
finetune/   QLoRA SFT of Qwen3-8B (TRL + PEFT + bitsandbytes) + merge + GGUF
serving/    serve each Qwen variant with vLLM (OpenAI-compatible + tool calling)
eval/       the evaluation suite: run all 5 models, emit the comparison tables
```

There are two independent environments; set them up separately.

---

## A. Evaluation environment (no GPU required)

The evaluation runs against API or served models and needs no GPU. It imports the backend (for the
real agent loop + Tectonic) plus a few extra dependencies.

```bash
python -m venv .venv-eval && . .venv-eval/bin/activate    # Windows: .venv-eval\Scripts\activate
pip install -r requirements-eval.txt
pip install -e ../backend          # makes `app.*` importable
```

Two API keys are required — the agent under test calls OpenAI, and the DeepEval judge calls Claude.
Both are read from environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). The simplest way
to provide them is a `research/.env` file, which the suite loads automatically (it is gitignored):

```bash
cp .env.example .env        # then edit .env and fill in the two keys
```

Plain environment variables also work and take precedence over `.env`:

```bash
export OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-...   # bash
$env:OPENAI_API_KEY="sk-..."; $env:ANTHROPIC_API_KEY="sk-ant-..."   # PowerShell
```

> **Tectonic** must be on PATH to score the LaTeX category (it is the same engine the backend
> uses). If it is missing, the suite still runs and the `compile_rate` column shows `n/a`.

### 1. Build the frozen evaluation set (80 tasks, from validation splits — no leakage)

```bash
cd <repo>/research
python -m eval.tasks.build_eval_set            # pulls validation splits (needs network)
python -m eval.tasks.build_eval_set --check    # offline structural check of an existing set
```

This is a one-time step that writes `eval/tasks/eval_set.jsonl`; the suite itself only reads that
file.

### 2. Verify the harness offline (no API spend)

```bash
python -m eval.run_eval --dry-run --tasks eval/tasks/eval_set.jsonl
```

Canned answers run through the deterministic scorers (tool-use, Tectonic) to confirm wiring.

### 3. Run the API models

These can run before any fine-tuning has happened:

```bash
python -m eval.run_eval --model gpt-4.1-mini
python -m eval.run_eval --model gpt-5.4-mini
```

Each run writes `eval/results/<model>.json` and rebuilds `eval/results/results_table.md` and
`deployability.md`. The model is selected in one place: the `--model` flag, or the `ACTIVE`
constant in [eval/models.py](eval/models.py).

### 4. Run the Qwen variants (after fine-tuning + serving)

Start the matching vLLM/Ollama server (see [serving/serve_vllm.md](serving/serve_vllm.md)), one
variant at a time on `:8000`, then:

```bash
python -m eval.run_eval --model qwen3-8b-base
python -m eval.run_eval --model qwen3-8b-sft
python -m eval.run_eval --model qwen3-8b-sft-q4
```

A sample of ~15 judge scores should be hand-verified to validate the judge. The generated tables
are the final output of the suite.

---

## B. Fine-tuning environment (cloud GPU ≥32 GB)

```bash
python -m venv .venv-finetune && . .venv-finetune/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu121   # match the box's CUDA
pip install -r requirements-finetune.txt
```

### 1. Build the training set

```bash
python -m data.build_dataset --selftest          # offline: validate the converters
python -m data.build_dataset --total 16000       # full build -> data/out/{train,val}.jsonl
```

### 2. QLoRA SFT

```bash
cd finetune
python train_qlora.py --config config.yaml --smoke   # 100 rows / 10 steps sanity run
python train_qlora.py --config config.yaml           # full run
python merge.py --config config.yaml                 # adapter -> merged fp16 (model #4)
```

### 3. Quantize to GGUF (model #5)

Follow [finetune/to_gguf.md](finetune/to_gguf.md) (llama.cpp convert + `q4_K_M`).

---

## The evaluation suite (what is measured)

80 tasks, 20 each: **lookup · synthesis · abstention · latex**.

| Metric | Tasks | How |
|---|---|---|
| Tool-use accuracy (appropriate tool + JSON-arg validity) | 80 | code — [eval/scorers/tool_use.py](eval/scorers/tool_use.py) |
| Grounding: faithfulness | 40 | DeepEval `FaithfulnessMetric` (Claude judge) |
| Citation accuracy | 40 | DeepEval `GEval` |
| Abstention (refuse-on-unanswerable / answer-on-control) | 20 | DeepEval `GEval` |
| LaTeX compile-rate | 20 | code — real Tectonic compile |
| Answer quality (1–5 vs gold) | 40 | DeepEval `GEval` |
| Deployability (tokens/s, TTFT, on-disk size) | local | code |

The judge is **Claude Sonnet 4.6**, blind to model identity. All models run at decoding temperature
`0` (deterministic, reproducible single-run results, matching the deployed agent; override via the
`EVAL_TEMPERATURE` environment variable), with identical prompts and tools, in a single run.

## Design choices

- **The evaluation reuses the production loop.** `run_agent` in `../backend/app/agent/ask.py`
  exposes a shared `_run_tool_loop` helper; the evaluation injects bundled-context tools into that
  same loop, so the agent under test is the real one.
- **Retrieval is held constant.** The evaluation's `search_sources`/`search_draft` use **BM25** over
  each task's bundled chunks — deterministic, offline, and identical across models. For a *model*
  comparison, retrieval only needs to be the same for every model; it is not the variable under
  test.
- **The LaTeX training slice is synthetic.** The 5% LaTeX slice is generated as `write_file`/
  `edit_file` trajectories (peS2o is cleaned prose, not LaTeX source; synthetic edits directly teach
  the agentic editing the evaluation scores). Every other slice is public data, remapped to
  Evidentia's tool schema.
- **No train/test leakage.** Training uses each dataset's `train` split; the evaluation set uses the
  `validation` split.
