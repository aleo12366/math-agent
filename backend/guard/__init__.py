"""Pre-LLM Guard Layer — zero-LLM local preprocessing for math problems."""

from .normalizer import normalize_problem, build_constraint_graph
from .complexity import estimate_risk
from .type_matcher import hybrid_classify
from .precompute import local_precompute
from .router import CalibratedRouter
from .context_builder import build_presolve_context
from .cache import ProblemCache

__all__ = [
    "normalize_problem", "build_constraint_graph", "estimate_risk",
    "hybrid_classify", "local_precompute", "CalibratedRouter",
    "build_presolve_context", "ProblemCache",
]
