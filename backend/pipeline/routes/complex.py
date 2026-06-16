"""Complex route: planner → solver×N (freeform) → canonicalize → verify → consensus → reflect → format."""

from __future__ import annotations

import asyncio
import json as _json
import logging
from typing import Any

from pipeline.canonicalizer import canonicalize_answer, answers_match
from config.prompts import (
    CONSENSUS_SYSTEM,
    CONSENSUS_USER,
    ADAPTIVE_VERIFIER_SYSTEM,
    ADAPTIVE_VERIFIER_USER,
    ADAPTIVE_REFLECTION_SYSTEM,
    ADAPTIVE_REFLECTION_USER,
    format_prompt,
)
from utils.llm_client import llm_client
from utils.json_parser import extract_json_from_text

logger = logging.getLogger(__name__)


async def route_complex(
    *,
    planner: Any,
    solver: Any,
    verifier: Any,
    reflection: Any,
    tool_agent: Any,
    problem: str,
    ctx: dict[str, Any],
    config: Any,
    emit_stage: Any,
    all_outputs: dict[str, Any],
) -> dict[str, Any]:
    """Run the complex route with parallel freeform solvers, canonicalization, and consensus.

    Dual-channel: solver uses freeform reasoning, verifier uses step-level JSON.
    PreSolve Context passed to all agents.
    """
    normalized = ctx.get("normalized", {})
    classification = ctx.get("classification", {})
    fusion = ctx.get("fusion", {})
    n_candidates = fusion.get("n_candidates", config.debate_agents)

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
    await emit_stage("planning", "complete", 20)

    # Stage: Parallel Solving (freeform, no JSON constraint)
    await emit_stage("solving", "started", 25)
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

    for result in valid_results:
        if result.get("reasoning_steps"):
            result["reasoning_steps"] = await tool_agent.execute_from_solver_output(
                result["reasoning_steps"]
            )

    await emit_stage("solving", "complete", 50)

    # Stage: Canonicalization
    await emit_stage("canonicalization", "started", 55)
    answer_type = normalized.get("answer_type", "expression")
    canonicalized = []
    for r in valid_results:
        canon = canonicalize_answer(r.get("final_answer", ""), answer_type)
        canonicalized.append({**r, "_canonical": canon})
    all_outputs["canonicalized_answers"] = canonicalized
    await emit_stage("canonicalization", "complete", 60)

    # Stage: Verification (step-level JSON on best candidate)
    await emit_stage("verification", "started", 65)
    best_solution = valid_results[0]
    verification = await _run_adaptive_verifier(
        verifier=verifier,
        problem=problem,
        solution=best_solution,
        ctx=ctx,
    )
    all_outputs["verification"] = verification
    await emit_stage("verification", "complete", 72)

    # Stage: Consensus
    await emit_stage("consensus", "started", 75)
    consensus = await _run_consensus(problem, valid_results, n_candidates)
    all_outputs["consensus"] = consensus

    selected_agent = consensus.get("selected_agent", 0)
    best_solution = next(
        (r for r in valid_results if r.get("_agent_id") == selected_agent),
        valid_results[0],
    )
    if consensus.get("consensus_answer"):
        best_solution["final_answer"] = consensus["consensus_answer"]
    if consensus.get("consensus_latex"):
        best_solution["final_answer_latex"] = consensus["consensus_latex"]

    all_outputs["solving"] = best_solution
    all_outputs["all_solutions"] = valid_results
    await emit_stage("consensus", "complete", 82)

    # Stage: Reflection + Retry (targeted, verifier-triggered)
    max_retries = config.max_retries
    retry_count = 0

    while not verification.get("verified", False) and retry_count < max_retries:
        await emit_stage("reflection", "started", 85)
        reflection_result = await _run_adaptive_reflection(
            reflection=reflection,
            problem=problem,
            solution=best_solution,
            verification=verification,
            ctx=ctx,
        )
        all_outputs["reflection"] = reflection_result
        await emit_stage("reflection", "complete", 88)

        if not reflection_result.get("retry_recommended", False):
            break

        retry_count += 1
        all_outputs["_retry_count"] = retry_count

        await emit_stage("solving", "started", 40)
        retry_context = {**solve_context, "correction_hints": reflection_result.get("correction_strategy", {})}
        retry_tasks = []
        for i in range(n_candidates):
            s = solver.__class__()
            s.config = config.model_copy(update={
                "temperature": min(1.5, config.temperature + i * 0.1)
            })
            retry_tasks.append(s.run_freeform({**retry_context, "agent_id": i}))
        solver_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
        valid_results = [r for r in solver_results if isinstance(r, dict) and "final_answer" in r]
        if not valid_results:
            break

        for result in valid_results:
            if result.get("reasoning_steps"):
                result["reasoning_steps"] = await tool_agent.execute_from_solver_output(
                    result["reasoning_steps"]
                )

        await emit_stage("solving", "complete", 50)

        await emit_stage("consensus", "started", 75)
        consensus = await _run_consensus(problem, valid_results, n_candidates)
        all_outputs["consensus"] = consensus
        selected_agent = consensus.get("selected_agent", 0)
        best_solution = next(
            (r for r in valid_results if r.get("_agent_id") == selected_agent),
            valid_results[0],
        )
        if consensus.get("consensus_answer"):
            best_solution["final_answer"] = consensus["consensus_answer"]
        if consensus.get("consensus_latex"):
            best_solution["final_answer_latex"] = consensus["consensus_latex"]
        all_outputs["solving"] = best_solution
        all_outputs["all_solutions"] = valid_results
        await emit_stage("consensus", "complete", 82)

        await emit_stage("verification", "started", 65)
        verification = await _run_adaptive_verifier(
            verifier=verifier,
            problem=problem,
            solution=best_solution,
            ctx=ctx,
        )
        all_outputs["verification"] = verification
        await emit_stage("verification", "complete", 72)

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


