"""Deterministic tool-use scoring — no judge.

Two sub-metrics per task:
  - appropriate: did the model call at least one of the task's expected tool(s)?
  - arg_valid:   fraction of the model's tool calls whose JSON args satisfy Evidentia's schema
                 (all required args present, no unexpected args).
"""

from __future__ import annotations

from data.schema import allowed_args, required_args


def _call_valid(name: str, args: dict) -> bool:
    if not isinstance(args, dict):
        return False
    if any(a not in args for a in required_args(name)):
        return False
    allowed = allowed_args(name)
    if allowed and any(a not in allowed for a in args):
        return False
    return True


def score_tool_use(task: dict, result) -> dict:
    expected = set(task.get("expected_tools", []))
    trace = result.tool_trace
    called = {c["name"] for c in trace}

    appropriate = (not expected) or bool(expected & called)
    if trace:
        valid = sum(_call_valid(c["name"], c.get("args", {})) for c in trace)
        arg_valid = valid / len(trace)
    else:
        # No calls: vacuously valid on args, but `appropriate` already flags the miss.
        arg_valid = 1.0

    return {
        "appropriate": appropriate,
        "arg_valid": arg_valid,
        "n_calls": len(trace),
        "called": sorted(called),
    }
