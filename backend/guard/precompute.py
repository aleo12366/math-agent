"""Local Precompute — symbolic candidates, numeric sanity, verification hooks."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

try:
    import sympy
    from sympy import symbols, solve, integrate, diff, simplify, Eq, oo
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
    _SYMPY_AVAILABLE = True
except ImportError:
    _SYMPY_AVAILABLE = False


def _safe_parse(expr_str: str, local_dict: dict | None = None):
    """Parse a string into a SymPy expression, returning None on failure."""
    if not _SYMPY_AVAILABLE:
        return None
    try:
        transformations = standard_transformations + (implicit_multiplication_application,)
        return parse_expr(expr_str, local_dict=local_dict or {}, transformations=transformations)
    except Exception:
        return None


def _extract_simple_equation(text: str) -> tuple[str | None, str | None]:
    """Try to extract a simple 'LHS = RHS' from text. Returns (lhs, rhs) or (None, None)."""
    m = re.search(r"([a-zA-Z0-9_+\-*/^().\s]+?)\s*=\s*([a-zA-Z0-9_+\-*/^().\s]+)", text)
    if m:
        lhs = m.group(1).strip()
        rhs = m.group(2).strip()
        if lhs and rhs:
            return lhs, rhs
    return None, None


def _extract_integral(text: str) -> tuple[str | None, str | None, str | None]:
    """Try to extract integral expression. Returns (integrand, var, limits_str) or (None, None, None)."""
    m = re.search(r"∫\s*([^\s∫]+)\s*d([a-zA-Z])", text)
    if m:
        return m.group(1), m.group(2), None
    m = re.search(r"integral\s+of\s+(.+?)\s+d([a-zA-Z])", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(), m.group(2), None
    m = re.search(r"int(?:_([^\s]+))?\^(?:\{([^}]+)\}|([^\s{]+))\s+(.+?)\s+d([a-zA-Z])", text)
    if m:
        lower = m.group(1) or m.group(2) or m.group(3)
        integrand = m.group(4).strip()
        var = m.group(5)
        return integrand, var, lower
    return None, None, None


def _precompute_calculus(text: str, graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Try SymPy integration/differentiation/equation solving for calculus problems."""
    candidates: list[dict[str, Any]] = []

    integrand, var_name, _limits = _extract_integral(text)
    if integrand and var_name and _SYMPY_AVAILABLE:
            try:
                x = symbols(var_name)
                expr = _safe_parse(integrand, local_dict={var_name: x})
                if expr is not None:
                    result = integrate(expr, x)
                    candidates.append({
                        "type": "indefinite_integral",
                        "expr": str(expr),
                        "result": str(result),
                        "var": var_name,
                    })
            except Exception as e:
                logger.debug("Precompute calculus (integral) failed: %s", e)

    lhs_str, rhs_str = _extract_simple_equation(text)
    if lhs_str and rhs_str and _SYMPY_AVAILABLE:
        var_names = graph.get("unknowns", []) or graph.get("variables", [])
        if var_names:
            try:
                sym_dict = {v: symbols(v) for v in var_names}
                lhs = _safe_parse(lhs_str, local_dict=sym_dict)
                rhs = _safe_parse(rhs_str, local_dict=sym_dict)
                if lhs is not None and rhs is not None:
                    solutions = solve(Eq(lhs, rhs), list(sym_dict.values()))
                    if solutions:
                        candidates.append({
                            "type": "equation_solution",
                            "equation": f"{lhs_str} = {rhs_str}",
                            "solutions": [str(s) for s in solutions],
                        })
            except Exception as e:
                logger.debug("Precompute calculus (equation) failed: %s", e)

    return candidates


