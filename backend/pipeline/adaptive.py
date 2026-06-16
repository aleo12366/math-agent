"""Adaptive Pipeline — routes problems through one of four strategies based on guard-layer features."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from api.event_bus import EventBus
from config.settings import Settings, settings
from config.schemas import MathAgentOutput
from pipeline.base import BasePipeline
from pipeline.routes.simple import route_simple
from pipeline.routes.standard import route_standard
from pipeline.routes.complex import route_complex
from pipeline.routes.safe_fallback import route_safe_fallback
from agents.planner import Planner
from agents.solver import Solver
from agents.verifier import Verifier
from agents.reflection import Reflection
from agents.tool_agent import ToolAgent
from guard.context_builder import build_presolve_context
from utils.logger import logger as structured_logger

logger = logging.getLogger(__name__)


class AdaptivePipeline(BasePipeline):
    """Adaptive pipeline that selects among four routing strategies.

    Routes:
        simple:       solver → format (1 LLM call)
        standard:     planner → solver → verifier → format (3 LLM calls)
        complex:      planner → solver×N → canonicalize → verify → consensus → reflect → format
        safe_fallback: planner → solver×N → mandatory tool crosscheck → verifier → flag uncertainty
    """

    def __init__(self, config: Optional[Settings] = None, event_bus: Optional[EventBus] = None):
        super().__init__(config, event_bus)
        self.planner = Planner()
        self.solver = Solver()
        self.verifier = Verifier()
        self.reflection = Reflection()
        self.tool_agent = ToolAgent()

    async def solve(self, problem: str) -> MathAgentOutput:
        """Solve a math problem through the adaptive pipeline.

        Builds a PreSolve context, determines the route, and delegates
        to the appropriate route handler.

        Args:
            problem: The math problem text.

        Returns:
            MathAgentOutput with the complete solution.
        """
        start_time = datetime.now()
        all_outputs = {
            "_start_time": start_time,
            "_pipeline_mode": "adaptive",
            "_debate_agents": self.config.debate_agents,
            "_retry_count": 0,
        }

        structured_logger.pipeline_start(problem[:200], "adaptive")

        try:
            # Guard Layer: build pre-solve context (zero LLM calls)
            await self._emit_stage("preprocessing", "started", 5)
            ctx = build_presolve_context(problem)
            route = ctx.get("fusion", {}).get("route", "standard")
            all_outputs["_route"] = route
            all_outputs["_pre_llm_confidence"] = ctx.get("fusion", {}).get("pre_llm_confidence", 0.0)
            all_outputs["_conflict_flags"] = ctx.get("fusion", {}).get("conflict_flags", [])
            await self._emit_stage("preprocessing", "complete", 10)

            structured_logger.info(f"Adaptive route selected: {route}")

            # Understanding + Classification from guard context
            await self._emit_stage("understanding", "started", 10)
            all_outputs["understanding"] = {
                "cleaned_problem": ctx.get("normalized", {}).get("clean_text", problem),
                "input_type": "mixed",
                "language": "zh",
                "problem_summary": problem[:200],
            }
            all_outputs["classification"] = ctx.get("classification", {})
            all_outputs["knowledge"] = {
                "knowledge_points": ctx.get("classification", {}).get("knowledge_points", []),
                "relevant_theorems": ctx.get("classification", {}).get("relevant_theorems", []),
            }
            await self._emit_stage("understanding", "complete", 15)

            # Route to appropriate strategy
            if route == "simple":
                all_outputs = await route_simple(
                    solver=self.solver,
                    formatter=self.formatter,
                    problem=problem,
                    ctx=ctx,
                    config=self.config,
                    emit_stage=self._emit_stage,
                    all_outputs=all_outputs,
                )
            elif route == "standard":
                all_outputs = await route_standard(
                    planner=self.planner,
                    solver=self.solver,
                    verifier=self.verifier,
                    tool_agent=self.tool_agent,
                    problem=problem,
                    ctx=ctx,
                    config=self.config,
                    emit_stage=self._emit_stage,
                    all_outputs=all_outputs,
                )
            elif route == "complex":
                all_outputs = await route_complex(
                    planner=self.planner,
                    solver=self.solver,
                    verifier=self.verifier,
                    reflection=self.reflection,
                    tool_agent=self.tool_agent,
                    problem=problem,
                    ctx=ctx,
                    config=self.config,
                    emit_stage=self._emit_stage,
                    all_outputs=all_outputs,
                )
            else:  # safe_fallback
                all_outputs = await route_safe_fallback(
                    planner=self.planner,
                    solver=self.solver,
                    verifier=self.verifier,
                    tool_agent=self.tool_agent,
                    problem=problem,
                    ctx=ctx,
                    config=self.config,
                    emit_stage=self._emit_stage,
                    all_outputs=all_outputs,
                )

            # Formatting
            await self._emit_stage("formatting", "started", 95)
            result = self.formatter.format(all_outputs)
            await self._emit_stage("formatting", "complete", 100)

            duration_ms = result.processing_time_ms
            await self._emit_complete("success", duration_ms=duration_ms)

            structured_logger.pipeline_complete(result.problem_id, duration_ms)

            return result

        except Exception as e:
            logger.error("Adaptive pipeline error: %s", e)
            structured_logger.pipeline_error("unknown", str(e))
            await self._emit_error("pipeline", str(e))

            try:
                return self.formatter.format(all_outputs)
            except Exception:
                raise e