async def _run_adaptive_reflection(
    *,
    reflection: Any,
    problem: str,
    solution: dict,
    verification: dict,
    ctx: dict,
) -> dict:
    """Run reflection with adaptive targeted-revision prompt."""
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
            # Freeform reflection — treat as revised solution
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


async def _run_consensus(problem: str, solver_results: list[dict], n_agents: int) -> dict:
    """Run consensus voting across solver results."""
    agent_solutions = ""
    for i, result in enumerate(solver_results):
        answer = result.get("final_answer", "No answer")
        latex = result.get("final_answer_latex", "")
        steps = len(result.get("reasoning_steps", []))
        agent_solutions += f"\n**Agent {i}** (answer: {answer}, latex: {latex}, steps: {steps})\n"
        for step in result.get("reasoning_steps", []):
            if isinstance(step, dict):
                agent_solutions += f"  Step {step.get('step_id', '?')}: {step.get('description', '')} → {step.get('result', '')}\n"

    user_prompt = format_prompt(
        CONSENSUS_USER,
        n_agents=str(len(solver_results)),
        problem=problem,
        agent_solutions=agent_solutions,
    )

    messages = [
        {"role": "system", "content": CONSENSUS_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await llm_client.chat(messages, temperature=0.3, max_tokens=4096)
        result = extract_json_from_text(response)

        if result is None:
            return {
                "consensus_reached": True,
                "selected_agent": 0,
                "consensus_answer": solver_results[0].get("final_answer", ""),
                "consensus_latex": solver_results[0].get("final_answer_latex", ""),
                "agreement_score": 0.5,
            }
        return result

    except Exception as e:
        logger.error("Consensus error: %s", e)
        return {
            "consensus_reached": False,
            "selected_agent": 0,
            "consensus_answer": solver_results[0].get("final_answer", ""),
            "consensus_latex": solver_results[0].get("final_answer_latex", ""),
            "agreement_score": 0.0,
            "error": str(e),
        }
