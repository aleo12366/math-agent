"""Calibrated Router — routes problems to pipeline paths based on guard features."""

from __future__ import annotations

from typing import Any


class CalibratedRouter:
    """Rule-based router that maps guard-layer features to a pipeline route.

    Routes:
        simple       — high confidence, low complexity
        standard     — moderate confidence/complexity
        complex      — low confidence or high complexity
        safe_fallback — hard overrides (parse failure, signal conflict)

    Attributes:
        CONFIDENCE_HIGH: threshold above which confidence is "high".
        CONFIDENCE_MID:  threshold above which confidence is "moderate".
        COMPLEXITY_LOW:  threshold below which complexity is "low".
        COMPLEXITY_MID:  threshold below which complexity is "moderate".
    """

    CONFIDENCE_HIGH: float = 0.8
    CONFIDENCE_MID: float = 0.5
    COMPLEXITY_LOW: float = 0.2
    COMPLEXITY_MID: float = 0.5

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """Route a problem based on guard-layer features.

        Args:
            features: dict with keys:
                type_confidence: float 0.0-1.0
                complexity_score: float 0.0-1.0
                retrieval_score: float 0.0-1.0 (optional)
                tool_success: float 0.0-1.0 (optional)
                guard_parse_failed: bool (optional, default False)
                top1_top2_method_conflict: bool (optional, default False)
                top1_top2_classification_conflict: bool (optional, default False)
                precompute_failure: bool (optional, default False)

        Returns:
            dict with keys:
                route: one of "simple", "standard", "complex", "safe_fallback"
                pre_llm_confidence: float, blended confidence score
                conflict_flags: list[str], detected conflict types
                n_candidates: int, number of candidate solutions to generate
        """
        conflict_flags = self._detect_conflicts(features)
        confidence = self._rule_based(features)

        # Hard overrides
        if features.get("guard_parse_failed", False):
            return {
                "route": "safe_fallback",
                "pre_llm_confidence": confidence,
                "conflict_flags": conflict_flags + ["guard_parse_failed"],
                "n_candidates": 3,
            }

        if "signal_conflict" in conflict_flags:
            return {
                "route": "safe_fallback",
                "pre_llm_confidence": confidence,
                "conflict_flags": conflict_flags,
                "n_candidates": 3,
            }

        complexity = features.get("complexity_score", 0.0)
        route = self._route_from_scores(confidence, complexity)

        n_candidates = 3 if route in ("complex", "safe_fallback") else 1

        return {
            "route": route,
            "pre_llm_confidence": confidence,
            "conflict_flags": conflict_flags,
            "n_candidates": n_candidates,
        }

    def _rule_based(self, features: dict[str, Any]) -> float:
        """Cold-start hand-written confidence blending.

        Uses a weighted combination of type_confidence, retrieval_score,
        and tool_success. Weights are calibrated for cold-start (no ML model).
        """
        type_conf = features.get("type_confidence", 0.0)
        retrieval = features.get("retrieval_score", 0.0)
        tool = features.get("tool_success", 0.0)

        confidence = 0.6 * type_conf + 0.25 * retrieval + 0.15 * tool
        return round(min(confidence, 1.0), 4)

    def _route_from_scores(self, confidence: float, complexity: float) -> str:
        """Map confidence and complexity scores to a route.

        Rules:
            simple:   confidence > 0.8 AND complexity <= 0.2
            standard: confidence > 0.5 AND complexity <= 0.5
            complex:  everything else
        """
        if confidence > self.CONFIDENCE_HIGH and complexity <= self.COMPLEXITY_LOW:
            return "simple"
        if confidence > self.CONFIDENCE_MID and complexity <= self.COMPLEXITY_MID:
            return "standard"
        return "complex"

    def _detect_conflicts(self, features: dict[str, Any]) -> list[str]:
        """Detect conflicts in guard-layer signals.

        Returns a list of conflict flag strings:
            method_conflict:          top1 vs top2 methods disagree
            classification_conflict:  top1 vs top2 classifications disagree
            precompute_failure:       local precompute failed
            signal_conflict:          any severe signal disagreement (triggers safe_fallback)
        """
        flags: list[str] = []

        if features.get("top1_top2_method_conflict", False):
            flags.append("method_conflict")

        if features.get("top1_top2_classification_conflict", False):
            flags.append("classification_conflict")

        if features.get("precompute_failure", False):
            flags.append("precompute_failure")

        # signal_conflict is a composite: any severe disagreement
        if "method_conflict" in flags or "classification_conflict" in flags:
            flags.append("signal_conflict")

        return flags
