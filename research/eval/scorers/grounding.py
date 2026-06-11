"""Grounding scorers (DeepEval, Claude judge): faithfulness + citation accuracy.

  - faithfulness: DeepEval's FaithfulnessMetric — are the answer's claims entailed by the context
    the model was given (the task's source chunks)?
  - citation:     a GEval criterion — are the answer's [n] citation markers actually supported by
    that context, and does it avoid citing unsupported claims?

Both scored only on lookup + synthesis tasks (where a grounded, cited answer is expected).
"""

from __future__ import annotations


def _context(task: dict) -> list[str]:
    chunks: list[str] = []
    for src in task.get("sources", []):
        for c in src.get("chunks", []):
            chunks.append(f"[{src['filename']}] {c['text']}")
    return chunks or ["(no sources)"]


def score_grounding(task: dict, result, judge) -> dict:
    from deepeval.metrics import FaithfulnessMetric, GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    answer = result.content or "(no answer)"
    tc = LLMTestCase(
        input=task["question"],
        actual_output=answer,
        retrieval_context=_context(task),
    )

    faithfulness = FaithfulnessMetric(model=judge, threshold=0.5, include_reason=False, async_mode=False)
    citation = GEval(
        name="CitationAccuracy",
        criteria=(
            "Evaluate whether the bracketed [n] citation markers in the actual output are justified "
            "by the retrieval context. Score high only if every cited claim is supported by the "
            "context and the answer does not attach citations to unsupported claims. An answer with "
            "no citations but also no factual claims may score moderately."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        model=judge,
        threshold=0.5,
        async_mode=False,
    )

    out: dict = {}
    for key, metric in (("faithfulness", faithfulness), ("citation", citation)):
        try:
            metric.measure(tc)
            out[key] = float(metric.score)
        except Exception as exc:  # noqa: BLE001
            out[key] = None
            out[f"{key}_error"] = str(exc)
    return out
