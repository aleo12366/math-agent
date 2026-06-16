"""Context Builder — main Guard Layer entry point that ties all modules together."""

from __future__ import annotations

import uuid
from typing import Any

from .normalizer import normalize_problem, build_constraint_graph
from .complexity import estimate_risk
from .type_matcher import hybrid_classify
from .precompute import local_precompute
from .router import CalibratedRouter


_router = CalibratedRouter()


def build_presolve_context(raw_problem: str) -> dict[str, Any]:
    """Build a PreSolveContext from a raw problem string.

    This is the single entry point for the Guard Layer. It runs the full
    zero-LLM local preprocessing pipeline:

        normalize_problem → build_constraint_graph → hybrid_classify →
        estimate_risk → local_precompute → CalibratedRouter.predict

    Args:
        raw_problem: The raw problem text (may contain LaTeX, unicode, etc.).

    Returns:
        A PreSolveContext dict with keys:
            problem_id: str (UUID)
            raw_problem: str
            normalized: dict (from normalize_problem)
            constraint_graph: dict (from build_constraint_graph)
            risk: dict (from estimate_risk)
            classification: dict (from hybrid_classify)
            precompute: dict (from local_precompute)
            fusion: dict (from CalibratedRouter.predict)
    """
    normalized = normalize_problem(raw_problem)
    constraint_graph = build_constraint_graph(normalized)
    risk = estimate_risk(normalized, constraint_graph)
    classification = hybrid_classify(
        normalized["clean_text"],
        normalized.get("symbols"),
        constraint_graph,
    )
    precompute = local_precompute(constraint_graph, classification)

    fusion = _router.predict({
        "type_confidence": classification.get("confidence", 0.0),
        "complexity_score": risk.get("complexity_score", 0.0),
        "retrieval_score": 0.0,
        "tool_success": 0.0,
    })

    return {
        "problem_id": str(uuid.uuid4()),
        "raw_problem": raw_problem,
        "normalized": normalized,
        "constraint_graph": constraint_graph,
        "risk": risk,
        "classification": classification,
        "retrieval": None,
        "precompute": precompute,
        "fusion": fusion,
    }
