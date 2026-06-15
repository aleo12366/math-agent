"""Multi-agent debate pipeline implementation."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from api.event_bus import EventBus
from config.settings import Settings, settings
from config.schemas import MathAgentOutput, PipelineMode
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
from config.prompts import CONSENSUS_SYSTEM, CONSENSUS_USER, format_prompt
from utils.llm_client import llm_client
from utils.json_parser import extract_json_from_text
from utils.logger import logger as structured_logger

logger = logging.getLogger(__name__)


class MultiPipeline(BasePipeline):
    """Multi-agent debate pipeline.

    Flow: understand → classify → locate → plan → N×solve (parallel)
         → consensus → verify → (if failed: reflect + retry) → explain → format
    """

    def __init__(self, config: Optional[Settings] = None, event_bus: Optional[EventBus] = None):
        super().__init__(config, event_bus)
        self.understander = ProblemUnderstander()
        self.classifier = Classifier()
        self.knowledge_locator = KnowledgeLocator()
        self.planner = Planner()
        self.tool_agent = ToolAgent()
        self.verifier = Verifier()
        self.reflection = Reflection()
        self.explainer = Explainer()
        self.n_agents = config.debate_agents if config else settings.debate_agents

    async def _run_solver(self, agent_id: int, problem: str, context: dict) -> dict:
        """Run a single solver agent instance.

        Args:
            agent_id: Solver agent ID.
            problem: Problem text.
            context: Shared context dict.

        Returns:
            Solver output dict.
        """
        solver = Solver()
        # Add slight variation to encourage diverse solutions
        solver.config = self.config.model_copy(update={
            "temperature": min(1.5, self.config.temperature + agent_id * 0.1)
        })
        result = await solver.run({**context, "agent_id": agent_id})
        result["_agent_id"] = agent_id
        return result

    async def _run_consensus(self, problem: str, solver_results: list[dict]) -> dict:
        """Run consensus voting across solver results.

        Args:
            problem: Original problem text.
            solver_results: List of solver output dicts.

        Returns:
            Consensus result dict.
        """
        # Format agent solutions
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
                # Fallback: pick the first solver's result
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
            # Fallback to first solver
            return {
                "consensus_reached": False,
                "selected_agent": 0,
                "consensus_answer": solver_results[0].get("final_answer", ""),
                "consensus_latex": solver_results[0].get("final_answer_latex", ""),
                "agreement_score": 0.0,
                "error": str(e),
            }

    async def solve(self, problem: str) -> MathAgentOutput:
        """Solve a math problem through the debate pipeline.

        Args:
            problem: The math problem text.

        Returns:
            MathAgentOutput with the consensus solution.
        """
        start_time = datetime.now()
        all_outputs = {
            "_start_time": start_time,
            "_pipeline_mode": "multi_debate",
            "_debate_agents": self.n_agents,
            "_retry_count": 0,
        }

        structured_logger.pipeline_start(problem[:200], "multi_debate")

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

            # Stage 5: Parallel Solving with N agents
            await self._emit_stage("solving", "started", self._calc_progress(5))
            context = {**understanding, **classification, **planning, **knowledge}

            solver_tasks = [
                self._run_solver(i, problem, context)
                for i in range(self.n_agents)
            ]
            solver_results = await asyncio.gather(*solver_tasks, return_exceptions=True)

            # Filter out exceptions
            valid_results = [
                r for r in solver_results if isinstance(r, dict) and "final_answer" in r
            ]
            failed_count = len(solver_results) - len(valid_results)
            if failed_count:
                logger.warning("%d/%d solvers failed on first pass", failed_count, len(solver_results))
            if not valid_results:
                # All solvers failed - use first exception or empty
                valid_results = [{"final_answer": "All solvers failed", "reasoning_steps": []}]

            # Enrich with tool results
            for result in valid_results:
                if result.get("reasoning_steps"):
                    result["reasoning_steps"] = await self.tool_agent.execute_from_solver_output(
                        result["reasoning_steps"]
                    )

            await self._emit_stage("solving", "complete", self._calc_progress(5))

            # Stage 5.5: Consensus
            await self._emit_stage("consensus", "started", self._calc_progress(5))
            consensus = await self._run_consensus(problem, valid_results)
            all_outputs["consensus"] = consensus

            # Use the consensus-selected solver result as the main solving output
            selected_agent = consensus.get("selected_agent", 0)
            best_solution = next(
                (r for r in valid_results if r.get("_agent_id") == selected_agent),
                valid_results[0],
            )

            # Override final answer with consensus answer if available
            if consensus.get("consensus_answer"):
                best_solution["final_answer"] = consensus["consensus_answer"]
            if consensus.get("consensus_latex"):
                best_solution["final_answer_latex"] = consensus["consensus_latex"]

            all_outputs["solving"] = best_solution
            all_outputs["all_solutions"] = valid_results
            await self._emit_stage("consensus", "complete", self._calc_progress(5))

            # Stage 6: Verification
            await self._emit_stage("verification", "started", self._calc_progress(6))
            verification = await self.verifier.run({
                **understanding, **best_solution,
            })
            all_outputs["verification"] = verification
            await self._emit_stage("verification", "complete", self._calc_progress(6))

            # Stage 6.5: Reflection + Retry
            max_retries = self.config.max_retries
            retry_count = 0

            while not verification.get("verified", False) and retry_count < max_retries:
                await self._emit_stage("reflection", "started", self._calc_progress(6))
                structured_logger.retry(
                    retry_count + 1, max_retries,
                    str(verification.get("issues_found", ["Unknown"])),
                )

                reflection_result = await self.reflection.run({
                    **understanding, **best_solution, **verification,
                })
                all_outputs["reflection"] = reflection_result
                await self._emit_stage("reflection", "complete", self._calc_progress(6))

                if not reflection_result.get("retry_recommended", False):
                    break

                retry_count += 1
                all_outputs["_retry_count"] = retry_count

                # Re-run parallel solvers with correction hints
                await self._emit_stage("solving", "started", self._calc_progress(5))
                retry_context = {**context, "correction_hints": reflection_result.get("correction_strategy", {})}
                solver_tasks = [
                    self._run_solver(i, problem, retry_context)
                    for i in range(self.n_agents)
                ]
                solver_results = await asyncio.gather(*solver_tasks, return_exceptions=True)
                valid_results = [r for r in solver_results if isinstance(r, dict) and "final_answer" in r]
                failed_count = len(solver_results) - len(valid_results)
                if failed_count:
                    logger.warning("Retry %d: %d/%d solvers failed", retry_count, failed_count, len(solver_results))
                if not valid_results:
                    logger.error("Retry %d: all solvers failed, stopping retries", retry_count)
                    break
                # Re-run tool enrichment
                for result in valid_results:
                    if result.get("reasoning_steps"):
                        result["reasoning_steps"] = await self.tool_agent.execute_from_solver_output(
                            result["reasoning_steps"]
                        )
                # Re-run consensus
                await self._emit_stage("consensus", "started", self._calc_progress(5))
                consensus = await self._run_consensus(problem, valid_results)
                all_outputs["consensus"] = consensus
                all_outputs["all_solutions"] = valid_results

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
                await self._emit_stage("consensus", "complete", self._calc_progress(5))
                await self._emit_stage("solving", "complete", self._calc_progress(5))

                # Re-verify
                await self._emit_stage("verification", "started", self._calc_progress(6))
                verification = await self.verifier.run({
                    **understanding, **best_solution,
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
                **understanding, **classification, **best_solution, **knowledge,
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

            structured_logger.pipeline_complete(result.problem_id, duration_ms)

            return result

        except Exception as e:
            logger.error("Multi-pipeline error: %s", e)
            structured_logger.pipeline_error("unknown", str(e))
            await self._emit_error("pipeline", str(e))

            try:
                return self.formatter.format(all_outputs)
            except Exception:
                raise e