"""Model registry — the ONE place to switch which model the eval runs against.

Each entry is an OpenAI-compatible endpoint (the app's agent talks OpenAI protocol to all of them):
the two GPT models via the OpenAI API, the three Qwen variants via a local vLLM/Ollama server.
The eval is server-agnostic — only `model` + `base_url` + `api_key` matter here.

Run a specific model:   python -m eval.run_eval --model gpt-4.1-mini
Default (no --model):   ACTIVE below.

GPT models run NOW (set OPENAI_API_KEY). The Qwen entries point at http://localhost:8000/v1 —
start the matching vLLM server first (see ../serving/serve_vllm.md), one variant at a time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_LOCAL_BASE = os.environ.get("EVAL_LOCAL_BASE_URL", "http://localhost:8000/v1")
_OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
# Default 0 = deterministic, reproducible single-run results, and matches the deployed agent
# (ask.py builds the chat model at temperature 0). Override via EVAL_TEMPERATURE for experiments.
_TEMPERATURE = float(os.environ.get("EVAL_TEMPERATURE", "0"))


@dataclass(frozen=True)
class ModelSpec:
    name: str          # label used in result files/tables
    model: str         # model id sent to the endpoint
    base_url: str | None
    api_key: str
    temperature: float = _TEMPERATURE
    is_local: bool = False


REGISTRY: dict[str, ModelSpec] = {
    # --- API models (run now) ---
    "gpt-4.1-mini": ModelSpec("gpt-4.1-mini", "gpt-4.1-mini", None, _OPENAI_KEY),
    "gpt-5.4-mini": ModelSpec("gpt-5.4-mini", "gpt-5.4-mini", None, _OPENAI_KEY),
    # --- Local Qwen variants (served by vLLM/Ollama, one at a time on _LOCAL_BASE) ---
    "qwen3-8b-base": ModelSpec("qwen3-8b-base", "qwen3-8b-base", _LOCAL_BASE, "not-needed", is_local=True),
    "qwen3-8b-sft": ModelSpec("qwen3-8b-sft", "qwen3-8b-sft", _LOCAL_BASE, "not-needed", is_local=True),
    "qwen3-8b-sft-q4": ModelSpec("qwen3-8b-sft-q4", "qwen3-8b-sft-q4", _LOCAL_BASE, "not-needed", is_local=True),
}

# The 5 models of the thesis comparison, in table order.
COMPARISON = ["gpt-4.1-mini", "gpt-5.4-mini", "qwen3-8b-base", "qwen3-8b-sft", "qwen3-8b-sft-q4"]

# Default when --model is omitted.
ACTIVE = "gpt-4.1-mini"


def get(name: str | None) -> ModelSpec:
    spec = REGISTRY.get(name or ACTIVE)
    if spec is None:
        raise SystemExit(f"Unknown model '{name}'. Choices: {', '.join(REGISTRY)}")
    return spec
