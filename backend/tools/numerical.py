"""SciPy/NumPy numerical operations for the tool agent."""

import ast
import logging
import numpy as np
from scipy import optimize, linalg, integrate as scipy_integrate
from config.schemas import ToolResult

logger = logging.getLogger(__name__)

MAX_EXPR_LEN = 500

_SAFE_GLOBALS = {
    "__builtins__": {},
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
    "pi": np.pi, "e": np.e, "abs": np.abs,
    "arcsin": np.arcsin, "arccos": np.arccos, "arctan": np.arctan,
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "array": np.array, "linspace": np.linspace,
}
_SAFE_NAMES = set(_SAFE_GLOBALS.keys())


def _validate_expr(expr: str):
    """Reject expressions with attribute access (prevents sandbox escape)."""
    try:
        tree = ast.parse(expr, mode="eval")
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                raise ValueError("attribute access not allowed")
    except SyntaxError:
        raise ValueError("invalid expression syntax")


def _safe_eval(expr: str, local_vars: dict = None):
    """Eval with sandboxed builtins and length limit."""
    if not expr or len(expr) > MAX_EXPR_LEN:
        raise ValueError(f"expression too long ({len(expr)} chars)")
    _validate_expr(expr)
    return eval(expr, _SAFE_GLOBALS, local_vars or {})


def scipy_optimize(method: str, func: str, constraints: dict = None, x0: list = None) -> ToolResult:
    """Perform numerical optimization.
    
    Args:
        method: Optimization method (minimize, maximize, root).
        func: String expression of the objective function.
        constraints: Optional constraints dict.
        x0: Optional initial guess.
        
    Returns:
        ToolResult with optimization result.
    """
    try:
        # Parse the function
        def objective(x):
            return _safe_eval(func, {"x": x})

        if x0 is None:
            x0 = [0.0]

        if method == "minimize":
            result = optimize.minimize(objective, x0, method="Nelder-Mead",
                                       options={"maxiter": 300, "maxfev": 500})
            return ToolResult(
                value=f"min={result.fun:.6f}, x={result.x.tolist()}",
                numeric=float(result.fun),
            )
        elif method == "maximize":
            result = optimize.minimize(lambda x: -objective(x), x0, method="Nelder-Mead",
                                       options={"maxiter": 300, "maxfev": 500})
            return ToolResult(
                value=f"max={-result.fun:.6f}, x={result.x.tolist()}",
                numeric=float(-result.fun),
            )
        elif method == "root":
            result = optimize.root(objective, x0, options={"maxfev": 500})
            return ToolResult(
                value=f"root={result.x.tolist()}, success={result.success}",
                numeric=float(result.x[0]) if len(result.x) == 1 else None,
            )
        else:
            return ToolResult(value=f"Unknown optimization method: {method}")
    except Exception as e:
        logger.error("scipy_optimize error: %s", e)
        return ToolResult(value=f"Error: {e}")


def scipy_linalg(operation: str, matrix: list) -> ToolResult:
    """Perform numerical linear algebra operations.
    
    Args:
        operation: Operation type (eigvals, solve, svd, lu, qr, cholesky).
        matrix: 2D list of matrix values.
        
    Returns:
        ToolResult with operation result.
    """
    try:
        A = np.array(matrix, dtype=float)

        if operation == "eigvals":
            eigenvalues = linalg.eigvals(A)
            vals = ", ".join(f"{v:.6f}" for v in eigenvalues)
            return ToolResult(value=f"eigenvalues=[{vals}]")

        elif operation == "eig":
            eigenvalues, eigenvectors = linalg.eig(A)
            vals = ", ".join(f"{v:.6f}" for v in eigenvalues)
            return ToolResult(value=f"eigenvalues=[{vals}]")

        elif operation == "svd":
            U, s, Vh = linalg.svd(A)
            singular_vals = ", ".join(f"{v:.6f}" for v in s)
            return ToolResult(value=f"singular_values=[{singular_vals}]")

        elif operation == "det":
            d = linalg.det(A)
            return ToolResult(value=str(d), numeric=float(d))

        elif operation == "inv":
            A_inv = linalg.inv(A)
            return ToolResult(value=str(A_inv.tolist()))

        elif operation == "lu":
            P, L, U = linalg.lu(A)
            return ToolResult(value=f"L={L.tolist()}, U={U.tolist()}")

        elif operation == "qr":
            Q, R = linalg.qr(A)
            return ToolResult(value=f"Q={Q.tolist()}, R={R.tolist()}")

        elif operation == "norm":
            norms = {
                "frobenius": linalg.norm(A, "fro"),
                "spectral": linalg.norm(A, 2),
            }
            return ToolResult(
                value=f"frobenius={norms['frobenius']:.6f}, spectral={norms['spectral']:.6f}",
                numeric=float(norms["frobenius"]),
            )

        else:
            return ToolResult(value=f"Unknown linalg operation: {operation}")

    except Exception as e:
        logger.error("scipy_linalg error: %s", e)
        return ToolResult(value=f"Error: {e}")


