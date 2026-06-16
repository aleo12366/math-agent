"""Structured Cache — multi-field keyed problem cache with semantic reuse checks."""

from __future__ import annotations

import hashlib
from typing import Any


def _canonicalize(text: str) -> str:
    """Collapse whitespace and strip for canonical comparison."""
    return " ".join(text.split()).strip()


def _build_cache_key(
    canonical_text: str,
    constraint_signature: str,
    answer_type: str,
    domain: str,
) -> str:
    """Build a deterministic cache key from multiple problem fields.

    The key is a SHA-256 hex digest of the concatenation of:
    canonical_text + constraint_signature + answer_type + domain.
    This ensures that problems with the same text but different constraints,
    answer types, or domains produce different keys.
    """
    raw = f"{canonical_text}|{constraint_signature}|{answer_type}|{domain}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_constraint_signature(graph: dict[str, Any]) -> str:
    """Build a compact string signature from the constraint graph.

    Encodes the structural constraints (equalities, inequalities, boundaries,
    initial conditions, domain, variables, knowns) into a canonical string
    so that problems with the same text but different constants/ranges
    produce different signatures.
    """
    parts: list[str] = []
    for key in (
        "variables",
        "unknowns",
        "knowns",
        "equality_constraints",
        "inequality_constraints",
        "boundary_constraints",
        "initial_constraints",
        "domain_constraints",
    ):
        vals = graph.get(key, [])
        parts.append(f"{key}={','.join(str(v) for v in sorted(vals))}")
    parts.append(f"target={graph.get('target', '')}")
    parts.append(f"answer_shape={graph.get('answer_shape', '')}")
    return "|".join(parts)


def _constraint_signature_similarity(sig_a: str, sig_b: str) -> float:
    """Compute similarity between two constraint signatures.

    Uses Jaccard similarity over the token set of each signature.
    Returns a float 0.0-1.0.
    """
    tokens_a = set(sig_a.split("|"))
    tokens_b = set(sig_b.split("|"))
    if not tokens_a and not tokens_b:
        return 1.0
    union = tokens_a | tokens_b
    intersection = tokens_a & tokens_b
    return len(intersection) / len(union)


class ProblemCache:
    """In-memory cache for PreSolveContext keyed by multi-field hash.

    Cache key = hash(canonical_text + constraint_signature + answer_type + domain).
    This prevents false cache hits when problems share similar text but differ
    in constants, ranges, constraints, or domain classification.

    Usage:
        cache = ProblemCache()
        cache.set(problem_id, context)
        cached = cache.get(problem_id, new_context)
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, problem_id: str, context: dict[str, Any]) -> dict[str, Any] | None:
        """Look up a cached context by problem_id, then verify reuse is safe.

        Returns the cached context if reuse_ok(), else None.
        """
        if problem_id not in self._store:
            return None
        cached = self._store[problem_id]
        if self.reuse_ok(cached, context):
            return cached
        return None

    def set(self, problem_id: str, context: dict[str, Any]) -> None:
        """Store a context in the cache."""
        self._store[problem_id] = context

    def invalidate(self, problem_id: str) -> None:
        """Remove an entry from the cache."""
        self._store.pop(problem_id, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)

    @staticmethod
    def build_key(context: dict[str, Any]) -> str:
        """Build the cache key from a PreSolveContext dict."""
        normalized = context.get("normalized", {})
        graph = context.get("constraint_graph", {})
        classification = context.get("classification", {})

        canonical_text = _canonicalize(normalized.get("clean_text", ""))
        constraint_sig = _build_constraint_signature(graph)
        answer_type = normalized.get("answer_type", "")
        domain = classification.get("domain", "")

        return _build_cache_key(canonical_text, constraint_sig, answer_type, domain)

    @staticmethod
    def reuse_ok(cached: dict[str, Any], incoming: dict[str, Any]) -> bool:
        """Check whether a cached context can be reused for an incoming problem.

        Reuse requires ALL of:
            1. same_domain: domains must match exactly
            2. same_answer_type: answer types must match exactly
            3. constraint_signature_similarity >= 0.98

        Returns True if reuse is safe, False otherwise.
        """
        cached_class = cached.get("classification", {})
        incoming_class = incoming.get("classification", {})

        if cached_class.get("domain") != incoming_class.get("domain"):
            return False

        cached_norm = cached.get("normalized", {})
        incoming_norm = incoming.get("normalized", {})
        if cached_norm.get("answer_type") != incoming_norm.get("answer_type"):
            return False

        cached_graph = cached.get("constraint_graph", {})
        incoming_graph = incoming.get("constraint_graph", {})
        cached_sig = _build_constraint_signature(cached_graph)
        incoming_sig = _build_constraint_signature(incoming_graph)
        similarity = _constraint_signature_similarity(cached_sig, incoming_sig)
        return similarity >= 0.98
