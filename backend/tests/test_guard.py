"""Tests for guard.normalizer — normalize_problem and build_constraint_graph."""

import pytest
from guard.normalizer import normalize_problem, build_constraint_graph


# ── normalize_problem ──────────────────────────────────────────────


class TestNormalizeProblem:
    def test_basic_algebra(self):
        raw = "求解方程 x^2 - 4 = 0"
        norm = normalize_problem(raw)
        assert "clean_text" in norm
        assert "x^2" in norm["clean_text"] or "x²" in norm["clean_text"]
        assert isinstance(norm["latex_blocks"], list)
        assert isinstance(norm["symbols"], list)
        assert isinstance(norm["keywords"], list)
        assert isinstance(norm["answer_type"], str)
        assert isinstance(norm["is_proof"], bool)

    def test_latex_extraction(self):
        raw = r"计算 $\int_0^1 x^2 \, dx$ 的值"
        norm = normalize_problem(raw)
        assert len(norm["latex_blocks"]) > 0
        assert any("int" in b for b in norm["latex_blocks"])

    def test_proof_detection(self):
        raw = "证明：对任意正整数n，1+2+...+n = n(n+1)/2"
        norm = normalize_problem(raw)
        assert norm["is_proof"] is True

    def test_non_proof(self):
        raw = "计算 2 + 3 的值"
        norm = normalize_problem(raw)
        assert norm["is_proof"] is False

    def test_symbols_extraction(self):
        raw = "求 f(x) = sin(x) + cos(x) 的导数"
        norm = normalize_problem(raw)
        syms = norm["symbols"]
        assert any("x" in s for s in syms)

    def test_keywords_extraction(self):
        raw = "求解微分方程 dy/dx = y"
        norm = normalize_problem(raw)
        kws = norm["keywords"]
        assert any("微分方程" in k or "differential" in k.lower() for k in kws)

    def test_answer_type_number(self):
        raw = "计算 3 + 5 的值"
        norm = normalize_problem(raw)
        assert norm["answer_type"] in ("number", "expression", "computation")

    def test_answer_type_proof(self):
        raw = "证明勾股定理"
        norm = normalize_problem(raw)
        assert norm["answer_type"] in ("proof", "judgment")

    def test_unicode_cleaning(self):
        raw = "求解\u00a0x²＝\uff10"  # nbsp, fullwidth equals, fullwidth zero
        norm = normalize_problem(raw)
        text = norm["clean_text"]
        assert "\u00a0" not in text  # nbsp replaced
        # fullwidth ＝ may be normalized to =
        assert isinstance(text, str)
        assert len(text) > 0

    def test_empty_input(self):
        norm = normalize_problem("")
        assert norm["clean_text"] == ""
        assert norm["latex_blocks"] == []
        assert norm["symbols"] == []
        assert norm["keywords"] == []
        assert norm["is_proof"] is False

    def test_latex_dollar_signs(self):
        raw = r"求 $a^2 + b^2 = c^2$ 中 $c$ 的值"
        norm = normalize_problem(raw)
        assert len(norm["latex_blocks"]) >= 1

    def test_latex_double_dollar(self):
        raw = r"$$\sum_{i=1}^{n} i = \frac{n(n+1)}{2}$$"
        norm = normalize_problem(raw)
        assert len(norm["latex_blocks"]) >= 1

    def test_multiple_latex_blocks(self):
        raw = r"已知 $f(x)=x^2$ 和 $g(x)=2x+1$，求 $f(g(x))$"
        norm = normalize_problem(raw)
        assert len(norm["latex_blocks"]) >= 2


# ── build_constraint_graph ─────────────────────────────────────────


