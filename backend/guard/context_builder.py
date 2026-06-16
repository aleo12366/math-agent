"""Context Builder — main Guard Layer entry point that ties all modules together."""

from __future__ import annotations

import uuid
from typing import Any

from .normalizer import normalize_problem, build_constraint_graph
from .complexity import estimate_risk
from .type_matcher import hybrid_classify
from .precompute import local_precompute
from .router import CalibratedRouter
from .retriever import retrieve_similar


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

    # Initial retrieval estimate for router confidence
    similar_cases = retrieve_similar(raw_problem, route="standard", top_k=5)
    retrieval_score = 0.5 if similar_cases else 0.0

    # Calculate tool_success from precompute results
    tool_success = 0.0
    if precompute.get("symbolic_candidates"):
        tool_success = 1.0
    elif precompute.get("numeric_sanity", {}).get("has_target"):
        tool_success = 0.5

    fusion = _router.predict({
        "type_confidence": classification.get("confidence", 0.0),
        "complexity_score": risk.get("complexity_score", 0.0),
        "retrieval_score": retrieval_score,
        "tool_success": tool_success,
    })

    # Apply evidence budget: re-filter results for the selected route
    route = fusion.get("route", "standard")
    budget = retrieve_similar.__defaults__  # not reliable, use EVIDENCE_BUDGET directly
    from .retriever import EVIDENCE_BUDGET
    max_cases = EVIDENCE_BUDGET.get(route, EVIDENCE_BUDGET["standard"])["similar_cases"]
    budgeted_cases = similar_cases[:max_cases]

    return {
        "problem_id": str(uuid.uuid4()),
        "raw_problem": raw_problem,
        "normalized": normalized,
        "constraint_graph": constraint_graph,
        "risk": risk,
        "classification": classification,
        "retrieval": {
            "similar_cases": budgeted_cases,
            "method_templates": [],
        },
        "precompute": precompute,
        "fusion": fusion,
    }
