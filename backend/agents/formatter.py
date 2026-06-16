"""Module 8: Formatter agent - assemble final JSON output."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from config.schemas import (
    MathAgentOutput,
    Domain,
    ProblemType,
    Difficulty,
    AnswerFormat,
    VerificationStatus,
    StepStatus,
    PlanStep,
    KeyStep,
    ToolResult,
    VerificationCheck,
    VerificationDetails,
    TokenUsage,
    ErrorLog,
    PipelineMetadata,
    ModuleName,
    ErrorType,
    PipelineMode,
)

logger = logging.getLogger(__name__)


class Formatter:
    """Assembles all module outputs into the final MathAgentOutput JSON.

    This agent does NOT use the LLM. It is pure data assembly.
    """

    def __init__(self):
        self.name = "formatter"

    def format(self, all_outputs: dict, model_name: str = "Intern-S1") -> MathAgentOutput:
        """Assemble all module outputs into the unified MathAgentOutput.

        Args:
            all_outputs: Dict containing outputs from all pipeline stages.
                Expected keys: understanding, classification, knowledge, planning,
                solving, verification, explanation, and optionally reflection.

        Returns:
            MathAgentOutput Pydantic model with all required fields.
        """
        understanding = all_outputs.get("understanding", {})
        classification = all_outputs.get("classification", {})
        knowledge = all_outputs.get("knowledge", {})
        planning = all_outputs.get("planning", {})
        solving = all_outputs.get("solving", {})
        verification = all_outputs.get("verification", {})
        explanation = all_outputs.get("explanation", {})
        reflection = all_outputs.get("reflection", {})
        start_time = all_outputs.get("_start_time", datetime.now())

        # Parse domain
        domain_str = classification.get("domain", "微积分")
        try:
            domain = Domain(domain_str)
        except ValueError:
            domain = Domain.CALCULUS

        # Parse problem type
        ptype_str = classification.get("problem_type", "计算题")
        try:
            problem_type = ProblemType(ptype_str)
        except ValueError:
            problem_type = ProblemType.COMPUTATION

        # Parse difficulty
        diff_str = classification.get("difficulty", "medium")
        try:
            difficulty = Difficulty(diff_str)
        except ValueError:
            difficulty = Difficulty.MEDIUM

        # Parse answer format
        af_str = solving.get("answer_format", "text")
        try:
            answer_format = AnswerFormat(af_str)
        except ValueError:
            answer_format = AnswerFormat.TEXT

        # Parse verification status
        verified = verification.get("verified", False)
        if verified:
            vstatus = VerificationStatus.PASS
        elif verification.get("confidence", 0) > 0.5:
            vstatus = VerificationStatus.UNCERTAIN
        else:
            vstatus = VerificationStatus.FAIL

        # Build PlanStep list
        reasoning_plan = []
        for step in planning.get("steps", []):
            if isinstance(step, dict):
                try:
                    reasoning_plan.append(PlanStep(
                        step_id=step.get("step_id", 1),
                        description=step.get("description", ""),
                        method=step.get("method", ""),
                        expected_outcome=step.get("expected_outcome"),
                        tools_needed=step.get("tools_needed", []),
                        knowledge_applied=step.get("knowledge_applied"),
                    ))
                except Exception as e:
                    logger.warning("Invalid plan step skipped: %s", e)
        key_steps = []
        for step in solving.get("reasoning_steps", []):
            if isinstance(step, dict):
                try:
                    tool_result = None
                    if step.get("tool_result"):
                        tr = step["tool_result"]
                        tool_result = ToolResult(
                            value=tr.get("value"),
                            numeric=tr.get("numeric"),
                            latex=tr.get("latex"),
                        )

                    status_str = step.get("status", "complete")
                    try:
                        status = StepStatus(status_str)
                    except ValueError:
                        status = StepStatus.COMPLETE

                    key_steps.append(KeyStep(
                        step_id=step.get("step_id", 1),
                        description=step.get("description", ""),
                        mathematical_expression=step.get("mathematical_expression", ""),
                        justification=step.get("justification"),
                        result=step.get("result", ""),
                        tool_used=step.get("tool_used"),
                        tool_result=tool_result,
                        status=status,
                    ))
                except Exception as e:
                    logger.warning("Invalid key step skipped: %s", e)
        vdetails = verification.get("details", {})
        def _make_check(name: str) -> VerificationCheck:
            check = vdetails.get(name, {})
            return VerificationCheck(
                passed=check.get("passed", False),
                detail=check.get("detail", "Not checked"),
                score=max(0.0, min(1.0, float(check.get("score", 0.0)))),
            )

        verification_details = VerificationDetails(
            formula_consistency=_make_check("formula_consistency"),
            boundary_conditions=_make_check("boundary_conditions"),
            logical_consistency=_make_check("logical_consistency"),
            special_cases=_make_check("special_cases"),
            dimension_check=_make_check("dimension_check"),
            completeness=_make_check("completeness"),
        )

        # Compute processing time
        end_time = datetime.now()
        processing_ms = int((end_time - start_time).total_seconds() * 1000)
        if processing_ms < 0:
            processing_ms = 0

        # Build token usage estimate
        token_usage = TokenUsage(input=0, output=0, total=0)
        tu = all_outputs.get("token_usage", {})
        if tu:
            token_usage = TokenUsage(
                input=tu.get("input", 0),
                output=tu.get("output", 0),
                total=tu.get("total", 0),
            )

        # Build error logs
        _MODULE_MAP = {
            "understanding": ModuleName.PROBLEM_UNDERSTANDING,
            "classification": ModuleName.CLASSIFIER,
            "knowledge": ModuleName.KNOWLEDGE_LOCATOR,
            "planning": ModuleName.PLANNER,
            "solving": ModuleName.SOLVER,
            "verification": ModuleName.VERIFIER,
            "reflection": ModuleName.REFLECTION,
            "explanation": ModuleName.EXPLAINER,
            "formatting": ModuleName.FORMATTER,
        }
        error_logs = []
        for key, output in all_outputs.items():
            if isinstance(output, dict) and "error" in output:
                error_logs.append(ErrorLog(
                    timestamp=datetime.now(),
                    module=_MODULE_MAP.get(key, ModuleName.FORMATTER),
                    error_type=ErrorType.LLM_ERROR,
                    message=str(output["error"]),
                ))

        # Build metadata
        mode_str = all_outputs.get("_pipeline_mode", "adaptive")
        try:
            mode = PipelineMode(mode_str)
        except ValueError:
            mode = PipelineMode.ADAPTIVE

        metadata = PipelineMetadata(
            model=model_name,
            mode=mode,
            debate_agents=all_outputs.get("_debate_agents", 1),
            retry_count=all_outputs.get("_retry_count", 0),
            created_at=start_time,
        )

        return MathAgentOutput(
            domain=domain,
            problem_type=problem_type,
            difficulty=difficulty,
            difficulty_score=float(classification.get("difficulty_score", 0.5)),
            reasoning_plan=reasoning_plan,
            key_steps=key_steps,
            final_answer=solving.get("final_answer", "No answer"),
            final_answer_latex=solving.get("final_answer_latex"),
            answer_format=answer_format,
            confidence=float(verification.get("confidence", 0.0)),
            verification_status=vstatus,
            verification_details=verification_details,
            educational_explanation=explanation.get("explanation", ""),
            knowledge_points=knowledge.get("knowledge_points", []),
            theorems_applied=knowledge.get("relevant_theorems", []),
            alternative_methods=planning.get("alternative_approaches", []),
            error_logs=error_logs,
            token_usage_estimate=token_usage,
            processing_time_ms=processing_ms,
            pipeline_version="2.0.0",
            metadata=metadata,
        )