# Quantize the merged model to 4-bit GGUF (model #5)

This produces the **q4_K_M GGUF** that is both the headline "ships to users" artifact and eval
model #5 (`qwen3-8b-sft-q4`). It runs on the merged fp16 directory from `merge.py`.

## Prerequisites
- A completed merge: `./merged/qwen3-8b-evidentia/` (from `python merge.py`).
- [`llama.cpp`](https://github.com/ggml-org/llama.cpp) checked out and built.

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
pip install -r requirements.txt        # for the convert script
cmake -B build && cmake --build build --config Release -j   # builds llama-quantize
```

## 1. Convert HF -> GGUF (fp16)
```bash
python llama.cpp/convert_hf_to_gguf.py \
  ./merged/qwen3-8b-evidentia \
  --outfile ./merged/qwen3-8b-evidentia-f16.gguf \
  --outtype f16
```

## 2. Quantize to q4_K_M (the shipped/eval variant)
```bash
./llama.cpp/build/bin/llama-quantize \
  ./merged/qwen3-8b-evidentia-f16.gguf \
  ./merged/qwen3-8b-evidentia-q4_K_M.gguf \
  Q4_K_M
```

## 3. (Optional) the ablation points
For the quantization-impact sentence in the thesis, also produce `Q5_K_M` and `Q8_0`:
```bash
for q in Q5_K_M Q8_0; do
  ./llama.cpp/build/bin/llama-quantize \
    ./merged/qwen3-8b-evidentia-f16.gguf \
    ./merged/qwen3-8b-evidentia-${q}.gguf "$q"
done
```

## 4. Record the deployability numbers
`ls -la *.gguf` gives the **on-disk size** column. Tokens/sec + TTFT come from the eval runner
once the model is served (see `../serving/serve_vllm.md` — vLLM serves GGUF, or use Ollama for the
end-user delivery path).

> Note: vLLM's GGUF support for Qwen3 can lag llama.cpp. If vLLM refuses the GGUF, serve model #5
> with **Ollama** instead (`ollama create`), and point the eval at the Ollama OpenAI endpoint —
> the eval is server-agnostic, so only `base_url`/`model` in `eval/models.py` change.
