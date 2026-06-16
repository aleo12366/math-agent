"""Evaluation framework for the adaptive math agent pipeline.

Provides metrics collection (PipelineMetrics) and ablation experiment
runner (AblationRunner) for measuring guard quality, end-to-end accuracy,
anti-hallucination, calibration, and efficiency.
"""

from .metrics import PipelineMetrics, AblationRunner

__all__ = ["PipelineMetrics", "AblationRunner"]
