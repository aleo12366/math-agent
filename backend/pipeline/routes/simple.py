"""Simple route: solver → format (1 LLM call)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def route_simple(
    *,
    solver: Any,
    formatter: Any,
    problem: str,
    ctx: dict[str, Any],
    config: Any,
    emit_stage: Any,
    all_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Run the simple route: one solver call then format.

    Args:
        solver: Solver agent instance.
        formatter: Formatter instance.
        problem: Problem text.
        ctx: PreSolve context from build_presolve_context.
        config: Settings instance.
        emit_stage: Coroutine to emit stage events.
        all_outputs: Mutable dict accumulating outputs.

    Returns:
        Updated all_outputs dict.
    """
    normalized = ctx.get("normalized", {})
    classification = ctx.get("classification", {})

    solver_input = {
        "problem": problem,
        "cleaned_problem": normalized.get("clean_text", problem),
        "domain": classification.get("domain", "微积分"),
        "problem_type": classification.get("problem_type", "计算题"),
        "difficulty": classification.get("difficulty", "medium"),
        "strategy": "Direct computation",
        "steps": [],
    }

    await emit_stage("solving", "started", 50)
    solving = await solver.run(solver_input)
    all_outputs["solving"] = solving
    await emit_stage("solving", "complete", 80)

    return all_outputs
