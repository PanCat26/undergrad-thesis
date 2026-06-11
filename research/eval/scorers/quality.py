"""Answer-quality scorer (DeepEval GEval, Claude judge) — 1-5 vs the gold answer.

Judges the response against the task's gold answer on correctness + grounding + completeness,
blind to which model produced it. GEval returns 0-1; we report both the raw score and the 1-5
scale the thesis tables use. Scored on lookup + synthesis tasks.
"""

from __future__ import annotations


def score_quality(task: dict, result, judge) -> dict:
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    metric = GEval(
        name="AnswerQuality",
        criteria=(
            "Judge the actual output against the expected (gold) answer for the question. Reward "
            "factual correctness, faithful use of the provided sources, and completeness; penalize "
            "hallucinated or unsupported claims and missing key points. Do not reward verbosity."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        model=judge,
        threshold=0.5,
        async_mode=False,
    )
    tc = LLMTestCase(
        input=task["question"],
        actual_output=result.content or "(no answer)",
        expected_output=task.get("gold_answer", ""),
    )
    try:
        metric.measure(tc)
        raw = float(metric.score)
        return {"raw": raw, "score_1_5": round(1 + 4 * raw, 2)}
    except Exception as exc:  # noqa: BLE001
        return {"raw": None, "score_1_5": None, "error": str(exc)}
