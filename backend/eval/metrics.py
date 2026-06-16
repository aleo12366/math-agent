"""Evaluation metrics and ablation runner for the adaptive pipeline.

Five metric categories (per [S9]):
  1. Guard quality  — route accuracy, type classification correctness
  2. End-to-end     — pass@1, final answer correctness
  3. Anti-hallucination — verification catch rate, tool crosscheck agreement
  4. Calibration    — confidence vs actual correctness (ECE)
  5. Efficiency     — avg latency, avg LLM calls per problem
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProblemResult:
    """Raw result for a single problem evaluation."""

    problem_id: str
    problem: str
    predicted_answer: str
    expected_answer: str
    correct: bool
    route: str
    domain: str = ""
    difficulty: str = ""
    confidence: float = 0.0
    latency_ms: float = 0.0
    llm_calls: int = 0
    verification_passed: bool = False
    guard_route: str = ""
    ground_truth_route: str = ""
    tool_used: bool = False
    tool_agreed: bool = True
    error: str = ""


class PipelineMetrics:
    """Collects per-problem results and computes summary statistics.

    Covers five metric categories: guard quality, end-to-end effectiveness,
    anti-hallucination, calibration, and efficiency.

    Usage:
        metrics = PipelineMetrics()
        metrics.record(result)
        summary = metrics.summary()
        metrics.save("eval_results.json")
    """

    def __init__(self) -> None:
        self.results: list[ProblemResult] = []
        self._start_time = time.monotonic()

    def record(self, result: ProblemResult) -> None:
        """Record a single problem result.

        Args:
            result: A ProblemResult dataclass with the problem's evaluation data.
        """
        self.results.append(result)

    def summary(self) -> dict[str, Any]:
        """Generate evaluation summary across all recorded results.

        Returns:
            dict with keys for each metric category:
              - pass_at_1: fraction of correct answers
              - route_distribution: count of problems per route
              - avg_latency_ms: mean processing latency
              - avg_llm_calls: mean number of LLM API calls per problem
              - guard_accuracy: fraction where guard route matched ground truth
              - verification_catch_rate: fraction of wrong answers caught by verifier
              - tool_agreement_rate: fraction where tool crosscheck agreed with answer
              - ece: expected calibration error (confidence vs correctness)
              - by_domain: per-domain accuracy breakdown
              - by_difficulty: per-difficulty accuracy breakdown
              - total_problems: total number of recorded results
              - total_errors: number of results with errors
              - elapsed_seconds: wall-clock time since metrics creation
        """
        n = len(self.results)
        if n == 0:
            return {"total_problems": 0, "message": "No results recorded."}

        correct_count = sum(1 for r in self.results if r.correct)
        route_counter = Counter(r.route for r in self.results)
        total_latency = sum(r.latency_ms for r in self.results)
        total_llm_calls = sum(r.llm_calls for r in self.results)

        guard_correct = sum(
            1 for r in self.results
            if r.ground_truth_route and r.guard_route == r.ground_truth_route
        )
        guard_total = sum(1 for r in self.results if r.ground_truth_route)

        wrong_results = [r for r in self.results if not r.correct]
        caught = sum(1 for r in wrong_results if not r.verification_passed)
        verification_catch_rate = caught / len(wrong_results) if wrong_results else 0.0

        tool_results = [r for r in self.results if r.tool_used]
        tool_agreed = sum(1 for r in tool_results if r.tool_agreed)

        ece = self._compute_ece()

        by_domain: dict[str, dict[str, int]] = {}
        for r in self.results:
            if not r.domain:
                continue
            bucket = by_domain.setdefault(r.domain, {"correct": 0, "total": 0})
            bucket["total"] += 1
            if r.correct:
                bucket["correct"] += 1

        by_difficulty: dict[str, dict[str, int]] = {}
        for r in self.results:
            if not r.difficulty:
                continue
            bucket = by_difficulty.setdefault(r.difficulty, {"correct": 0, "total": 0})
            bucket["total"] += 1
            if r.correct:
                bucket["correct"] += 1

        return {
            "total_problems": n,
            "total_errors": sum(1 for r in self.results if r.error),
            "pass_at_1": correct_count / n,
            "route_distribution": dict(route_counter),
            "avg_latency_ms": total_latency / n,
            "avg_llm_calls": total_llm_calls / n,
            "guard_accuracy": guard_correct / guard_total if guard_total else None,
            "verification_catch_rate": verification_catch_rate,
            "tool_agreement_rate": tool_agreed / len(tool_results) if tool_results else None,
            "ece": ece,
            "by_domain": {
                d: {**v, "accuracy": v["correct"] / v["total"]}
                for d, v in by_domain.items()
            },
            "by_difficulty": {
                d: {**v, "accuracy": v["correct"] / v["total"]}
                for d, v in by_difficulty.items()
            },
            "elapsed_seconds": time.monotonic() - self._start_time,
        }

    def _compute_ece(self, n_bins: int = 10) -> float:
        """Compute Expected Calibration Error.

        ECE measures how well predicted confidence aligns with actual accuracy.
        Lower is better (0.0 = perfectly calibrated).
        """
        if not self.results:
            return 0.0

        bins: list[list[ProblemResult]] = [[] for _ in range(n_bins)]
        for r in self.results:
            idx = min(int(r.confidence * n_bins), n_bins - 1)
            bins[idx].append(r)

        ece = 0.0
        for bin_results in bins:
            if not bin_results:
                continue
            avg_conf = sum(r.confidence for r in bin_results) / len(bin_results)
            avg_acc = sum(1 for r in bin_results if r.correct) / len(bin_results)
            ece += len(bin_results) / len(self.results) * abs(avg_conf - avg_acc)

        return ece

    def save(self, filename: str) -> None:
        """Save results and summary to a JSON file.

        Args:
            filename: Output file path. Parent directories are created if needed.
        """
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "summary": self.summary(),
            "results": [
                {
                    "problem_id": r.problem_id,
                    "problem": r.problem,
                    "predicted_answer": r.predicted_answer,
                    "expected_answer": r.expected_answer,
                    "correct": r.correct,
                    "route": r.route,
                    "domain": r.domain,
                    "difficulty": r.difficulty,
                    "confidence": r.confidence,
                    "latency_ms": r.latency_ms,
                    "llm_calls": r.llm_calls,
                    "verification_passed": r.verification_passed,
                    "guard_route": r.guard_route,
                    "ground_truth_route": r.ground_truth_route,
                    "tool_used": r.tool_used,
                    "tool_agreed": r.tool_agreed,
                    "error": r.error,
                }
                for r in self.results
            ],
        }

        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved %d results to %s", len(self.results), filename)


class AblationRunner:
    """Runs ablation experiments to measure contribution of each pipeline component.

    Each experiment disables or modifies one component of the pipeline so
    we can quantify its marginal contribution.

    Experiment names:
        no_guard                   — skip the entire guard layer
        guard_no_retrieval         — guard without knowledge retrieval
        guard_no_precompute        — guard without local precompute step
        standard_no_verifier       — standard route without verification
        complex_self_reflection_only — complex route, only self-reflection (no multi-agent)
        full_chain_strict_json     — full pipeline enforcing strict JSON throughout
        control_plane_only_json    — only the control-plane agents use strict JSON
    """

    EXPERIMENTS: list[str] = [
        "no_guard",
        "guard_no_retrieval",
        "guard_no_precompute",
        "standard_no_verifier",
        "complex_self_reflection_only",
        "full_chain_strict_json",
        "control_plane_only_json",
    ]

    def run_experiment(
        self,
        name: str,
        problems: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a single ablation experiment.

        This is a placeholder that returns a structured result. Actual pipeline
        execution will be wired up when the evaluation harness is integrated
        with the live pipeline.

        Args:
            name: Experiment name (must be in EXPERIMENTS).
            problems: List of problem dicts with at least 'problem' and 'expected_answer'.
            config: Optional override config for this experiment.

        Returns:
            dict with experiment name, status, and placeholder metrics.

        Raises:
            ValueError: If experiment name is not recognized.
        """
        if name not in self.EXPERIMENTS:
            raise ValueError(
                f"Unknown experiment '{name}'. Choose from: {self.EXPERIMENTS}"
            )

        logger.info("Ablation experiment '%s' started with %d problems", name, len(problems))

        metrics = PipelineMetrics()

        for _i, _problem in enumerate(problems):
            result = ProblemResult(
                problem_id=f"ablation_{name}_{_i}",
                problem=_problem.get("problem", ""),
                predicted_answer="",
                expected_answer=_problem.get("expected_answer", ""),
                correct=False,
                route=_problem.get("expected_route", "standard"),
            )
            metrics.record(result)

        summary = metrics.summary()

        return {
            "experiment": name,
            "config": config or {},
            "status": "placeholder",
            "note": "Wire up with live pipeline for actual results.",
            "summary": summary,
        }
