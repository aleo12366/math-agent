"""Tests for the adaptive pipeline, routes, and canonicalizer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pipeline.canonicalizer import canonicalize_answer, answers_match
from pipeline.adaptive import AdaptivePipeline


# ── canonicalizer ──────────────────────────────────────────────


class TestCanonicalizeAnswer:
    def test_basic_expression(self):
        result = canonicalize_answer("x^2 + 1", "expression")
        assert "canonical_answer" in result
        assert "equivalent_forms" in result
        assert "comparison_key" in result
        assert isinstance(result["equivalent_forms"], list)
        assert len(result["equivalent_forms"]) >= 1

    def test_number_canonicalization(self):
        result = canonicalize_answer("42", "number")
        assert result["comparison_key"] == "42"

    def test_latex_operators_normalized(self):
        result = canonicalize_answer(r"x \times y", "expression")
        key = result["comparison_key"]
        assert "*" in key or "x" in key

    def test_whitespace_normalized(self):
        result = canonicalize_answer("  x   +   1  ", "expression")
        assert result["comparison_key"] == "x+1"

    def test_dollar_signs_stripped(self):
        result = canonicalize_answer("$x^2$", "expression")
        key = result["comparison_key"]
        assert "$" not in key

    def test_equivalent_forms_populated(self):
        result = canonicalize_answer(r"$x \cdot y$", "expression")
        assert len(result["equivalent_forms"]) >= 1

    def test_empty_string(self):
        result = canonicalize_answer("", "expression")
        assert result["canonical_answer"] is not None
        assert result["comparison_key"] is not None

    def test_latex_leq_geq(self):
        result = canonicalize_answer(r"x \leq 5", "expression")
        key = result["comparison_key"]
        assert "<=" in key


class TestAnswersMatch:
    def test_identical_strings(self):
        assert answers_match("42", "42", "number") is True

    def test_whitespace_difference(self):
        assert answers_match("x + 1", "x+1", "expression") is True

    def test_latex_vs_plain(self):
        assert answers_match("$x^2$", "x^2", "expression") is True

    def test_different_values(self):
        assert answers_match("42", "43", "number") is False

    def test_different_expressions(self):
        assert answers_match("x + 1", "x + 2", "expression") is False

    def test_sympy_equivalent(self):
        # (x+1)^2 and x^2+2x+1 are equivalent
        result = answers_match("(x+1)**2", "x**2 + 2*x + 1", "expression")
        assert result is True

    def test_sympy_not_equivalent(self):
        result = answers_match("x**2", "x**3", "expression")
        assert result is False


# ── adaptive pipeline ─────────────────────────────────────────


class TestAdaptivePipelineInit:
    def test_default_init(self):
        pipeline = AdaptivePipeline()
        assert pipeline.planner is not None
        assert pipeline.solver is not None
        assert pipeline.verifier is not None
        assert pipeline.reflection is not None
        assert pipeline.tool_agent is not None
        assert pipeline.formatter is not None

    def test_stages_total(self):
        pipeline = AdaptivePipeline()
        assert pipeline.stages_total == 9

    def test_has_solve_method(self):
        pipeline = AdaptivePipeline()
        assert hasattr(pipeline, "solve")
        assert callable(pipeline.solve)


# ── simple route ──────────────────────────────────────────────


class TestSimpleRoute:
    @pytest.mark.asyncio
    async def test_simple_route_calls_solver(self):
        from pipeline.routes.simple import route_simple

        mock_solver = AsyncMock()
        mock_solver.run_freeform = AsyncMock(return_value={
            "final_answer": "4",
            "final_answer_latex": "4",
            "reasoning_steps": [{"step_id": 1, "description": "test", "mathematical_expression": "2+2", "result": "4"}],
            "answer_format": "number",
            "raw_response": "2+2=4",
        })

        mock_formatter = MagicMock()
        mock_emit = AsyncMock()
        all_outputs = {}

        ctx = {
            "normalized": {"clean_text": "2+2", "answer_type": "number"},
            "classification": {"domain": "代数", "problem_type": "计算题", "difficulty": "easy"},
        }

        result = await route_simple(
            solver=mock_solver,
            formatter=mock_formatter,
            problem="2+2",
            ctx=ctx,
            config=MagicMock(),
            emit_stage=mock_emit,
            all_outputs=all_outputs,
        )

        mock_solver.run_freeform.assert_called_once()
        assert "solving" in result
        assert result["solving"]["final_answer"] == "4"

    @pytest.mark.asyncio
    async def test_simple_route_emits_stages(self):
        from pipeline.routes.simple import route_simple

        mock_solver = AsyncMock()
        mock_solver.run_freeform = AsyncMock(return_value={
            "final_answer": "5",
            "reasoning_steps": [],
            "answer_format": "number",
            "raw_response": "2+3=5",
        })

        mock_emit = AsyncMock()
        all_outputs = {}

        ctx = {
            "normalized": {"clean_text": "2+3"},
            "classification": {"domain": "代数", "problem_type": "计算题", "difficulty": "easy"},
        }

        await route_simple(
            solver=mock_solver,
            formatter=MagicMock(),
            problem="2+3",
            ctx=ctx,
            config=MagicMock(),
            emit_stage=mock_emit,
            all_outputs=all_outputs,
        )

        assert mock_emit.call_count == 2
        calls = mock_emit.call_args_list
        assert calls[0][0][:2] == ("solving", "started")
        assert calls[1][0][:2] == ("solving", "complete")
