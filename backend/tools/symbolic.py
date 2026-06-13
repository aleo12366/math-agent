"""SymPy symbolic math operations for the tool agent."""

import logging
import sympy
from sympy import (
    symbols, simplify, solve, integrate, diff, limit,
    Matrix, Eq, oo, pi, E, I, sqrt, sin, cos, tan, log, exp,
    latex, factorial, binomial, Rational, Sum, Product,
    Function, Derivative, Integral, dsolve, solveset,
    S, Interval, Union, Intersection, FiniteSet,
)
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor,
)
from config.schemas import ToolResult

logger = logging.getLogger(__name__)

TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


def _safe_parse(expr_str: str):
    """Safely parse a string expression into a SymPy expression."""
    try:
        return parse_expr(expr_str, transformations=TRANSFORMATIONS)
    except Exception:
        return sympy.sympify(expr_str)


def sympy_simplify(expr: str) -> ToolResult:
    """Simplify a symbolic expression.
    
    Args:
        expr: String expression to simplify.
        
    Returns:
        ToolResult with simplified expression.
    """
    try:
        parsed = _safe_parse(expr)
        result = simplify(parsed)
        return ToolResult(
            value=str(result),
            latex=f"${latex(result)}$",
        )
    except Exception as e:
        logger.error("sympy_simplify error: %s", e)
        return ToolResult(value=f"Error: {e}")


def sympy_solve(equation: str, variable: str = "x") -> ToolResult:
    """Solve an equation for a variable.
    
    Args:
        equation: String equation (e.g., "x**2 - 4" or "Eq(x**2, 4)").
        variable: Variable to solve for.
        
    Returns:
        ToolResult with solution(s).
    """
    try:
        var = symbols(variable)
        # Handle Eq(...) format
        if equation.startswith("Eq("):
            eq = _safe_parse(equation)
        else:
            parsed = _safe_parse(equation)
            eq = parsed  # solve() can handle expression = 0

        solutions = solve(eq, var)
        sol_str = ", ".join(str(s) for s in solutions)
        sol_latex = ", ".join(latex(s) for s in solutions)

        return ToolResult(
            value=sol_str,
            latex=f"${sol_latex}$",
        )
    except Exception as e:
        logger.error("sympy_solve error: %s", e)
        return ToolResult(value=f"Error: {e}")


def sympy_integrate(expr: str, var: str = "x", bounds: tuple = None) -> ToolResult:
    """Compute integral of an expression.
    
    Args:
        expr: Expression to integrate.
        var: Variable of integration.
        bounds: Optional tuple (lower, upper) for definite integral.
        
    Returns:
        ToolResult with integral result.
    """
    try:
        x = symbols(var)
        parsed = _safe_parse(expr)

        if bounds:
            lower = _safe_parse(str(bounds[0])) if bounds[0] else None
            upper = _safe_parse(str(bounds[1])) if bounds[1] else None
            result = integrate(parsed, (x, lower, upper))
        else:
            result = integrate(parsed, x)

        return ToolResult(
            value=str(result),
            latex=f"${latex(result)}$",
        )
    except Exception as e:
        logger.error("sympy_integrate error: %s", e)
        return ToolResult(value=f"Error: {e}")


def sympy_diff(expr: str, var: str = "x", order: int = 1) -> ToolResult:
    """Compute derivative of an expression.
    
    Args:
        expr: Expression to differentiate.
        var: Variable of differentiation.
        order: Order of derivative.
        
    Returns:
        ToolResult with derivative result.
    """
    try:
        x = symbols(var)
        parsed = _safe_parse(expr)
        result = diff(parsed, x, order)
        simplified = simplify(result)

        return ToolResult(
            value=str(simplified),
            latex=f"${latex(simplified)}$",
        )
    except Exception as e:
        logger.error("sympy_diff error: %s", e)
        return ToolResult(value=f"Error: {e}")


def sympy_limit(expr: str, var: str = "x", point: str = "0") -> ToolResult:
    """Compute limit of an expression.
    
    Args:
        expr: Expression to compute limit for.
        var: Variable approaching the limit.
        point: Point the variable approaches (can be "oo" for infinity).
        
    Returns:
        ToolResult with limit result.
    """
    try:
        x = symbols(var)
        parsed = _safe_parse(expr)
        pt = _safe_parse(point)

        result = limit(parsed, x, pt)

        return ToolResult(
            value=str(result),
            latex=f"${latex(result)}$",
        )
    except Exception as e:
        logger.error("sympy_limit error: %s", e)
        return ToolResult(value=f"Error: {e}")


def sympy_matrix(operation: str, matrix_data: list) -> ToolResult:
    """Perform matrix operations.
    
    Args:
        operation: Operation type (det, inv, eigenvals, rref, rank, multiply).
        matrix_data: 2D list of matrix values.
        
    Returns:
        ToolResult with matrix operation result.
    """
    try:
        M = Matrix(matrix_data)

        if operation == "det":
            result = M.det()
        elif operation == "inv":
            result = M.inv()
        elif operation == "eigenvals":
            result = M.eigenvals()
        elif operation == "rref":
            result = M.rref()
        elif operation == "rank":
            result = M.rank()
        elif operation == "transpose":
            result = M.T
        elif operation == "charpoly":
            result = M.charpoly()
        else:
            return ToolResult(value=f"Unknown operation: {operation}")

        return ToolResult(
            value=str(result),
            latex=f"${latex(result)}$",
        )
    except Exception as e:
        logger.error("sympy_matrix error: %s", e)
        return ToolResult(value=f"Error: {e}")


def verify_equality(expr1: str, expr2: str) -> ToolResult:
    """Verify if two expressions are mathematically equal.
    
    Args:
        expr1: First expression.
        expr2: Second expression.
        
    Returns:
        ToolResult with verification result.
    """
    try:
        e1 = _safe_parse(expr1)
        e2 = _safe_parse(expr2)

        # Try symbolic equality
        diff_expr = simplify(e1 - e2)
        is_equal = diff_expr == 0

        return ToolResult(
            value=str(is_equal),
            numeric=1.0 if is_equal else 0.0,
        )
    except Exception as e:
        logger.error("verify_equality error: %s", e)
        return ToolResult(value=f"Error: {e}")


def numerical_eval(expr: str, precision: int = 15) -> ToolResult:
    """Evaluate an expression numerically.
    
    Args:
        expr: Expression to evaluate.
        precision: Number of decimal digits.
        
    Returns:
        ToolResult with numerical value.
    """
    try:
        parsed = _safe_parse(expr)
        result = parsed.evalf(precision)

        return ToolResult(
            value=str(result),
            numeric=float(result) if result.is_real else None,
            latex=f"${latex(result)}$",
        )
    except Exception as e:
        logger.error("numerical_eval error: %s", e)
        return ToolResult(value=f"Error: {e}")