"""Module 2: Classifier agent - domain, type, and difficulty classification."""

import logging
from agents.base import BaseAgent
from config.prompts import (
    CLASSIFIER_SYSTEM,
    CLASSIFIER_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class Classifier(BaseAgent):
    """Agent that classifies math problems into domain, type, and difficulty."""

    def __init__(self):
        super().__init__(name="classifier")

    async def run(self, input_data: dict) -> dict:
        """Classify the math problem.

        Args:
            input_data: Dict with 'problem', optional 'variables', 'math_expressions'.

        Returns:
            Dict with domain, problem_type, difficulty, difficulty_score, etc.
        """
        problem = input_data.get("cleaned_problem") or input_data.get("problem", "")
        variables = input_data.get("variables", [])
        math_expressions = input_data.get("math_expressions", [])

        user_prompt = format_prompt(
            CLASSIFIER_USER,
            problem=problem,
            variables=", ".join(str(v) for v in variables),
            math_expressions=", ".join(str(e) for e in math_expressions),
        )

        messages = self.build_messages(
            system_prompt=CLASSIFIER_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages)
            result = self.extract_json(response)

            if result is None:
                return {
                    "domain": "微积分",
                    "problem_type": "计算题",
                    "difficulty": "medium",
                    "difficulty_score": 0.5,
                    "sub_domains": [],
                    "reasoning": "Classification failed, using defaults",
                    "raw_response": response,
                }

            # Validate and set defaults
            result.setdefault("domain", "微积分")
            result.setdefault("problem_type", "计算题")
            result.setdefault("difficulty", "medium")
            result.setdefault("difficulty_score", 0.5)
            result.setdefault("sub_domains", [])
            result.setdefault("reasoning", "")

            # Clamp difficulty_score
            if "difficulty_score" in result:
                result["difficulty_score"] = max(0.0, min(1.0, float(result["difficulty_score"])))

            return result

        except Exception as e:
            logger.error("Classifier error: %s", e)
            return {
                "domain": "微积分",
                "problem_type": "计算题",
                "difficulty": "medium",
                "difficulty_score": 0.5,
                "sub_domains": [],
                "reasoning": f"Error: {e}",
                "error": str(e),
            }