def scipy_integrate_quad(func: str, lower: float, upper: float) -> ToolResult:
    """Perform numerical integration using scipy.integrate.quad.
    
    Args:
        func: String expression of the function to integrate.
        lower: Lower bound.
        upper: Upper bound.
        
    Returns:
        ToolResult with integration result.
    """
    try:
        def integrand(x):
            return _safe_eval(func, {"x": x})

        result, error = scipy_integrate.quad(integrand, lower, upper, limit=100)
        return ToolResult(
            value=f"result={result:.10f}, error={error:.2e}",
            numeric=float(result),
        )
    except Exception as e:
        logger.error("scipy_integrate error: %s", e)
        return ToolResult(value=f"Error: {e}")


def scipy_solve_ode(func: str, y0: list, t_span: tuple, t_eval: list = None) -> ToolResult:
    """Solve an ODE numerically.
    
    Args:
        func: String expression defining dy/dt = f(t, y).
        y0: Initial conditions.
        t_span: Time span (t_start, t_end).
        t_eval: Optional specific time points to evaluate.
        
    Returns:
        ToolResult with ODE solution.
    """
    try:
        from scipy.integrate import solve_ivp

        def ode_func(t, y):
            return _safe_eval(func, {"t": t, "y": y})

        if t_eval is None:
            t_eval = np.linspace(t_span[0], t_span[1], 100).tolist()

        sol = solve_ivp(ode_func, t_span, y0, t_eval=t_eval, method="RK45",
                        max_step=(t_span[1] - t_span[0]) / 50)

        if sol.success:
            # Return last value
            final_vals = sol.y[:, -1].tolist()
            return ToolResult(
                value=f"y_final={[f'{v:.6f}' for v in final_vals]}",
                numeric=float(final_vals[0]) if len(final_vals) == 1 else None,
            )
        else:
            return ToolResult(value=f"ODE solver failed: {sol.message}")

    except Exception as e:
        logger.error("scipy_solve_ode error: %s", e)
        return ToolResult(value=f"Error: {e}")


def numerical_eval_np(expr: str, variables: dict = None) -> ToolResult:
    """Evaluate a numerical expression using NumPy.
    
    Args:
        expr: String expression to evaluate.
        variables: Optional dict of variable values.
        
    Returns:
        ToolResult with numerical result.
    """
    try:
        ns = {"__builtins__": {}, "sin": np.sin, "cos": np.cos, "tan": np.tan,
              "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
              "pi": np.pi, "e": np.e, "abs": np.abs,
              "arcsin": np.arcsin, "arccos": np.arccos, "arctan": np.arctan,
              "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
              "array": np.array}

        if not expr or len(expr) > MAX_EXPR_LEN:
            raise ValueError(f"expression too long ({len(expr)} chars)")
        _validate_expr(expr)
        # Pass variables as locals (cannot override __builtins__ in globals)
        result = eval(expr, ns, variables or {})
        result = float(np.asarray(result).flat[0])

        return ToolResult(
            value=f"{result:.10f}",
            numeric=result,
        )
    except Exception as e:
        logger.error("numerical_eval_np error: %s", e)
        return ToolResult(value=f"Error: {e}")