"""Simple route: solver (freeform) → format (1 LLM call)."""

from __future__ import annotations

import logging
from typing import Any

from pipeline.routes._common import build_explanation

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
    """Run the simple route: one freeform solver call then format.

    Uses run_freeform (no JSON constraint) with PreSolve Context passed to solver.
    """
    normalized = ctx.get("normalized", {})
    classification = ctx.get("classification", {})

    solver_input = {
        "problem": problem,
        "cleaned_problem": normalized.get("clean_text", problem),
        "domain": classification.get("domain", "未知"),
        "presolve_context": ctx,
    }

    await emit_stage("solving", "started", 50)
    solving = await solver.run_freeform(solver_input)
    all_outputs["solving"] = solving
    await emit_stage("solving", "complete", 80)

    # Build educational explanation from solver output
    all_outputs["explanation"] = build_explanation(solving, classification)

    return all_outputs
