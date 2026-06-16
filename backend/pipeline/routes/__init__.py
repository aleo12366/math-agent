"""Pipeline routing strategies."""

from pipeline.routes.simple import route_simple
from pipeline.routes.standard import route_standard
from pipeline.routes.complex import route_complex
from pipeline.routes.safe_fallback import route_safe_fallback

__all__ = ["route_simple", "route_standard", "route_complex", "route_safe_fallback"]
