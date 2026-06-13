"""Module 1: Problem Understanding agent - clean and parse input."""

import logging
from agents.base import BaseAgent
from config.prompts import (
    PROBLEM_UNDERSTANDER_SYSTEM,
    PROBLEM_UNDERSTANDER_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class ProblemUnderstander(BaseAgent):
    """Agent that cleans, parses, and normalizes math problem input."""

    def __init__(self):
        super().__init__(name="problem_understander")

    async def run(self, input_data: dict) -> dict:
        """Clean and understand the input math problem.

        Args:
            input_data: Dict with 'problem' key containing the raw problem text.

        Returns:
            Dict with cleaned problem, input type, language, expressions, etc.
        """
        problem = input_data.get("problem", "")
        if not problem:
            return {"error": "No problem provided", "cleaned_problem": ""}

        user_prompt = format_prompt(
            PROBLEM_UNDERSTANDER_USER,
            problem=problem,
        )

        messages = self.build_messages(
            system_prompt=PROBLEM_UNDERSTANDER_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages)
            result = self.extract_json(response)

            if result is None:
                # Fallback: return the original problem as cleaned
                return {
                    "cleaned_problem": problem,
                    "input_type": "text",
                    "language": "unknown",
                    "math_expressions": [],
                    "variables": [],
                    "constraints": [],
                    "problem_summary": problem[:200],
                    "raw_response": response,
                }

            # Ensure required fields
            result.setdefault("cleaned_problem", problem)
            result.setdefault("input_type", "text")
            result.setdefault("language", "unknown")
            result.setdefault("math_expressions", [])
            result.setdefault("variables", [])
            result.setdefault("constraints", [])

            return result

        except Exception as e:
            logger.error("ProblemUnderstander error: %s", e)
            return {
                "cleaned_problem": problem,
                "input_type": "text",
                "language": "unknown",
                "math_expressions": [],
                "variables": [],
                "constraints": [],
                "error": str(e),
            }