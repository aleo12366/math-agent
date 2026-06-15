"""
Math Agent - Challenge Cup Competition Entry Point

This module provides the ReasoningAgent class required by the competition platform.
It wraps the multi-agent pipeline (10 agents, verification, retry) using the
platform-provided client for LLM calls.
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add backend to Python path so we can import pipeline modules
_backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(_backend_dir))

from agents.base import BaseAgent
from config.settings import Settings
from pipeline.single import SinglePipeline
from pipeline.multi import MultiPipeline


logger = logging.getLogger(__name__)


class ClientAdapter:
    """Adapts the competition platform client to match LLMClient interface.

    The competition client provides synchronous client.chat(messages, temperature, max_tokens).
    Our pipeline expects an async client with client.chat(messages, temperature, max_tokens).
    This adapter wraps the sync call with asyncio.to_thread() for non-blocking execution.
    """

    def __init__(self, client):
        self._client = client

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        retries: int = 3,
    ) -> str:
        """Async wrapper around the competition client's sync chat method."""
        return await asyncio.to_thread(
            self._client.chat,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


class ReasoningAgent:
    """Math reasoning agent for the Challenge Cup competition.

    Uses a multi-agent pipeline with 10 specialized agents:
    - Problem Understanding, Classification, Knowledge Locating
    - Planning, Solving (with SymPy/SciPy tool calls)
    - 6-Dimension Verification, Reflection/Retry
    - Educational Explanation, Formatting

    Pipeline modes:
    - "single": Linear single-agent flow
    - "multi_debate": N parallel solvers with consensus voting
    """

    def __init__(self, client, *args, **kwargs):
        """Initialize the reasoning agent with the platform-provided client.

        Args:
            client: Official LLM client from the competition platform.
                    Must support client.chat(messages, temperature, max_tokens).
        """
        self.client = client
        self.adapter = ClientAdapter(client)

        # Inject the adapter so all BaseAgent subclasses use the competition client
        BaseAgent._shared_llm = self.adapter

        # Configure settings for competition (no .env file, no local server)
        self.config = Settings(
            temperature=0.3,
            max_tokens=4096,
            pipeline_mode="single",
            max_retries=2,
            log_level="WARNING",
        )

        logger.info("ReasoningAgent initialized with competition client")

    def solve(self, problem: str, metadata: dict) -> dict:
        """Solve a math problem and return the result.

        Args:
            problem: Math problem text.
            metadata: Problem metadata from the platform (may contain idx, etc.).

        Returns:
            Dict with at least "final_response" (non-empty string).
            Also includes "trace" for diagnostics.
        """
        start_time = datetime.now()
        idx = metadata.get("idx", "unknown")
        trace = []

        try:
            trace.append({
                "step": "init",
                "content": f"Problem {idx}: {problem[:100]}...",
            })

            # Run the async pipeline synchronously
            result = asyncio.run(self._solve_async(problem, trace))

            elapsed = (datetime.now() - start_time).total_seconds()
            trace.append({
                "step": "complete",
                "content": f"Solved in {elapsed:.1f}s, confidence={result.get('confidence', 0)}",
            })

            return {
                "final_response": result.get("final_response", ""),
                "trace": trace,
            }

        except Exception as e:
            logger.error("Solve failed for problem %s: %s", idx, e)
            trace.append({
                "step": "error",
                "content": {"type": type(e).__name__, "message": str(e)},
            })
            return {
                "final_response": "",
                "trace": trace,
            }

    async def _solve_async(self, problem: str, trace: list) -> dict:
        """Run the pipeline asynchronously and extract the final response.

        Args:
            problem: Math problem text.
            trace: Mutable trace list to append steps to.

        Returns:
            Dict with final_response, confidence, and other metadata.
        """
        # Create pipeline (single mode for stability)
        pipeline = SinglePipeline(config=self.config)

        # Run the full pipeline
        output = await pipeline.solve(problem)

        # Extract key steps for trace
        for step in output.key_steps[:5]:  # First 5 steps only
            trace.append({
                "step": f"solve_step_{step.step_id}",
                "content": step.description,
            })

        # Verification result
        trace.append({
            "step": "verify",
            "content": f"status={output.verification_status.value}, "
                       f"confidence={output.confidence}",
        })

        return {
            "final_response": output.final_answer,
            "confidence": output.confidence,
            "domain": output.domain.value,
            "problem_type": output.problem_type.value,
            "difficulty": output.difficulty.value,
            "verification_status": output.verification_status.value,
        }