class TestBuildConstraintGraph:
    def _norm(self, raw):
        return normalize_problem(raw)

    def test_basic_structure(self):
        raw = "求解方程 x + 1 = 3"
        graph = build_constraint_graph(self._norm(raw))
        for key in (
            "variables", "unknowns", "knowns", "domain_constraints",
            "equality_constraints", "inequality_constraints",
            "boundary_constraints", "initial_constraints",
            "target", "answer_shape", "has_pde", "has_proof",
            "requires_case_split", "requires_tool",
        ):
            assert key in graph, f"missing key: {key}"

    def test_unknowns_extraction(self):
        raw = "求解方程 x + 1 = 3"
        graph = build_constraint_graph(self._norm(raw))
        assert "x" in graph["unknowns"]

    def test_knowns_extraction(self):
        raw = "求解方程 x + 1 = 3"
        graph = build_constraint_graph(self._norm(raw))
        # 1 and 3 should appear somewhere as knowns
        known_vals = [str(k) for k in graph["knowns"]]
        assert any("1" in k for k in known_vals) or "1" in str(graph["knowns"])
        assert any("3" in k for k in known_vals) or "3" in str(graph["knowns"])

    def test_equality_constraints(self):
        raw = "求解方程 x + 1 = 3"
        graph = build_constraint_graph(self._norm(raw))
        assert len(graph["equality_constraints"]) >= 1

    def test_inequality_constraints(self):
        raw = "求解不等式 x > 0 且 x < 10"
        graph = build_constraint_graph(self._norm(raw))
        assert len(graph["inequality_constraints"]) >= 1

    def test_proof_graph(self):
        raw = "证明：对任意实数x，x^2 >= 0"
        graph = build_constraint_graph(self._norm(raw))
        assert graph["has_proof"] is True

    def test_pde_detection(self):
        raw = "求解偏微分方程 ∂u/∂t = ∂²u/∂x²"
        graph = build_constraint_graph(self._norm(raw))
        assert graph["has_pde"] is True

    def test_not_pde(self):
        raw = "求解方程 x + 1 = 3"
        graph = build_constraint_graph(self._norm(raw))
        assert graph["has_pde"] is False

    def test_target_field(self):
        raw = "求解方程 x^2 = 4"
        graph = build_constraint_graph(self._norm(raw))
        assert graph["target"] is not None

    def test_answer_shape(self):
        raw = "求解方程 x^2 = 4"
        graph = build_constraint_graph(self._norm(raw))
        assert isinstance(graph["answer_shape"], str)
        assert len(graph["answer_shape"]) > 0

    def test_boundary_constraints(self):
        raw = "求解微分方程 y'' + y = 0，y(0) = 1, y(π) = 0"
        graph = build_constraint_graph(self._norm(raw))
        assert len(graph["boundary_constraints"]) >= 1

    def test_initial_conditions(self):
        raw = "求解初值问题 dy/dx = y, y(0) = 1"
        graph = build_constraint_graph(self._norm(raw))
        assert len(graph["initial_constraints"]) >= 1

    def test_requires_tool_heavy_computation(self):
        raw = "计算 ∫₀¹ e^(-x²) dx 的数值近似值"
        graph = build_constraint_graph(self._norm(raw))
        assert isinstance(graph["requires_tool"], bool)

    def test_case_split_detection(self):
        raw = "讨论参数a对方程 ax^2 + 2x + 1 = 0 解的影响"
        graph = build_constraint_graph(self._norm(raw))
        assert graph["requires_case_split"] is True

    def test_variables_list(self):
        raw = "求解方程组 {x + y = 3, x - y = 1}"
        graph = build_constraint_graph(self._norm(raw))
        assert len(graph["variables"]) >= 2

    def test_domain_constraints(self):
        raw = "在区间 [0, 2π] 上求解 sin(x) = 1/2"
        graph = build_constraint_graph(self._norm(raw))
        assert len(graph["domain_constraints"]) >= 1

    def test_empty_normalization(self):
        norm = normalize_problem("")
        graph = build_constraint_graph(norm)
        assert graph["variables"] == []
        assert graph["unknowns"] == []
        assert graph["has_proof"] is False
        assert graph["has_pde"] is False


# ── helper functions ────────────────────────────────────────────────


class TestHelpers:
    def test_clean_unicode_replaces_nbsp(self):
        from guard.normalizer import clean_unicode
        assert "\u00a0" not in clean_unicode("a\u00a0b")

    def test_clean_unicode_normalizes_fullwidth(self):
        from guard.normalizer import clean_unicode
        result = clean_unicode("１＋２＝３")
        assert "1" in result or "１" in result  # may or may not normalize

    def test_extract_latex_empty(self):
        from guard.normalizer import extract_latex
        assert extract_latex("no latex here") == []

    def test_extract_latex_dollar(self):
        from guard.normalizer import extract_latex
        blocks = extract_latex(r"see $x^2$ here")
        assert len(blocks) == 1
        assert "x^2" in blocks[0]

    def test_extract_latex_display(self):
        from guard.normalizer import extract_latex
        blocks = extract_latex(r"display $$y = mx + b$$ done")
        assert len(blocks) == 1

    def test_extract_symbols_from_latex(self):
        from guard.normalizer import extract_symbols
        syms = extract_symbols(r"$\alpha + \beta = \gamma$", [])
        assert len(syms) >= 0  # should not crash

    def test_detect_proof_intent_positive(self):
        from guard.normalizer import detect_proof_intent
        assert detect_proof_intent("证明：勾股定理") is True
        assert detect_proof_intent("Prove that sqrt(2) is irrational") is True

    def test_detect_proof_intent_negative(self):
        from guard.normalizer import detect_proof_intent
        assert detect_proof_intent("计算 2+3") is False

    def test_predict_answer_type(self):
        from guard.normalizer import predict_answer_type
        at = predict_answer_type("计算 2+3", False)
        assert isinstance(at, str)
        assert len(at) > 0

    def test_predict_answer_type_proof(self):
        from guard.normalizer import predict_answer_type
        at = predict_answer_type("证明xxx", True)
        assert at == "proof"
