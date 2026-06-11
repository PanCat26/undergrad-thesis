"""Eval package init.

Loads `research/.env` (if present) so OPENAI_API_KEY / ANTHROPIC_API_KEY and the optional
EVAL_* knobs are picked up automatically — no per-shell `export`/`$env:` needed. Real environment
variables still work and take precedence. Kept import-safe so the package also imports in the
fine-tuning env, where python-dotenv may not be installed.
"""

try:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # research/.env
    load_dotenv()  # also honor a .env in the current working directory / ancestors
except Exception:  # python-dotenv absent, or no .env file — env vars still work
    pass
