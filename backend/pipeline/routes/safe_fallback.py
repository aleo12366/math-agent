"""Safe fallback route: planner → solver×N (freeform) → mandatory tool crosscheck → verifier → flag uncertainty."""

from __future__ import annotations

import asyncio
import json as _json
import logging
from typing import Any

from pipeline.canonicalizer import answers_match
from config.prompts import (
    ADAPTIVE_VERIFIER_SYSTEM,
    ADAPTIVE_VERIFIER_USER,
    format_prompt,
)

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

    Dual-channel: solver uses freeform reasoning, verifier uses step-level JSON.
    PreSolve Context passed to all agents.
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
        "presolve_context": ctx,
    }

    # Stage: Planning
    await emit_stage("planning", "started", 15)
    planning = await planner.run(base_context)
    all_outputs["planning"] = planning
    await emit_stage("planning", "complete", 25)

    # Stage: Parallel Solving (freeform)
    await emit_stage("solving", "started", 30)
    solve_context = {**base_context, **planning}

    async def _run_solver(agent_id: int) -> dict:
        s = solver.__class__()
        s.config = config.model_copy(update={
            "temperature": min(1.5, config.temperature + agent_id * 0.1)
        })
        result = await s.run_freeform({**solve_context, "agent_id": agent_id})
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

    # Stage: Verification (step-level JSON)
    await emit_stage("verification", "started", 70)
    best_solution = valid_results[0]
    verification = await _run_adaptive_verifier(
        verifier=verifier,
        problem=problem,
        solution=best_solution,
        ctx=ctx,
    )
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
