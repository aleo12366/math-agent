"""Module 5: Solver agent - execute solution plan with step-by-step reasoning."""

import re
import logging
from agents.base import BaseAgent
from config.prompts import (
    SOLVER_SYSTEM,
    SOLVER_USER,
    ADAPTIVE_SOLVER_SYSTEM,
    ADAPTIVE_SOLVER_USER,
    format_prompt,
)

logger = logging.getLogger(__name__)


class Solver(BaseAgent):
    """Agent that executes the solution plan step by step."""

    def __init__(self):
        super().__init__(name="solver")

    async def run_freeform(self, input_data: dict) -> dict:
        """Run solver with free-form natural language reasoning (no JSON constraint).

        Used by the adaptive pipeline's dual-channel strategy where the solver
        produces natural language reasoning and a separate final_answer is extracted.

        Args:
            input_data: Dict with 'problem', 'presolve_context'.

        Returns:
            Dict with reasoning_steps, final_answer, final_answer_latex, answer_format.
        """
        problem = input_data.get("cleaned_problem") or input_data.get("problem", "")
        presolve_ctx = input_data.get("presolve_context", {})

        import json as _json
        ctx_str = _json.dumps(presolve_ctx, ensure_ascii=False, indent=2) if presolve_ctx else "(无)"

        user_prompt = format_prompt(
            ADAPTIVE_SOLVER_USER,
            problem=problem,
            presolve_context=ctx_str,
        )

        messages = self.build_messages(
            system_prompt=ADAPTIVE_SOLVER_SYSTEM,
            user_prompt=user_prompt,
        )

        try:
            response = await self.call_llm(messages, max_tokens=8192)
            return self._parse_freeform_response(response)
        except Exception as e:
            logger.error("Solver freeform error: %s", e)
            return {
                "reasoning_steps": [],
                "final_answer": f"Error during solving: {e}",
                "final_answer_latex": None,
                "answer_format": "text",
                "error": str(e),
            }

    def _parse_freeform_response(self, response: str) -> dict:
        """Extract final answer from free-form reasoning text.

        Looks for common answer patterns:
        - 最终答案：...
        - 答案：...
        - Final Answer: ...
        - \\boxed{...}
        - The answer is ...
        Falls back to the last paragraph if no explicit answer found.
        """
        if not response:
            return {
                "reasoning_steps": [],
                "final_answer": "Unable to solve",
                "final_answer_latex": None,
                "answer_format": "text",
                "raw_response": response,
            }

        final_answer = None
        final_answer_latex = None

        # Try boxed LaTeX (handle nested braces like \boxed{\dfrac{1}{3}})
        boxed = re.search(r"\\boxed\{((?:[^{}]|\{[^{}]*\})+)\}", response)
        if boxed:
            final_answer_latex = boxed.group(1)
            final_answer = final_answer_latex

        # Try explicit answer markers
        if not final_answer:
            for pattern in [
                r"(?:最终答案|答案|Final\s*Answer|Answer)\s*[：:]\s*(.+?)(?:\n|$)",
                r"(?:因此|所以|综上)\s*[,，]?\s*(.+?)(?:\n|$)",
            ]:
                m = re.search(pattern, response, re.IGNORECASE)
                if m:
                    final_answer = m.group(1).strip()
                    break

        # Fallback: last non-empty paragraph
        if not final_answer:
            paragraphs = [p.strip() for p in response.split("\n\n") if p.strip()]
            if paragraphs:
                final_answer = paragraphs[-1][:500]
            else:
                final_answer = response[-500:]

        # Build a single reasoning step from the full response
        reasoning_steps = [{
            "step_id": 1,
            "description": response[:2000],
            "mathematical_expression": final_answer_latex or "",
            "result": final_answer,
            "status": "complete",
        }]

        return {
            "reasoning_steps": reasoning_steps,
            "final_answer": final_answer,
            "final_answer_latex": final_answer_latex,
            "answer_format": "latex" if final_answer_latex else "text",
            "raw_response": response,
        }

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