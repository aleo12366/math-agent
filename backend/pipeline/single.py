"""Single-agent linear pipeline implementation."""

import logging
import time
from datetime import datetime
from typing import Optional

from api.event_bus import EventBus
from config.settings import Settings, settings
from config.schemas import MathAgentOutput
from pipeline.base import BasePipeline
from agents.problem_understander import ProblemUnderstander
from agents.classifier import Classifier
from agents.knowledge_locator import KnowledgeLocator
from agents.planner import Planner
from agents.solver import Solver
from agents.tool_agent import ToolAgent
from agents.verifier import Verifier
from agents.reflection import Reflection
from agents.explainer import Explainer
from agents.formatter import Formatter
from utils.logger import logger as structured_logger

logger = logging.getLogger(__name__)


class SinglePipeline(BasePipeline):
    """Linear single-agent pipeline.

    Flow: understand → classify → locate → plan → solve → verify
         → (if failed: reflect + retry) → explain → format
    """

    def __init__(self, config: Optional[Settings] = None, event_bus: Optional[EventBus] = None):
        super().__init__(config, event_bus)
        self.understander = ProblemUnderstander()
        self.classifier = Classifier()
        self.knowledge_locator = KnowledgeLocator()
        self.planner = Planner()
        self.solver = Solver()
        self.tool_agent = ToolAgent()
        self.verifier = Verifier()
        self.reflection = Reflection()
        self.explainer = Explainer()
        self.formatter = Formatter()

    async def _solve_with_tools(self, context: dict) -> dict:
        """Run solver then enrich with tool results."""
        solving = await self.solver.run(context)
        if solving.get("reasoning_steps"):
            solving["reasoning_steps"] = await self.tool_agent.execute_from_solver_output(
                solving["reasoning_steps"]
            )
        return solving

    async def solve(self, problem: str) -> MathAgentOutput:
        """Solve a math problem through the linear pipeline.

        Args:
            problem: The math problem text.

        Returns:
            MathAgentOutput with the complete solution.
        """
        start_time = datetime.now()
        all_outputs = {
            "_start_time": start_time,
            "_pipeline_mode": "single",
            "_debate_agents": 1,
            "_retry_count": 0,
        }

        structured_logger.pipeline_start(problem[:200], "single")

        try:
            # Stage 1: Problem Understanding
            await self._emit_stage("understanding", "started", self._calc_progress(1))
            understanding = await self.understander.run({"problem": problem})
            all_outputs["understanding"] = understanding
            await self._emit_stage("understanding", "complete", self._calc_progress(1))

            # Stage 2: Classification
            await self._emit_stage("classification", "started", self._calc_progress(2))
            classification = await self.classifier.run(understanding)
            all_outputs["classification"] = classification
            await self._emit_stage("classification", "complete", self._calc_progress(2))

            # Stage 3: Knowledge Locating
            await self._emit_stage("knowledge", "started", self._calc_progress(3))
            knowledge = await self.knowledge_locator.run({**understanding, **classification})
            all_outputs["knowledge"] = knowledge
            await self._emit_stage("knowledge", "complete", self._calc_progress(3))

            # Stage 4: Planning
            await self._emit_stage("planning", "started", self._calc_progress(4))
            planning = await self.planner.run({
                **understanding, **classification, **knowledge,
            })
            all_outputs["planning"] = planning
            await self._emit_stage("planning", "complete", self._calc_progress(4))

            # Stage 5: Solving
            await self._emit_stage("solving", "started", self._calc_progress(5))
            solving = await self._solve_with_tools({
                **understanding, **classification, **planning, **knowledge,
            })
            all_outputs["solving"] = solving

            # Emit step events for each reasoning step
            steps = solving.get("reasoning_steps", [])
            for i, step in enumerate(steps):
                if isinstance(step, dict):
                    await self._emit_step(
                        step.get("step_id", i + 1),
                        len(steps),
                        step.get("description", ""),
                        step.get("mathematical_expression", ""),
                        self._calc_progress(5) + int((i / max(len(steps), 1)) * (100 // self.stages_total)),
                    )

            await self._emit_stage("solving", "complete", self._calc_progress(5))

            # Stage 6: Verification
            await self._emit_stage("verification", "started", self._calc_progress(6))
            verification = await self.verifier.run({
                **understanding, **solving,
            })
            all_outputs["verification"] = verification
            await self._emit_stage("verification", "complete", self._calc_progress(6))

            # Stage 6.5: Reflection + Retry loop
            max_retries = self.config.max_retries
            retry_count = 0

            while not verification.get("verified", False) and retry_count < max_retries:
                await self._emit_stage("reflection", "started", self._calc_progress(6))
                structured_logger.retry(
                    retry_count + 1, max_retries,
                    str(verification.get("issues_found", ["Unknown"])),
                )

                reflection_result = await self.reflection.run({
                    **understanding, **solving, **verification,
                })
                all_outputs["reflection"] = reflection_result
                await self._emit_stage("reflection", "complete", self._calc_progress(6))

                if not reflection_result.get("retry_recommended", False):
                    break

                # Re-solve with correction hints
                retry_count += 1
                all_outputs["_retry_count"] = retry_count

                await self._emit_stage("solving", "started", self._calc_progress(5))
                solving = await self._solve_with_tools({
                    **understanding, **classification, **planning, **knowledge,
                    "correction_hints": reflection_result.get("correction_strategy", {}),
                })
                all_outputs["solving"] = solving
                await self._emit_stage("solving", "complete", self._calc_progress(5))

                # Re-verify
                await self._emit_stage("verification", "started", self._calc_progress(6))
                verification = await self.verifier.run({
                    **understanding, **solving,
                })
                all_outputs["verification"] = verification
                await self._emit_stage("verification", "complete", self._calc_progress(6))

            structured_logger.verification(
                verification.get("verified", False),
                verification.get("confidence", 0),
                verification.get("overall_score", 0),
            )

            # Stage 7: Explanation
            await self._emit_stage("explanation", "started", self._calc_progress(7))
            explanation = await self.explainer.run({
                **understanding, **classification, **solving, **knowledge,
            })
            all_outputs["explanation"] = explanation
            await self._emit_stage("explanation", "complete", self._calc_progress(7))

            # Stage 8: Formatting
            await self._emit_stage("formatting", "started", self._calc_progress(8))
            result = self.formatter.format(all_outputs)
            await self._emit_stage("formatting", "complete", self._calc_progress(9))

            # Emit completion
            duration_ms = result.processing_time_ms
            await self._emit_complete("success", duration_ms=duration_ms)

            structured_logger.pipeline_complete(
                result.problem_id, duration_ms,
            )

            return result

        except Exception as e:
            logger.error("Pipeline error: %s", e)
            structured_logger.pipeline_error("unknown", str(e))
            await self._emit_error("pipeline", str(e))

            # Try to format whatever we have
            try:
                return self.formatter.format(all_outputs)
            except Exception:
                raise e