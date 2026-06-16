"""Safe fallback route: planner → solver×N → mandatory tool crosscheck → verifier → flag uncertainty."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pipeline.canonicalizer import canonicalize_answer, answers_match

logger = logging.getLogger(__name__)


async def route_safe_fallback(
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
    """Run the safe_fallback route with mandatory tool crosscheck and uncertainty flagging.

    This route is used when the guard layer detects signal conflicts or parse failures.
    It runs multiple solvers, crosschecks with tools, verifies, and flags uncertainty.

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
        Updated all_outputs dict with uncertainty_flags.
    """
    normalized = ctx.get("normalized", {})
    classification = ctx.get("classification", {})
    fusion = ctx.get("fusion", {})
    precompute = ctx.get("precompute", {})
    n_candidates = fusion.get("n_candidates", 3)

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
    await emit_stage("planning", "started", 15)
    planning = await planner.run(base_context)
    all_outputs["planning"] = planning
    await emit_stage("planning", "complete", 25)

    # Stage: Parallel Solving
    await emit_stage("solving", "started", 30)
    solve_context = {**base_context, **planning}

    async def _run_solver(agent_id: int) -> dict:
        s = solver.__class__()
        s.config = config.model_copy(update={
            "temperature": min(1.5, config.temperature + agent_id * 0.1)
        })
        result = await s.run({**solve_context, "agent_id": agent_id})
        result["_agent_id"] = agent_id
        return result

    solver_tasks = [_run_solver(i) for i in range(n_candidates)]
    solver_results = await asyncio.gather(*solver_tasks, return_exceptions=True)

    valid_results = [r for r in solver_results if isinstance(r, dict) and "final_answer" in r]
    if not valid_results:
        valid_results = [{"final_answer": "All solvers failed", "reasoning_steps": [], "_agent_id": 0}]

    await emit_stage("solving", "complete", 50)

    # Stage: Mandatory Tool Crosscheck
    await emit_stage("tool_crosscheck", "started", 55)
    crosscheck_results = []
    for result in valid_results:
        tool_enriched = dict(result)
        if tool_enriched.get("reasoning_steps"):
            tool_enriched["reasoning_steps"] = await tool_agent.execute_from_solver_output(
                tool_enriched["reasoning_steps"]
            )

        symbolic_candidates = precompute.get("symbolic_candidates", [])
        tool_crosscheck = []
        for candidate in symbolic_candidates:
            try:
                tool_result = await tool_agent.execute(
                    candidate.get("type", "simplify"),
                    candidate.get("params", {}),
                )
                tool_crosscheck.append({
                    "candidate": candidate,
                    "tool_result": {
                        "value": tool_result.value,
                        "numeric": tool_result.numeric,
                        "latex": tool_result.latex,
                    },
                })
            except Exception as e:
                logger.warning("Tool crosscheck failed: %s", e)
                tool_crosscheck.append({
                    "candidate": candidate,
                    "tool_result": {"value": f"Error: {e}"},
                })

        tool_enriched["_tool_crosscheck"] = tool_crosscheck
        crosscheck_results.append(tool_enriched)

    valid_results = crosscheck_results
    all_outputs["tool_crosscheck"] = [r.get("_tool_crosscheck", []) for r in valid_results]
    await emit_stage("tool_crosscheck", "complete", 65)

    # Stage: Verification
    await emit_stage("verification", "started", 70)
    best_solution = valid_results[0]
    verification = await verifier.run({
        "problem": problem,
        "cleaned_problem": normalized.get("clean_text", problem),
        **best_solution,
    })
    all_outputs["verification"] = verification
    all_outputs["solving"] = best_solution
    await emit_stage("verification", "complete", 85)

    # Flag uncertainty
    uncertainty_flags = list(fusion.get("conflict_flags", []))
    if not verification.get("verified", False):
        uncertainty_flags.append("verification_failed")
    if len(valid_results) > 1:
        answers = [r.get("final_answer", "") for r in valid_results]
        answer_type = normalized.get("answer_type", "expression")
        for i in range(len(answers)):
            for j in range(i + 1, len(answers)):
                if not answers_match(answers[i], answers[j], answer_type):
                    uncertainty_flags.append("solver_disagreement")
                    break
            if "solver_disagreement" in uncertainty_flags:
                break

    all_outputs["uncertainty_flags"] = uncertainty_flags
    all_outputs["all_solutions"] = valid_results

    if uncertainty_flags:
        all_outputs["_pipeline_notes"] = (
            f"Uncertainty detected: {', '.join(uncertainty_flags)}. "
            "Results should be reviewed carefully."
        )

    return all_outputs