def _precompute_algebra(text: str, graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Try SymPy linear equation solving for algebra problems."""
    candidates: list[dict[str, Any]] = []

    equalities = graph.get("equality_constraints", [])
    var_names = graph.get("unknowns", []) or graph.get("variables", [])

    if not equalities or not var_names or not _SYMPY_AVAILABLE:
        return candidates

    try:
        sym_dict = {v: symbols(v) for v in var_names}
        equations = []
        for eq_str in equalities:
            lhs_str, rhs_str = _extract_simple_equation(eq_str)
            if lhs_str is None:
                if "=" in eq_str:
                    parts = eq_str.split("=", 1)
                    lhs_str, rhs_str = parts[0].strip(), parts[1].strip()
                else:
                    continue
            lhs = _safe_parse(lhs_str, local_dict=sym_dict)
            rhs = _safe_parse(rhs_str, local_dict=sym_dict)
            if lhs is not None and rhs is not None:
                equations.append(Eq(lhs, rhs))

        if equations:
            syms = list(sym_dict.values())
            solutions = solve(equations, syms)
            if solutions:
                if isinstance(solutions, dict):
                    solutions = [solutions]
                candidates.append({
                    "type": "linear_system_solution",
                    "equations": equalities,
                    "solutions": [{str(k): str(v) for k, v in sol.items()} if isinstance(sol, dict) else str(sol) for sol in solutions],
                })
    except Exception as e:
        logger.debug("Precompute algebra (linear system) failed: %s", e)

    return candidates


def _numeric_sanity_check(graph: dict[str, Any]) -> dict[str, Any]:
    """Check structural completeness of the constraint graph."""
    return {
        "has_domain": bool(graph.get("domain_constraints")),
        "has_boundary": bool(graph.get("boundary_constraints")),
        "has_target": bool(graph.get("target")),
        "has_equalities": bool(graph.get("equality_constraints")),
        "has_inequalities": bool(graph.get("inequality_constraints")),
        "has_initial": bool(graph.get("initial_constraints")),
    }


def _build_verification_hooks(graph: dict[str, Any], classification: dict[str, Any]) -> list[dict[str, Any]]:
    """Build verification hooks based on graph and classification."""
    hooks: list[dict[str, Any]] = []

    if graph.get("has_proof"):
        hooks.append({"type": "proof_verifier", "domain": classification.get("domain", "未知")})

    answer_shape = graph.get("answer_shape", "expression")
    if answer_shape == "set":
        hooks.append({"type": "set_completeness_check"})
    elif answer_shape == "matrix":
        hooks.append({"type": "matrix_dimension_check"})
    elif answer_shape == "interval":
        hooks.append({"type": "interval_boundary_check"})

    if graph.get("requires_case_split"):
        hooks.append({"type": "case_exhaustiveness_check"})

    return hooks


def local_precompute(
    graph: dict[str, Any],
    classification: dict[str, Any],
    templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Local precompute: produce symbolic candidates, numeric sanity, and verification hooks.

    Args:
        graph: Constraint graph from build_constraint_graph().
        classification: Domain classification from hybrid_classify().
        templates: Template list (unused currently, reserved for future matching).

    Returns:
        dict with keys:
            symbolic_candidates: list of symbolic computation results
            numeric_sanity: structural completeness check
            verification_hooks: hooks for downstream verification
    """
    domain = classification.get("domain", "未知")
    text = graph.get("target", "") or ""
    clean_text = " ".join(graph.get("equality_constraints", []))
    combined_text = text + " " + clean_text

    symbolic_candidates: list[dict[str, Any]] = []

    if domain in ("微积分", "calculus", "微分方程", "differential equation"):
        symbolic_candidates = _precompute_calculus(combined_text, graph)
    elif domain in ("代数", "algebra", "线性代数", "linear algebra"):
        symbolic_candidates = _precompute_algebra(combined_text, graph)

    numeric_sanity = _numeric_sanity_check(graph)
    verification_hooks = _build_verification_hooks(graph, classification)

    return {
        "symbolic_candidates": symbolic_candidates,
        "numeric_sanity": numeric_sanity,
        "verification_hooks": verification_hooks,
    }
