"""Module 4: Planner agent - create step-by-step solution plan."""

import logging
from agents.base import BaseAgent
from config.prompts import (
    PLANNER_SYSTEM,
    PLANNER_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class Planner(BaseAgent):
    """Agent that creates a detailed step-by-step solution plan."""

    def __init__(self):
        super().__init__(name="planner")

    async def run(self, input_data: dict) -> dict:
        """Create a solution plan for the math problem.

        Args:
            input_data: Dict with 'problem', 'domain', 'problem_type', 'difficulty',
                       'knowledge_points', 'relevant_theorems', 'solution_methods'.

        Returns:
            Dict with strategy, steps list, estimated_difficulty, alternative_approaches.
        """
        problem = input_data.get("cleaned_problem") or input_data.get("problem", "")
        domain = input_data.get("domain", "微积分")
        problem_type = input_data.get("problem_type", "计算题")
        difficulty = input_data.get("difficulty", "medium")
        knowledge_points = input_data.get("knowledge_points", [])
        relevant_theorems = input_data.get("relevant_theorems", [])
        solution_methods = input_data.get("solution_methods", [])

        user_prompt = format_prompt(
            PLANNER_USER,
            problem=problem,
            domain=domain,
            problem_type=problem_type,
            difficulty=difficulty,
            knowledge_points=", ".join(str(k) for k in knowledge_points),
            relevant_theorems=", ".join(str(t) for t in relevant_theorems),
            solution_methods=", ".join(str(m) for m in solution_methods),
        )

        messages = self.build_messages(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages)
            result = self.extract_json(response)

            if result is None:
                return {
                    "strategy": "Direct computation",
                    "steps": [],
                    "estimated_difficulty": difficulty,
                    "alternative_approaches": [],
                    "raw_response": response,
                }

            result.setdefault("strategy", "Direct computation")
            result.setdefault("steps", [])
            result.setdefault("estimated_difficulty", difficulty)
            result.setdefault("alternative_approaches", [])

            # Ensure steps have required fields
            for i, step in enumerate(result["steps"]):
                if isinstance(step, dict):
                    step.setdefault("step_id", i + 1)
                    step.setdefault("description", "")
                    step.setdefault("method", "")
                    step.setdefault("tools_needed", [])
                else:
                    # Convert non-dict step to dict
                    result["steps"][i] = {
                        "step_id": i + 1,
                        "description": str(step),
                        "method": "",
                        "tools_needed": [],
                    }

            return result

        except Exception as e:
            logger.error("Planner error: %s", e)
            return {
                "strategy": "Direct computation",
                "steps": [],
                "estimated_difficulty": difficulty,
                "alternative_approaches": [],
                "error": str(e),
            }