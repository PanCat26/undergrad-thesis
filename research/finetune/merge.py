"""Merge the QLoRA adapter into the base Qwen3-8B weights, producing a standalone fp16 model
directory that vLLM can serve directly (model #4 in the comparison).

  python merge.py --config config.yaml
  python merge.py --adapter ./outputs/qwen3-8b-evidentia-qlora --out ./merged/qwen3-8b-evidentia

The merged model also feeds the GGUF quantization step (see to_gguf.md) for model #5.
"""

from __future__ import annotations

import argparse

import yaml


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--adapter", default=None, help="adapter dir (defaults to training output_dir)")
    ap.add_argument("--out", default="./merged/qwen3-8b-evidentia", help="merged output dir")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    base_model = cfg["model"]["base_model"]
    adapter = args.adapter or cfg["training"]["output_dir"]

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading base {base_model} in bf16 (full precision, not 4-bit, for a clean merge)...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.bfloat16, trust_remote_code=True
    )
    print(f"Applying adapter from {adapter}...")
    model = PeftModel.from_pretrained(model, adapter)
    model = model.merge_and_unload()

    model.save_pretrained(args.out, safe_serialization=True)
    AutoTokenizer.from_pretrained(adapter, trust_remote_code=True).save_pretrained(args.out)
    print(f"\nMerged model written to {args.out}")
    print("Serve it with vLLM (see ../serving/serve_vllm.md), or convert to GGUF (see to_gguf.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
