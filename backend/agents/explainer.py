"""Module 7: Explainer agent - generate educational explanations."""

import logging
from agents.base import BaseAgent
from config.prompts import (
    EXPLAINER_SYSTEM,
    EXPLAINER_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class Explainer(BaseAgent):
    """Agent that generates educational explanations in Markdown+LaTeX."""

    def __init__(self):
        super().__init__(name="explainer")

    async def run(self, input_data: dict) -> dict:
        """Generate an educational explanation for the solution.

        Args:
            input_data: Dict with 'problem', 'domain', 'difficulty', 'reasoning_steps',
                       'final_answer', 'theorems_applied', 'knowledge_points'.

        Returns:
            Dict with 'explanation' containing Markdown+LaTeX text.
        """
        problem = input_data.get("cleaned_problem") or input_data.get("problem", "")
        domain = input_data.get("domain", "微积分")
        difficulty = input_data.get("difficulty", "medium")
        reasoning_steps = input_data.get("reasoning_steps", [])
        final_answer = input_data.get("final_answer", "")
        theorems_applied = input_data.get("relevant_theorems") or input_data.get("theorems_applied", [])
        knowledge_points = input_data.get("knowledge_points", [])

        # Format reasoning steps
        steps_text = ""
        for step in reasoning_steps:
            if isinstance(step, dict):
                sid = step.get("step_id", "?")
                desc = step.get("description", "")
                expr = step.get("mathematical_expression", "")
                result = step.get("result", "")
                justification = step.get("justification", "")
                steps_text += f"Step {sid}: {desc}\n"
                if expr:
                    steps_text += f"  Expression: {expr}\n"
                if result:
                    steps_text += f"  Result: {result}\n"
                if justification:
                    steps_text += f"  Justification: {justification}\n"
            else:
                steps_text += f"- {step}\n"

        user_prompt = format_prompt(
            EXPLAINER_USER,
            problem=problem,
            domain=domain,
            difficulty=difficulty,
            reasoning_steps=steps_text,
            final_answer=final_answer,
            theorems_applied=", ".join(str(t) for t in theorems_applied),
            knowledge_points=", ".join(str(k) for k in knowledge_points),
        )

        messages = self.build_messages(
            system_prompt=EXPLAINER_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages, max_tokens=4096)
            result = self.extract_json(response)

            if result is None:
                # If JSON extraction fails, use the raw response as the explanation
                return {
                    "explanation": response if response else "Explanation generation failed.",
                }

            result.setdefault("explanation", "No explanation generated.")

            return result

        except Exception as e:
            logger.error("Explainer error: %s", e)
            return {
                "explanation": f"Error generating explanation: {e}",
                "error": str(e),
            }