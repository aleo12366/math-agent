"""Standard route: planner → solver → verifier (3 LLM calls)."""

from __future__ import annotations

import logging
from typing import Any

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
    """Run the standard route: plan → solve → verify.

    Args:
        planner: Planner agent instance.
        solver: Solver agent instance.
        verifier: Verifier agent instance.
        tool_agent: ToolAgent instance.
        problem: Problem text.
        ctx: PreSolve context.
        config: Settings instance.
        emit_stage: Coroutine to emit stage events.
        all_outputs: Mutable dict accumulating outputs.

    Returns:
        Updated all_outputs dict.
    """
    normalized = ctx.get("normalized", {})
    classification = ctx.get("classification", {})
    precompute = ctx.get("precompute", {})

    base_context = {
        "problem": problem,
        "cleaned_problem": normalized.get("clean_text", problem),
        "domain": classification.get("domain", "微积分"),
        "problem_type": classification.get("problem_type", "计算题"),
        "difficulty": classification.get("difficulty", "medium"),
        "knowledge_points": classification.get("knowledge_points", []),
        "relevant_theorems": classification.get("relevant_theorems", []),
        "solution_methods": classification.get("solution_methods", []),
    }

    # Stage: Planning
    await emit_stage("planning", "started", 20)
    planning = await planner.run(base_context)
    all_outputs["planning"] = planning
    await emit_stage("planning", "complete", 30)

    # Stage: Solving
    await emit_stage("solving", "started", 40)
    solver_input = {**base_context, **planning}
    solving = await solver.run(solver_input)
    if solving.get("reasoning_steps"):
        solving["reasoning_steps"] = await tool_agent.execute_from_solver_output(
            solving["reasoning_steps"]
        )
    all_outputs["solving"] = solving
    await emit_stage("solving", "complete", 70)

    # Stage: Verification
    await emit_stage("verification", "started", 75)
    verification = await verifier.run({
        "problem": problem,
        "cleaned_problem": normalized.get("clean_text", problem),
        **solving,
    })
    all_outputs["verification"] = verification
    await emit_stage("verification", "complete", 90)

    return all_outputs
