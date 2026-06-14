"""Module 6.5: Reflection agent - error analysis and correction strategy."""

import logging
from agents.base import BaseAgent
from config.prompts import (
    REFLECTION_SYSTEM,
    REFLECTION_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class Reflection(BaseAgent):
    """Agent that analyzes errors and proposes correction strategies."""

    def __init__(self):
        super().__init__(name="reflection")

    async def run(self, input_data: dict) -> dict:
        """Analyze verification failures and propose corrections.

        Args:
            input_data: Dict with 'problem', 'reasoning_steps', 'verification_details',
                       'issues_found'.

        Returns:
            Dict with has_errors, error_analysis, correction_strategy, retry_recommended.
        """
        problem = input_data.get("cleaned_problem") or input_data.get("problem", "")
        reasoning_steps = input_data.get("reasoning_steps", [])
        verification_details = (
            input_data.get("verification_details")
            or input_data.get("details")
            or {}
        )
        issues_found = input_data.get("issues_found", [])

        # Format reasoning steps
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

        # Format verification details
        import json
        verification_text = json.dumps(verification_details, ensure_ascii=False, indent=2)
        issues_text = "\n".join(f"- {issue}" for issue in issues_found)

        user_prompt = format_prompt(
            REFLECTION_USER,
            problem=problem,
            reasoning_steps=steps_text,
            verification_details=verification_text,
            issues_found=issues_text,
        )

        messages = self.build_messages(
            system_prompt=REFLECTION_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages)
            result = self.extract_json(response)

            if result is None:
                return {
                    "has_errors": True,
                    "error_analysis": {
                        "error_type": "unknown",
                        "error_location": "unknown",
                        "root_cause": "Failed to analyze",
                        "severity": "medium",
                    },
                    "correction_strategy": {
                        "approach": "Retry entire solution",
                        "affected_steps": [],
                        "new_steps": [],
                    },
                    "retry_recommended": True,
                    "retry_reason": "Reflection failed, recommend full retry",
                    "raw_response": response,
                }

            result.setdefault("has_errors", True)
            result.setdefault("retry_recommended", True)

            # Validate error_analysis structure
            if "error_analysis" not in result or not isinstance(result["error_analysis"], dict):
                result["error_analysis"] = {
                    "error_type": "unknown",
                    "error_location": "unknown",
                    "root_cause": "Analysis incomplete",
                    "severity": "medium",
                }

            # Validate correction_strategy structure
            if "correction_strategy" not in result or not isinstance(result["correction_strategy"], dict):
                result["correction_strategy"] = {
                    "approach": "Retry",
                    "affected_steps": [],
                    "new_steps": [],
                }

            return result

        except Exception as e:
            logger.error("Reflection error: %s", e)
            return {
                "has_errors": True,
                "error_analysis": {
                    "error_type": "unknown",
                    "error_location": "unknown",
                    "root_cause": str(e),
                    "severity": "medium",
                },
                "correction_strategy": {
                    "approach": "Retry after error",
                    "affected_steps": [],
                    "new_steps": [],
                },
                "retry_recommended": True,
                "retry_reason": f"Reflection error: {e}",
                "error": str(e),
            }