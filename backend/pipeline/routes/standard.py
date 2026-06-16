"""Standard route: planner → solver (freeform) → verifier (step-level JSON) → format (3 LLM calls)."""

from __future__ import annotations

import logging
from typing import Any

from pipeline.routes._common import run_adaptive_verifier

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
    verification = await run_adaptive_verifier(
        verifier=verifier,
        problem=problem,
        solution=solving,
        ctx=ctx,
    )
    all_outputs["verification"] = verification
    await emit_stage("verification", "complete", 90)

    return all_outputs
