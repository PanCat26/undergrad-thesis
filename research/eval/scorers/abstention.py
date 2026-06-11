"""Abstention scorer (DeepEval GEval, Claude judge).

For each abstention task we know whether it is genuinely answerable from the provided sources
(`answerable`). A correct response:
  - abstains / says it lacks the information   when answerable is False (unanswerable)
  - actually answers                            when answerable is True  (control)

The judge classifies whether the response abstained; we compare that to the expectation.
A fast keyword path short-circuits obvious refusals to save judge calls.
"""

from __future__ import annotations

_ABSTAIN_HINTS = (
    "don't have enough information",
    "do not have enough information",
    "not enough information",
    "couldn't find",
    "could not find",
    "no relevant",
    "cannot answer",
    "can't answer",
    "unable to answer",
)


def _looks_abstained(text: str) -> bool | None:
    low = text.lower()
    if any(h in low for h in _ABSTAIN_HINTS):
        return True
    return None  # unclear — defer to the judge


def score_abstention(task: dict, result, judge) -> dict:
    answer = result.content or ""
    abstained = _looks_abstained(answer)

    if abstained is None:
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams

        metric = GEval(
            name="Abstention",
            criteria=(
                "Score 1 if the response declines to answer or states it lacks sufficient "
                "information in the user's sources; score 0 if it provides a substantive answer to "
                "the question."
            ),
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            model=judge,
            threshold=0.5,
            async_mode=False,
        )
        try:
            metric.measure(LLMTestCase(input=task["question"], actual_output=answer or "(empty)"))
            abstained = metric.score >= 0.5
        except Exception as exc:  # noqa: BLE001
            return {"abstained": None, "correct": None, "error": str(exc)}

    should_abstain = not task.get("answerable", True)
    return {"abstained": bool(abstained), "correct": bool(abstained) == should_abstain}
