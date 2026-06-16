"""Standard route: planner → solver (freeform) → verifier (step-level JSON) → format (3 LLM calls)."""

from __future__ import annotations

import json as _json
import logging
from typing import Any

from config.prompts import (
    ADAPTIVE_VERIFIER_SYSTEM,
    ADAPTIVE_VERIFIER_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


async def route_standard(
    *,
    planner: Any,
    solver: Any,
    verifier: Any,
    tool_agent: Any,
    problem: str,
    ctx: dict[str, Any],
    config: Any,
    emit_stage: Any,
    all_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Run the standard route: plan → freeform solve → step-level verify.

    Uses dual-channel: solver gets freeform prompt, verifier gets step-level JSON prompt.
    PreSolve Context is passed through to all agents.
    """
    normalized = ctx.get("normalized", {})
    classification = ctx.get("classification", {})

    base_context = {
        "problem": problem,
        "cleaned_problem": normalized.get("clean_text", problem),
        "domain": classification.get("domain", "微积分"),
        "presolve_context": ctx,
    }

    # Stage: Planning
    await emit_stage("planning", "started", 20)
    planning = await planner.run(base_context)
    all_outputs["planning"] = planning
    await emit_stage("planning", "complete", 30)

    # Stage: Solving (freeform, no JSON constraint)
    await emit_stage("solving", "started", 40)
    solving = await solver.run_freeform({**base_context, **planning})
    if solving.get("reasoning_steps"):
        solving["reasoning_steps"] = await tool_agent.execute_from_solver_output(
            solving["reasoning_steps"]
        )
    all_outputs["solving"] = solving
    await emit_stage("solving", "complete", 70)

    # Stage: Verification (step-level JSON with adaptive prompt)
    await emit_stage("verification", "started", 75)
    verification = await _run_adaptive_verifier(
        verifier=verifier,
        problem=problem,
        solution=solving,
        ctx=ctx,
    )
    all_outputs["verification"] = verification
    await emit_stage("verification", "complete", 90)

    return all_outputs


async def _run_adaptive_verifier(
    *,
    verifier: Any,
    problem: str,
    solution: dict,
    ctx: dict,
) -> dict:
    """Run verifier with adaptive step-level prompt."""
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

        # Map adaptive format to standard format
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
