"""Shared helpers for adaptive pipeline routes."""

from __future__ import annotations

import json as _json
import logging
import re
from typing import Any

from config.prompts import (
    ADAPTIVE_VERIFIER_SYSTEM,
    ADAPTIVE_VERIFIER_USER,
    ADAPTIVE_REFLECTION_SYSTEM,
    ADAPTIVE_REFLECTION_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)

# Mapping from adaptive verifier step labels to 6-dimension check names
_LABEL_TO_DIMENSION: dict[str, list[str]] = {
    "algebra_error": ["formula_consistency"],
    "arithmetic_error": ["dimension_check"],
    "constraint_mismatch": ["boundary_conditions"],
    "theorem_misuse": ["formula_consistency"],
    "unsupported": ["logical_consistency"],
    "incomplete": ["special_cases", "completeness"],
}


def _build_six_dim_checks(steps: list[dict], overall_valid: bool, confidence: float) -> dict[str, dict]:
    """Transform adaptive verifier step_labels into 6-dimension check format.

    Maps step-level labels (algebra_error, arithmetic_error, etc.) to the
    6 verification dimensions expected by the formatter.
    """
    # Initialize all 6 dimensions as passed with full score
    checks: dict[str, dict] = {
        name: {"passed": True, "detail": "通过", "score": 1.0}
        for name in [
            "formula_consistency",
            "boundary_conditions",
            "logical_consistency",
            "special_cases",
            "dimension_check",
            "completeness",
        ]
    }

    if not steps:
        # No step-level data: mark all as uncertain
        for name in checks:
            checks[name] = {
                "passed": overall_valid,
                "detail": f"整体验证: {'通过' if overall_valid else '未通过'} (置信度 {confidence:.0%})",
                "score": confidence if overall_valid else max(0.0, confidence - 0.3),
            }
        return checks

    # Aggregate step labels into dimensions
    dimension_issues: dict[str, list[str]] = {name: [] for name in checks}

    for step in steps:
        if not isinstance(step, dict):
            continue
        label = step.get("label", "valid")
        detail = step.get("detail", "")
        content = step.get("content", f"Step {step.get('step_id', '?')}")

        if label == "valid":
            continue

        # Map label to affected dimensions
        affected_dims = _LABEL_TO_DIMENSION.get(label, ["logical_consistency"])
        for dim in affected_dims:
            issue = f"{content}: {detail}" if detail else content
            dimension_issues[dim].append(issue)

    # Build final check results
    for dim_name, issues in dimension_issues.items():
        if issues:
            n_issues = len(issues)
            checks[dim_name] = {
                "passed": False,
                "detail": "; ".join(issues[:3]),  # Show up to 3 issues
                "score": max(0.0, 1.0 - n_issues * 0.25),
            }
        else:
            checks[dim_name] = {
                "passed": True,
                "detail": "通过",
                "score": confidence,
            }

    return checks


async def run_adaptive_verifier(
    *,
    verifier: Any,
    problem: str,
    solution: dict,
    ctx: dict,
) -> dict:
    """Run verifier with adaptive step-level JSON prompt.

    Shared across standard, complex, and safe_fallback routes.
    """
    candidate_text = solution.get("raw_response", "")
    if not candidate_text:
        steps = solution.get("reasoning_steps", [])
        candidate_text = "\n".join(
            f"Step {s.get('step_id', '?')}: {s.get('description', '')} → {s.get('result', '')}"
            for s in steps if isinstance(s, dict)
        )

    ctx_str = _json.dumps(ctx, ensure_ascii=False, indent=2) if ctx else "(无)"

    user_prompt = format_prompt(
        ADAPTIVE_VERIFIER_USER,
        problem=problem,
        candidate_solution=candidate_text,
        presolve_context=ctx_str,
    )

    messages = verifier.build_messages(
        system_prompt=ADAPTIVE_VERIFIER_SYSTEM,
        user_prompt=user_prompt,
    )

    try:
        response = await verifier.call_llm(messages)
        result = verifier.extract_json(response)

        if result is None:
            return verifier._build_default_result("Adaptive verification failed to parse")

        verified = result.get("overall_valid", False)
        confidence = result.get("confidence", 0.0)
        critical_errors = result.get("critical_errors", [])

        # Build 6-dimension verification checks from step labels
        step_labels = result.get("steps", [])
        six_dim_details = _build_six_dim_checks(step_labels, verified, confidence)

        return {
            "verified": verified,
            "confidence": max(0.0, min(1.0, float(confidence))),
            "overall_score": confidence if verified else max(0.0, confidence - 0.3),
            "details": six_dim_details,
            "step_labels": step_labels,
            "critical_errors": critical_errors,
            "issues_found": critical_errors,
            "suggestions": [result.get("repair_hint", "Review critical errors")],
        }
    except Exception as e:
        logger.error("Adaptive verifier error: %s", e)
        return verifier._build_default_result(str(e))


