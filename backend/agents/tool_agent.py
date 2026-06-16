"""Tool Agent - wraps SymPy/SciPy calls for use by other agents."""

import asyncio
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
            # Run blocking SymPy/SciPy in thread pool to avoid freezing event loop
            result = await asyncio.to_thread(func, **params)
            self.logger.debug("Tool %s(%s) = %s", tool_name, params, result.value)
            return result

        except TypeError as e:
            # Parameter mismatch - try with fewer params
            self.logger.warning("Tool %s param error: %s", tool_name, e)
            try:
                # Try with just the first param
                first_key = next(iter(params))
                result = await asyncio.to_thread(func, params[first_key])
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
        return await self.execute_parallel(steps)

    async def execute_parallel(self, reasoning_steps: list[dict]) -> list[dict]:
        """Execute tool calls in parallel, grouped by dependency.

        Groups tool calls into dependency batches and executes each batch
        concurrently using asyncio.gather.

        Args:
            reasoning_steps: List of reasoning step dicts from the solver.

        Returns:
            Enriched steps list with tool_result fields filled in.
        """
        tool_calls = [
            (i, step)
            for i, step in enumerate(reasoning_steps)
            if step.get("tool_used") and step.get("tool_used") in TOOL_REGISTRY
        ]

        if not tool_calls:
            return list(reasoning_steps)

        groups = self._build_dependency_groups(tool_calls)

        for group in groups:
            tasks = [self._execute_single_tool(step) for _, step in group]
            results = await asyncio.gather(*tasks)
            for (idx, _), result in zip(group, results):
                reasoning_steps[idx]["tool_result"] = {
                    "value": result.value,
                    "numeric": result.numeric,
                    "latex": result.latex,
                }

        return reasoning_steps

    def _build_dependency_groups(
        self, tool_calls: list[tuple[int, dict]]
    ) -> list[list[tuple[int, dict]]]:
        """Group tool calls by dependency for parallel execution.

        Uses a simple heuristic: all independent calls go into one group
        (fully parallel). Steps that reference a prior step's result are
        placed in a subsequent group.

        Args:
            tool_calls: List of (index, step) tuples with tool calls.

        Returns:
            List of groups, each group is a list of (index, step) tuples.
            Groups are executed sequentially; calls within a group run concurrently.
        """
        independent = []
        dependent = []
        seen_outputs = set()

        for item in tool_calls:
            idx, step = item
            expr = step.get("mathematical_expression", "")
            if any(ref in expr for ref in seen_outputs):
                dependent.append(item)
            else:
                independent.append(item)
                seen_outputs.add(f"step_{idx}")

        groups = []
        if independent:
            groups.append(independent)
        if dependent:
            groups.append(dependent)
        return groups

    async def _execute_single_tool(self, step: dict) -> ToolResult:
        """Execute a single tool call from a reasoning step.

        Args:
            step: A reasoning step dict containing tool_used and params.

        Returns:
            ToolResult from the tool execution.
        """
        tool_used = step["tool_used"]
        params = self._extract_tool_params(step)
        if params:
            return await self.execute(tool_used, params)
        return ToolResult(value=f"No params for tool: {tool_used}")

    def _extract_tool_params(self, step: dict) -> Optional[dict]:
        """Extract tool parameters from a reasoning step.

        Args:
            step: A reasoning step dict.

        Returns:
            Dict of tool parameters, or None if extraction fails.
        """
        # Prefer structured tool_params from solver output
        if isinstance(step.get("tool_params"), dict):
            return step["tool_params"]

        expr = step.get("mathematical_expression", "")
        tool_used = step.get("tool_used", "")

        if not expr:
            return None

        expr_clean = expr.replace("$", "").strip()

        defaults = {
            "simplify": {"expr": expr_clean},
            "solve": {"equation": expr_clean, "variable": "x"},
            "diff": {"expr": expr_clean, "var": "x"},
            "integrate": {"expr": expr_clean, "var": "x"},
            "limit": {"expr": expr_clean, "var": "x", "point": "0"},
            "numerical_eval": {"expr": expr_clean},
            "verify_equality": {"expr1": expr_clean, "expr2": ""},
            "optimize": {"method": "minimize", "func": expr_clean},
            "quad": {"func": expr_clean, "lower": 0.0, "upper": 1.0},
            "eval_np": {"expr": expr_clean},
        }
        return defaults.get(tool_used, {"expr": expr_clean})

    def list_tools(self) -> list[str]:
        """List all available tool names.

        Returns:
            List of registered tool names.
        """
        return list(TOOL_REGISTRY.keys())