"""QLoRA SFT for Qwen3-8B on the Evidentia training mix (TRL SFTTrainer + PEFT + bitsandbytes).

Runs on a single cloud GPU (>=32 GB). The dataset is the chat-format jsonl from
`data/build_dataset.py` (`{"messages", "tools"}` per row); TRL applies Qwen3's chat template,
so tool definitions and tool-call turns are rendered correctly for tool-use training.

  # one-time:  pip install -r ../requirements-finetune.txt   (CUDA torch first, see README)
  python train_qlora.py --config config.yaml                 # full run
  python train_qlora.py --config config.yaml --smoke         # 100 rows / 10 steps sanity run

After training, merge the adapter for serving:  python merge.py --config config.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--smoke", action="store_true", help="tiny run to validate the pipeline")
    # Common overrides (anything here wins over the YAML).
    ap.add_argument("--num-train-epochs", type=float, default=None)
    ap.add_argument("--learning-rate", type=float, default=None)
    ap.add_argument("--output-dir", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    # Heavy imports are deferred so `--help` and import-time errors stay cheap.
    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    m, q, lora, tr = cfg["model"], cfg["quantization"], cfg["lora"], cfg["training"]
    if args.num_train_epochs is not None:
        tr["num_train_epochs"] = args.num_train_epochs
    if args.learning_rate is not None:
        tr["learning_rate"] = args.learning_rate
    output_dir = args.output_dir or tr["output_dir"]

    # ---- tokenizer + 4-bit base model -------------------------------------------------
    tokenizer = AutoTokenizer.from_pretrained(m["base_model"], trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=q["load_in_4bit"],
        bnb_4bit_quant_type=q["bnb_4bit_quant_type"],
        bnb_4bit_use_double_quant=q["bnb_4bit_use_double_quant"],
        bnb_4bit_compute_dtype=getattr(torch, q["bnb_4bit_compute_dtype"]),
    )
    attn = m.get("attn_implementation", "sdpa")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            m["base_model"],
            quantization_config=bnb,
            torch_dtype=torch.bfloat16,
            attn_implementation=attn,
            trust_remote_code=True,
        )
    except (ImportError, ValueError):  # flash-attn not installed on this box
        print(f"attn_implementation={attn!r} unavailable; falling back to 'sdpa'")
        model = AutoModelForCausalLM.from_pretrained(
            m["base_model"],
            quantization_config=bnb,
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa",
            trust_remote_code=True,
        )
    model.config.use_cache = False

    peft_config = LoraConfig(
        r=lora["r"],
        lora_alpha=lora["alpha"],
        lora_dropout=lora["dropout"],
        target_modules=lora["target_modules"],
        bias="none",
        task_type="CAUSAL_LM",
    )

    # ---- data --------------------------------------------------------------------------
    data_files = {"train": cfg["data"]["train_file"], "validation": cfg["data"]["val_file"]}
    ds = load_dataset("json", data_files=data_files)
    if args.smoke:
        ds["train"] = ds["train"].select(range(min(100, len(ds["train"]))))
        ds["validation"] = ds["validation"].select(range(min(20, len(ds["validation"]))))
        tr["save_steps"], tr["eval_steps"], tr["logging_steps"] = 5, 5, 1

    # TRL renders {"messages","tools"} with the model's chat template. Drop the bookkeeping field.
    keep = {"messages", "tools"}
    ds = ds.map(lambda r: {k: r[k] for k in keep if k in r}, remove_columns=ds["train"].column_names)

    sft_config = SFTConfig(
        output_dir=output_dir,
        max_length=m["max_seq_len"],  # renamed from max_seq_length in recent TRL
        num_train_epochs=1 if args.smoke else tr["num_train_epochs"],
        max_steps=10 if args.smoke else -1,
        per_device_train_batch_size=tr["per_device_train_batch_size"],
        gradient_accumulation_steps=tr["gradient_accumulation_steps"],
        learning_rate=tr["learning_rate"],
        lr_scheduler_type=tr["lr_scheduler_type"],
        warmup_ratio=tr["warmup_ratio"],
        weight_decay=tr["weight_decay"],
        bf16=tr["bf16"],
        gradient_checkpointing=tr["gradient_checkpointing"],
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=tr["logging_steps"],
        eval_strategy=tr["eval_strategy"],
        eval_steps=tr["eval_steps"],
        save_strategy=tr["save_strategy"],
        save_steps=tr["save_steps"],
        save_total_limit=tr["save_total_limit"],
        seed=tr["seed"],
        report_to=tr["report_to"],
        packing=False,  # keep tool-call turns intact; don't pack across examples
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"],
        peft_config=peft_config,
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    Path(output_dir, "DONE").write_text("training complete\n", encoding="utf-8")
    print(f"\nAdapter saved to {output_dir}. Next: python merge.py --config {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