async def run_adaptive_reflection(
    *,
    reflection: Any,
    problem: str,
    solution: dict,
    verification: dict,
    ctx: dict,
) -> dict:
    """Run reflection with adaptive targeted-revision prompt.

    Shared across complex and safe_fallback routes.
    """
    prev_solution = solution.get("raw_response", solution.get("final_answer", ""))
    errors = verification.get("issues_found", [])
    errors_str = "\n".join(f"- {e}" for e in errors) if errors else "(无)"
    repair_hint = "; ".join(verification.get("suggestions", [])) or "(无)"

    user_prompt = format_prompt(
        ADAPTIVE_REFLECTION_USER,
        problem=problem,
        previous_solution=prev_solution,
        verification_errors=errors_str,
        repair_hint=repair_hint,
    )

    messages = reflection.build_messages(
        system_prompt=ADAPTIVE_REFLECTION_SYSTEM,
        user_prompt=user_prompt,
    )

    try:
        response = await reflection.call_llm(messages)
        result = reflection.extract_json(response)

        if result is None:
            return {
                "revised_solution": response,
                "retry_recommended": True,
                "correction_strategy": {"hints": repair_hint},
                "raw_response": response,
            }

        return {
            "revised_solution": result.get("revised_solution", response),
            "retry_recommended": result.get("retry_recommended", True),
            "correction_strategy": result.get("correction_strategy", {}),
            "raw_response": response,
        }
    except Exception as e:
        logger.error("Adaptive reflection error: %s", e)
        return {
            "revised_solution": "",
            "retry_recommended": False,
            "error": str(e),
        }


def _wrap_bare_latex(text: str) -> str:
    """Wrap bare LaTeX expressions in $$...$$ for remark-math detection.

    Only wraps if:
    - Text contains LaTeX commands (\\cmd pattern)
    - Text does NOT already contain $ delimiters (to avoid conflicts)
    - Text is short enough to be a standalone expression (< 120 chars)
    """
    if not text or len(text) > 120:
        return text
    if "$" in text:
        return text
    if re.search(r"\\[a-zA-Z]+", text):
        return f"$$ {text} $$"
    return text


def build_explanation(solving: dict, classification: dict) -> dict:
    """Build an educational explanation from solver output.

    Extracts the solver's step-by-step reasoning and formats it as a
    Markdown+LaTeX explanation suitable for the ExplanationPanel.
    Uses structured reasoning steps with proper LaTeX delimiters.
    """
    final_answer = solving.get("final_answer", "")
    final_answer_latex = solving.get("final_answer_latex", "")
    domain = classification.get("domain", "")

    # Build from reasoning steps, skipping raw-text descriptions (>200 chars
    # without markdown structure are likely raw LLM output with broken LaTeX)
    steps = solving.get("reasoning_steps", [])
    parts = []
    for s in steps:
        if not isinstance(s, dict):
            parts.append(str(s))
            continue
        desc = s.get("description", "")
        expr = s.get("mathematical_expression", "")
        result = s.get("result", "")
        step_id = s.get("step_id", "?")

        # Skip raw-text descriptions (too long, no markdown headings/lists)
        if len(desc) > 200 and not any(c in desc[:200] for c in ("#", "-", "*", "**")):
            desc = ""

        if desc:
            parts.append(f"**Step {step_id}**: {desc}")
        if expr:
            parts.append(f"$$ {expr} $$")
        if result:
            parts.append(f"\u2192 {_wrap_bare_latex(result)}")

    explanation = "\n\n".join(parts) if parts else ""

    if not explanation:
        explanation = f"\u6700\u7ec8\u7b54\u6848\uff1a{_wrap_bare_latex(final_answer)}"
        if final_answer_latex:
            explanation += f"\n\n$$ {final_answer_latex} $$"

    # Add domain context header if available
    if domain:
        header = f"### {domain} - \u89e3\u9898\u8fc7\u7a0b\n\n"
        explanation = header + explanation

    return {"explanation": explanation}
