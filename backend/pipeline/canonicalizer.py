"""Answer Canonicalizer — normalize and compare mathematical answers."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

try:
    import sympy
    from sympy import simplify, sympify, Eq
    from sympy.parsing.latex import parse_latex
    HAS_SYMPY = True
except ImportError:
    HAS_SYMPY = False


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def _strip_latex_wrappers(s: str) -> str:
    s = re.sub(r"^\$+", "", s)
    s = re.sub(r"\$+$", "", s)
    s = re.sub(r"^\\[(\[]", "", s)
    s = re.sub(r"\\[)\]]$", "", s)
    return s.strip()


def _normalize_latex_operators(s: str) -> str:
    s = s.replace(r"\times", "*").replace(r"\cdot", "*")
    s = s.replace(r"\div", "/")
    s = s.replace(r"\pm", "+/-").replace(r"\mp", "-/+")
    s = s.replace(r"\leq", "<=").replace(r"\geq", ">=")
    s = s.replace(r"\neq", "!=")
    s = s.replace(r"\left", "").replace(r"\right", "")
    return s


def _normalize_number(s: str) -> str:
    s = s.strip()
    s = s.rstrip("0").rstrip(".") if "." in s else s
    s = s.lstrip("0") or "0"
    return s


def _make_comparison_key(answer: str, answer_type: str) -> str:
    a = _normalize_whitespace(answer)
    a = _strip_latex_wrappers(a)
    a = _normalize_latex_operators(a)
    a = a.lower()
    a = re.sub(r"[\s,]+", "", a)
    return a


def _sympy_equivalent(a1: str, a2: str) -> bool | None:
    if not HAS_SYMPY:
        return None
    try:
        expr1 = parse_latex(a1) if "\\" in a1 else sympify(a1)
        expr2 = parse_latex(a2) if "\\" in a2 else sympify(a2)
        diff = simplify(expr1 - expr2)
        return diff == 0
    except Exception:
        return None


def _build_equivalent_forms(answer: str, answer_type: str) -> list[str]:
    forms = [answer]
    cleaned = _normalize_whitespace(answer)
    if cleaned != answer:
        forms.append(cleaned)
    no_latex = _normalize_latex_operators(_strip_latex_wrappers(cleaned))
    if no_latex not in forms:
        forms.append(no_latex)
    return forms


def canonicalize_answer(answer: str, answer_type: str = "expression") -> dict[str, Any]:
    """Canonicalize a mathematical answer for comparison.

    Args:
        answer: Raw answer string (may contain LaTeX).
        answer_type: One of "number", "expression", "equation", "set", "proof", etc.

    Returns:
        Dict with keys: canonical_answer, equivalent_forms, comparison_key.
    """
    comparison_key = _make_comparison_key(answer, answer_type)
    equivalent_forms = _build_equivalent_forms(answer, answer_type)
    canonical = equivalent_forms[-1] if equivalent_forms else answer

    return {
        "canonical_answer": canonical,
        "equivalent_forms": equivalent_forms,
        "comparison_key": comparison_key,
    }


def answers_match(answer1: str, answer2: str, answer_type: str = "expression") -> bool:
    """Check if two mathematical answers are equivalent.

    Uses exact key comparison first, then SymPy simplification if available.

    Args:
        answer1: First answer string.
        answer2: Second answer string.
        answer_type: Type hint for comparison strategy.

    Returns:
        True if answers are equivalent.
    """
    key1 = _make_comparison_key(answer1, answer_type)
    key2 = _make_comparison_key(answer2, answer_type)

    if key1 == key2:
        return True

    sympy_result = _sympy_equivalent(answer1, answer2)
    if sympy_result is not None:
        return sympy_result

    return False
