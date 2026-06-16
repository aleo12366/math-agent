"""Shared helpers for adaptive pipeline routes."""

from __future__ import annotations

import json as _json
import logging
from typing import Any

from config.prompts import (
    ADAPTIVE_VERIFIER_SYSTEM,
    ADAPTIVE_VERIFIER_USER,
    ADAPTIVE_REFLECTION_SYSTEM,
    ADAPTIVE_REFLECTION_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


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

        return {
            "verified": verified,
            "confidence": max(0.0, min(1.0, float(confidence))),
            "overall_score": confidence if verified else max(0.0, confidence - 0.3),
            "details": {
                "step_labels": result.get("steps", []),
                "critical_errors": critical_errors,
            },
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
