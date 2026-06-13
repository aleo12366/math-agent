"""Tool Agent - wraps SymPy/SciPy calls for use by other agents."""

import logging
from typing import Optional
from config.schemas import ToolResult
from tools.symbolic import (
    sympy_simplify,
    sympy_solve,
    sympy_integrate,
    sympy_diff,
    sympy_limit,
    sympy_matrix,
    verify_equality,
    numerical_eval,
)
from tools.numerical import (
    scipy_optimize,
    scipy_linalg,
    scipy_integrate_quad,
    scipy_solve_ode,
    numerical_eval_np,
)

logger = logging.getLogger(__name__)

# Registry of available tools
TOOL_REGISTRY = {
    "simplify": sympy_simplify,
    "solve": sympy_solve,
    "integrate": sympy_integrate,
    "diff": sympy_diff,
    "limit": sympy_limit,
    "matrix": sympy_matrix,
    "verify_equality": verify_equality,
    "numerical_eval": numerical_eval,
    "optimize": scipy_optimize,
    "linalg": scipy_linalg,
    "quad": scipy_integrate_quad,
    "ode": scipy_solve_ode,
    "eval_np": numerical_eval_np,
}


class ToolAgent:
    """Agent that executes mathematical tools (SymPy/SciPy).

    This agent does NOT use the LLM. It dispatches tool calls
    to the appropriate symbolic or numerical function.
    """

    def __init__(self):
        self.name = "tool_agent"
        self.logger = logging.getLogger("agent.tool_agent")

    async def execute(self, tool_name: str, params: dict) -> ToolResult:
        """Execute a named mathematical tool.

        Args:
            tool_name: Name of the tool to execute (must be in TOOL_REGISTRY).
            params: Parameters to pass to the tool function.

        Returns:
            ToolResult with the computation result.
        """
        if tool_name not in TOOL_REGISTRY:
            self.logger.warning("Unknown tool: %s", tool_name)
            return ToolResult(value=f"Unknown tool: {tool_name}")

        func = TOOL_REGISTRY[tool_name]

        try:
            # Filter params to match function signature
            result = func(**params)
            self.logger.debug("Tool %s(%s) = %s", tool_name, params, result.value)
            return result

        except TypeError as e:
            # Parameter mismatch - try with fewer params
            self.logger.warning("Tool %s param error: %s", tool_name, e)
            try:
                # Try with just the first param
                first_key = next(iter(params))
                result = func(params[first_key])
                return result
            except Exception as inner_e:
                self.logger.error("Tool %s retry failed: %s", tool_name, inner_e)
                return ToolResult(value=f"Tool error: {e}")

        except Exception as e:
            self.logger.error("Tool %s execution error: %s", tool_name, e)
            return ToolResult(value=f"Tool error: {e}")

    async def execute_from_solver_output(self, steps: list[dict]) -> list[dict]:
        """Execute tool calls referenced in solver output steps.

        Examines each step for tool_used fields and executes them,
        enriching the steps with tool_result data.

        Args:
            steps: List of reasoning step dicts from the solver.

        Returns:
            Enriched steps list with tool_result fields filled in.
        """
        enriched = []
        for step in steps:
            tool_used = step.get("tool_used")
            if tool_used and tool_used in TOOL_REGISTRY:
                # Extract tool params from the step
                params = self._extract_tool_params(step)
                if params:
                    result = await self.execute(tool_used, params)
                    step["tool_result"] = {
                        "value": result.value,
                        "numeric": result.numeric,
                        "latex": result.latex,
                    }
            enriched.append(step)
        return enriched

    def _extract_tool_params(self, step: dict) -> Optional[dict]:
        """Extract tool parameters from a reasoning step.

        Args:
            step: A reasoning step dict.

        Returns:
            Dict of tool parameters, or None if extraction fails.
        """
        expr = step.get("mathematical_expression", "")
        description = step.get("description", "")
        tool_used = step.get("tool_used", "")

        if not expr:
            return None

        # Clean LaTeX delimiters
        expr_clean = expr.replace("$", "").strip()

        if tool_used == "simplify":
            return {"expr": expr_clean}
        elif tool_used == "solve":
            return {"equation": expr_clean}
        elif tool_used == "diff":
            return {"expr": expr_clean}
        elif tool_used == "integrate":
            return {"expr": expr_clean}
        elif tool_used == "limit":
            return {"expr": expr_clean}
        elif tool_used == "numerical_eval":
            return {"expr": expr_clean}
        else:
            return {"expr": expr_clean}

    def list_tools(self) -> list[str]:
        """List all available tool names.

        Returns:
            List of registered tool names.
        """
        return list(TOOL_REGISTRY.keys())