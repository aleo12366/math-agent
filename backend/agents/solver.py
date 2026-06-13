"""Module 5: Solver agent - execute solution plan with step-by-step reasoning."""

import logging
from agents.base import BaseAgent
from config.prompts import (
    SOLVER_SYSTEM,
    SOLVER_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class Solver(BaseAgent):
    """Agent that executes the solution plan step by step."""

    def __init__(self):
        super().__init__(name="solver")

    async def run(self, input_data: dict) -> dict:
        """Execute the solution plan and produce reasoning steps.

        Args:
            input_data: Dict with 'problem', 'domain', 'strategy', 'steps',
                       'knowledge_points', 'relevant_theorems', etc.

        Returns:
            Dict with reasoning_steps, final_answer, final_answer_latex, answer_format.
        """
        problem = input_data.get("cleaned_problem") or input_data.get("problem", "")
        domain = input_data.get("domain", "微积分")
        strategy = input_data.get("strategy", "Direct computation")
        steps = input_data.get("steps", [])

        # Format steps as text
        steps_text = ""
        for step in steps:
            if isinstance(step, dict):
                sid = step.get("step_id", "?")
                desc = step.get("description", "")
                method = step.get("method", "")
                steps_text += f"Step {sid}: {desc}\n  Method: {method}\n"
            else:
                steps_text += f"- {step}\n"

        user_prompt = format_prompt(
            SOLVER_USER,
            problem=problem,
            domain=domain,
            strategy=strategy,
            steps_text=steps_text,
        )

        messages = self.build_messages(
            system_prompt=SOLVER_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages, max_tokens=8192)
            result = self.extract_json(response)

            if result is None:
                return {
                    "reasoning_steps": [],
                    "final_answer": response[:500] if response else "Unable to solve",
                    "final_answer_latex": None,
                    "answer_format": "text",
                    "raw_response": response,
                }

            result.setdefault("reasoning_steps", [])
            result.setdefault("final_answer", "No answer generated")
            result.setdefault("final_answer_latex", None)
            result.setdefault("answer_format", "text")

            # Validate reasoning steps
            for i, step in enumerate(result["reasoning_steps"]):
                if isinstance(step, dict):
                    step.setdefault("step_id", i + 1)
                    step.setdefault("description", "")
                    step.setdefault("mathematical_expression", "")
                    step.setdefault("result", "")
                    step.setdefault("status", "complete")
                else:
                    result["reasoning_steps"][i] = {
                        "step_id": i + 1,
                        "description": str(step),
                        "mathematical_expression": "",
                        "result": str(step),
                        "status": "complete",
                    }

            return result

        except Exception as e:
            logger.error("Solver error: %s", e)
            return {
                "reasoning_steps": [],
                "final_answer": f"Error during solving: {e}",
                "final_answer_latex": None,
                "answer_format": "text",
                "error": str(e),
            }