"""Module 6: Verifier agent - 6-dimension verification of solutions."""

import logging
from agents.base import BaseAgent
from config.prompts import (
    VERIFIER_SYSTEM,
    VERIFIER_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)

# Default verification check template
DEFAULT_CHECK = {
    "passed": False,
    "detail": "Verification not completed",
    "score": 0.0,
}


class Verifier(BaseAgent):
    """Agent that verifies solutions across 6 dimensions."""

    def __init__(self):
        super().__init__(name="verifier")

    async def run(self, input_data: dict) -> dict:
        """Verify the mathematical solution.

        Args:
            input_data: Dict with 'problem', 'reasoning_steps', 'final_answer',
                       'final_answer_latex'.

        Returns:
            Dict with verified (bool), confidence, overall_score, details, issues_found, suggestions.
        """
        problem = input_data.get("cleaned_problem") or input_data.get("problem", "")
        reasoning_steps = input_data.get("reasoning_steps", [])
        final_answer = input_data.get("final_answer", "")
        final_answer_latex = input_data.get("final_answer_latex", "")

        # Format reasoning steps as text
        steps_text = ""
        for step in reasoning_steps:
            if isinstance(step, dict):
                sid = step.get("step_id", "?")
                desc = step.get("description", "")
                expr = step.get("mathematical_expression", "")
                result = step.get("result", "")
                steps_text += f"Step {sid}: {desc}\n  Expression: {expr}\n  Result: {result}\n"
            else:
                steps_text += f"- {step}\n"

        user_prompt = format_prompt(
            VERIFIER_USER,
            problem=problem,
            reasoning_steps=steps_text,
            final_answer=final_answer,
            final_answer_latex=final_answer_latex or "N/A",
        )

        messages = self.build_messages(
            system_prompt=VERIFIER_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages)
            result = self.extract_json(response)

            if result is None:
                return self._build_default_result("Verification failed to parse LLM output")

            # Validate structure
            result.setdefault("verified", False)
            result.setdefault("confidence", 0.0)
            result.setdefault("overall_score", 0.0)
            result.setdefault("issues_found", [])
            result.setdefault("suggestions", [])

            # Ensure all 6 check dimensions exist
            details = result.get("details", {})
            for check_name in [
                "formula_consistency",
                "boundary_conditions",
                "logical_consistency",
                "special_cases",
                "dimension_check",
                "completeness",
            ]:
                details.setdefault(check_name, DEFAULT_CHECK.copy())

            result["details"] = details

            # Clamp values
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            result["overall_score"] = max(0.0, min(1.0, float(result["overall_score"])))

            return result

        except Exception as e:
            logger.error("Verifier error: %s", e)
            return self._build_default_result(str(e))

    def _build_default_result(self, error_msg: str) -> dict:
        """Build a default verification result with all checks failing."""
        return {
            "verified": False,
            "confidence": 0.0,
            "overall_score": 0.0,
            "details": {
                name: {"passed": False, "detail": error_msg, "score": 0.0}
                for name in [
                    "formula_consistency",
                    "boundary_conditions",
                    "logical_consistency",
                    "special_cases",
                    "dimension_check",
                    "completeness",
                ]
            },
            "issues_found": [error_msg],
            "suggestions": ["Retry verification"],
            "error": error_msg,
        }