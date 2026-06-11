"""Shared DeepEval judge — Claude Sonnet 4.6, blind to which model produced the answer.

One ``AnthropicModel`` instance is reused by every judge-based metric (grounding, abstention,
quality). Reads ANTHROPIC_API_KEY from the environment. Model id is ``claude-sonnet-4-6`` exactly
(no date suffix), per the user's choice of judge.
"""

from __future__ import annotations

import functools

JUDGE_MODEL = "claude-sonnet-4-6"


@functools.lru_cache(maxsize=1)
def get_judge():
    """Return the shared DeepEval Claude judge (lazy import so non-judge runs don't need deepeval)."""
    from deepeval.models import AnthropicModel

    # temperature defaults to 0 in DeepEval's AnthropicModel — deterministic judging.
    return AnthropicModel(model=JUDGE_MODEL)
