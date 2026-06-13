"""Module 3: Knowledge Locator agent - locate relevant knowledge points and theorems."""

import logging
from agents.base import BaseAgent
from config.prompts import (
    KNOWLEDGE_LOCATOR_SYSTEM,
    KNOWLEDGE_LOCATOR_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class KnowledgeLocator(BaseAgent):
    """Agent that locates relevant knowledge points, theorems, and methods."""

    def __init__(self):
        super().__init__(name="knowledge_locator")

    async def run(self, input_data: dict) -> dict:
        """Locate knowledge points and theorems for the problem.

        Args:
            input_data: Dict with 'problem', 'domain', 'problem_type', 'difficulty'.

        Returns:
            Dict with knowledge_points, relevant_theorems, key_formulas, etc.
        """
        problem = input_data.get("cleaned_problem") or input_data.get("problem", "")
        domain = input_data.get("domain", "微积分")
        problem_type = input_data.get("problem_type", "计算题")
        difficulty = input_data.get("difficulty", "medium")

        user_prompt = format_prompt(
            KNOWLEDGE_LOCATOR_USER,
            problem=problem,
            domain=domain,
            problem_type=problem_type,
            difficulty=difficulty,
        )

        messages = self.build_messages(
            system_prompt=KNOWLEDGE_LOCATOR_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages)
            result = self.extract_json(response)

            if result is None:
                return {
                    "knowledge_points": [],
                    "relevant_theorems": [],
                    "key_formulas": [],
                    "solution_methods": [],
                    "prerequisites": [],
                    "similar_problem_types": [],
                    "raw_response": response,
                }

            result.setdefault("knowledge_points", [])
            result.setdefault("relevant_theorems", [])
            result.setdefault("key_formulas", [])
            result.setdefault("solution_methods", [])
            result.setdefault("prerequisites", [])

            return result

        except Exception as e:
            logger.error("KnowledgeLocator error: %s", e)
            return {
                "knowledge_points": [],
                "relevant_theorems": [],
                "key_formulas": [],
                "solution_methods": [],
                "prerequisites": [],
                "error": str(e),
            }