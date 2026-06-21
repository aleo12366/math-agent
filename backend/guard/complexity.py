"""Complexity & Risk Estimator — zero-LLM risk assessment for math problems."""

from __future__ import annotations

from typing import Any

_SCORE_MAP: dict[str, float] = {
    "has_pde": 0.20,
    "has_proof": 0.20,
    "many_variables": 0.10,
    "requires_case_split": 0.15,
    "requires_tool": 0.10,
    "unclear_target": 0.15,
    "no_constraints": 0.10,
    "uncertain_answer_shape": 0.10,
    "advanced_topic": 0.15,
    "series_form": 0.15,
    "optimization": 0.10,
}

_ADVANCED_KEYWORDS = {
    "偏微分方程", "偏微分", "PDE", "pde",
    "特征值", "特征向量", "eigenvalue", "eigenvector",
    "傅里叶", "fourier", "拉普拉斯", "laplace",
    "泛函", "functional", "测度", "measure",
    "拓扑", "topology", "流形", "manifold",
    "微分几何", "differential geometry",
    "随机过程", "stochastic", "markov",
}


def estimate_risk(norm: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    """Estimate complexity and risk for a normalized math problem.

    Args:
        norm: Output of normalize_problem().
        graph: Output of build_constraint_graph().

    Returns:
        dict with keys:
            complexity_score: float 0.0-1.0
            risk_tags: list[str]
            needs_tool: bool
            needs_verifier: bool
            answer_shape_certainty: float 0.0-1.0
    """
    risk_tags: list[str] = []
    score = 0.0

    if graph.get("has_pde"):
        score += _SCORE_MAP["has_pde"]
        risk_tags.append("has_pde")
        if graph.get("boundary_constraints") or graph.get("initial_constraints"):
            score += 0.20
            risk_tags.append("pde_with_constraints")

    if graph.get("has_proof"):
        score += _SCORE_MAP["has_proof"]
        risk_tags.append("has_proof")

    variables = graph.get("variables", [])
    if len(variables) > 4:
        score += _SCORE_MAP["many_variables"]
        risk_tags.append("many_variables")

    if graph.get("requires_case_split"):
        score += _SCORE_MAP["requires_case_split"]
        risk_tags.append("requires_case_split")

    if graph.get("requires_tool"):
        score += _SCORE_MAP["requires_tool"]
        risk_tags.append("requires_tool")

    if not graph.get("target"):
        score += _SCORE_MAP["unclear_target"]
        risk_tags.append("unclear_target")

    has_equality = bool(graph.get("equality_constraints"))
    has_inequality = bool(graph.get("inequality_constraints"))
    has_boundary = bool(graph.get("boundary_constraints"))
    has_initial = bool(graph.get("initial_constraints"))
    if not any([has_equality, has_inequality, has_boundary, has_initial]):
        score += _SCORE_MAP["no_constraints"]
        risk_tags.append("no_constraints")

    answer_shape = graph.get("answer_shape", "expression")
    if answer_shape in ("proof", "set", "matrix"):
        score += _SCORE_MAP["uncertain_answer_shape"]
        risk_tags.append("uncertain_answer_form")

    text = norm.get("clean_text", "")
    lower = text.lower()
    if any(kw in lower or kw in text for kw in _ADVANCED_KEYWORDS):
        score += _SCORE_MAP["advanced_topic"]
        risk_tags.append("advanced_topic")

    # series_form: 级数问题
    if "级数" in text or "series" in lower or "∑" in text:
        score += _SCORE_MAP["series_form"]
        risk_tags.append("series_form")

    # optimization: 最优化问题
    if any(kw in text for kw in ("最大", "最小", "极值", "最值")) or \
       any(kw in lower for kw in ("max", "min", "optimize", "extremum")):
        score += _SCORE_MAP["optimization"]
        risk_tags.append("optimization")

    complexity_score = min(score, 1.0)

    needs_tool = graph.get("requires_tool", False) or complexity_score > 0.5
    needs_verifier = complexity_score > 0.3

    certainty = 1.0
    if not graph.get("target"):
        certainty -= 0.3
    if answer_shape in ("proof", "set", "matrix"):
        certainty -= 0.2
    answer_shape_certainty = max(certainty, 0.0)

    return {
        "complexity_score": round(complexity_score, 4),
        "risk_tags": risk_tags,
        "needs_tool": needs_tool,
        "needs_verifier": needs_verifier,
        "answer_shape_certainty": round(answer_shape_certainty, 4),
    }
