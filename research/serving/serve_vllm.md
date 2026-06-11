# Serving the Qwen variants (one tool: vLLM, OpenAI-compatible + tool calling)

All three local models (#3 base, #4 merged-SFT, #5 q4 GGUF) are served by **vLLM** behind an
OpenAI-compatible API with **tool calling enabled**, so Evidentia's agent loop talks to them
unchanged. The eval is server-agnostic — it only needs `{model, base_url, api_key}` in
`eval/models.py`. Serve **one variant at a time** on `:8000`, run the eval, then swap.

```bash
pip install vllm
```

Qwen3 uses the **hermes** tool-call parser. The flags that matter for this project:
`--enable-auto-tool-choice --tool-call-parser hermes`.

## #3 — Qwen3-8B base (no fine-tune)
```bash
vllm serve Qwen/Qwen3-8B \
  --served-model-name qwen3-8b-base \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --max-model-len 8192 --port 8000
```

## #4 — Qwen3-8B SFT (merged)
```bash
vllm serve ./finetune/merged/qwen3-8b-evidentia \
  --served-model-name qwen3-8b-sft \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --max-model-len 8192 --port 8000
```

## #5 — Qwen3-8B SFT + q4_K_M GGUF
```bash
vllm serve ./finetune/merged/qwen3-8b-evidentia-q4_K_M.gguf \
  --served-model-name qwen3-8b-sft-q4 \
  --tokenizer ./finetune/merged/qwen3-8b-evidentia \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --max-model-len 8192 --port 8000
```

> If vLLM rejects the Qwen3 GGUF (support can lag llama.cpp), serve #5 with **Ollama**:
> ```bash
> ollama create qwen3-8b-sft-q4 -f Modelfile      # FROM ./...-q4_K_M.gguf
> ollama serve                                    # OpenAI API at http://localhost:11434/v1
> ```
> Then set that `base_url`/`model` in `eval/models.py`. Ollama is also the recommended
> **end-user delivery** path for the shipped model.

## Point the eval at a served model
In `eval/models.py`, the local entries use `base_url="http://localhost:8000/v1"` and
`api_key="not-needed"`. Switch `ACTIVE` (or pass `--model`) to the variant currently being served:

```bash
cd ..    # research/
python -m eval.run_eval --model qwen3-8b-sft
```

## Sanity check a served endpoint
```bash
curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "qwen3-8b-base",
  "messages": [{"role":"user","content":"Say hi in 3 words."}]
}'
```
