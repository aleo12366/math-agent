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


# ── estimate_risk ─────────────────────────────────────────────────


class TestEstimateRisk:
    def _norm_and_graph(self, raw):
        from guard.normalizer import normalize_problem, build_constraint_graph
        norm = normalize_problem(raw)
        graph = build_constraint_graph(norm)
        return norm, graph

    def test_simple_problem(self):
        raw = "计算 2 + 3 的值"
        norm, graph = self._norm_and_graph(raw)
        from guard.complexity import estimate_risk
        result = estimate_risk(norm, graph)
        assert result["complexity_score"] <= 0.3
        assert isinstance(result["risk_tags"], list)
        assert isinstance(result["needs_tool"], bool)
        assert isinstance(result["needs_verifier"], bool)
        assert isinstance(result["answer_shape_certainty"], float)

    def test_complex_pde(self):
        raw = "求解偏微分方程 ∂u/∂t = ∂²u/∂x²，边界条件 u(0,t)=0, u(1,t)=0"
        norm, graph = self._norm_and_graph(raw)
        from guard.complexity import estimate_risk
        result = estimate_risk(norm, graph)
        assert result["complexity_score"] > 0.5
        assert result["needs_tool"] is True

    def test_proof_problem(self):
        raw = "证明：对任意正整数n，1+2+...+n = n(n+1)/2"
        norm, graph = self._norm_and_graph(raw)
        from guard.complexity import estimate_risk
        result = estimate_risk(norm, graph)
        assert result["complexity_score"] > 0.3

    def test_unclear_target_rises_risk(self):
        raw = "讨论函数 f(x) 的性质"
        norm, graph = self._norm_and_graph(raw)
        from guard.complexity import estimate_risk
        result = estimate_risk(norm, graph)
        assert result["complexity_score"] > 0.3
        tags = result["risk_tags"]
        assert "unclear_target" in tags or "uncertain_answer_form" in tags


# ── hybrid_classify ────────────────────────────────────────────────


class TestHybridClassify:
    def test_classify_linear_equation(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("求解 2x + 3 = 7")
        assert result["domain"] in ("代数", "algebra")
        assert "confidence" in result
        assert result["confidence"] > 0

    def test_classify_integral(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("计算定积分 ∫₀¹ x² dx")
        assert result["domain"] in ("微积分", "calculus")
        assert result["confidence"] > 0

    def test_classify_pde(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("求解热方程 u_t = u_xx")
        assert result["domain"] in ("偏微分方程", "PDE")
        assert result["confidence"] > 0

    def test_returns_alternatives(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("求解方程 x^2 - 4 = 0")
        assert "alternatives" in result
        assert isinstance(result["alternatives"], list)

    def test_classify_eigenvalue(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("求矩阵的特征值和特征向量")
        assert result["domain"] in ("线性代数", "linear algebra")
        assert result["confidence"] > 0

    def test_classify_linear_system(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("求解线性方程组 Ax = b")
        assert result["domain"] in ("线性代数", "linear algebra")

    def test_empty_input(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("")
        assert result["domain"] == "未知"
        assert result["confidence"] == 0.0

    def test_has_problem_type(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("计算定积分 ∫₀¹ x² dx")
        assert "problem_type" in result
        assert isinstance(result["problem_type"], str)

    def test_symbols_param_accepted(self):
        from guard.type_matcher import hybrid_classify
        result = hybrid_classify("求解 2x + 3 = 7", symbols=["x", "2", "3", "7"])
        assert result["domain"] in ("代数", "algebra")

    def test_constraints_boost_pde(self):
        from guard.type_matcher import hybrid_classify
        constraints = {"has_pde": True, "has_proof": False}
        result = hybrid_classify("求解 u_t = u_xx", constraints=constraints)
        assert result["domain"] in ("偏微分方程", "PDE")


# ── local_precompute ──────────────────────────────────────────────


class TestLocalPrecompute:
    def _build(self, raw):
        from guard.normalizer import normalize_problem, build_constraint_graph
        from guard.type_matcher import hybrid_classify
        norm = normalize_problem(raw)
        graph = build_constraint_graph(norm)
        classification = hybrid_classify(norm["clean_text"], norm.get("symbols"), graph)
        return graph, classification

    def test_integral_precompute(self):
        """Calculus domain → has symbolic_candidates."""
        from guard.precompute import local_precompute
        raw = "计算定积分 ∫ x^2 dx"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        assert "symbolic_candidates" in result
        assert isinstance(result["symbolic_candidates"], list)
        if result["symbolic_candidates"]:
            assert any(c.get("type") == "indefinite_integral" for c in result["symbolic_candidates"])

    def test_linear_system_precompute(self):
        """Algebra domain → has symbolic_candidates."""
        from guard.precompute import local_precompute
        raw = "求解方程 2*x + 3 = 7"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        assert "symbolic_candidates" in result
        assert isinstance(result["symbolic_candidates"], list)

    def test_empty_graph(self):
        """Empty input → symbolic_candidates == []."""
        from guard.precompute import local_precompute
        graph = {
            "variables": [], "unknowns": [], "knowns": [],
            "domain_constraints": [], "equality_constraints": [],
            "inequality_constraints": [], "boundary_constraints": [],
            "initial_constraints": [], "target": None,
            "answer_shape": "expression", "has_pde": False,
            "has_proof": False, "requires_case_split": False,
            "requires_tool": False,
        }
        classification = {"domain": "未知", "problem_type": "未分类", "confidence": 0.0, "alternatives": []}
        result = local_precompute(graph, classification)
        assert result["symbolic_candidates"] == []

    def test_numeric_sanity_structure(self):
        from guard.precompute import local_precompute
        raw = "求解方程 x + 1 = 3"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        sanity = result["numeric_sanity"]
        assert "has_domain" in sanity
        assert "has_boundary" in sanity
        assert "has_target" in sanity
        assert isinstance(sanity["has_domain"], bool)
        assert isinstance(sanity["has_boundary"], bool)
        assert isinstance(sanity["has_target"], bool)

    def test_numeric_sanity_has_target(self):
        from guard.precompute import local_precompute
        raw = "求解方程 x^2 = 4"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        assert result["numeric_sanity"]["has_target"] is True

    def test_numeric_sanity_no_target(self):
        from guard.precompute import local_precompute
        graph = {
            "variables": [], "unknowns": [], "knowns": [],
            "domain_constraints": [], "equality_constraints": [],
            "inequality_constraints": [], "boundary_constraints": [],
            "initial_constraints": [], "target": None,
            "answer_shape": "expression", "has_pde": False,
            "has_proof": False, "requires_case_split": False,
            "requires_tool": False,
        }
        classification = {"domain": "未知", "problem_type": "未分类", "confidence": 0.0, "alternatives": []}
        result = local_precompute(graph, classification)
        assert result["numeric_sanity"]["has_target"] is False

    def test_verification_hooks_proof(self):
        from guard.precompute import local_precompute
        raw = "证明：对任意正整数n，1+2+...+n = n(n+1)/2"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        hooks = result["verification_hooks"]
        assert isinstance(hooks, list)
        assert any(h.get("type") == "proof_verifier" for h in hooks)

    def test_verification_hooks_case_split(self):
        from guard.precompute import local_precompute
        raw = "讨论参数a对方程 ax^2 + 2x + 1 = 0 解的影响"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        hooks = result["verification_hooks"]
        assert any(h.get("type") == "case_exhaustiveness_check" for h in hooks)

    def test_returns_all_keys(self):
        from guard.precompute import local_precompute
        raw = "计算 2 + 3"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        assert "symbolic_candidates" in result
        assert "numeric_sanity" in result
        assert "verification_hooks" in result

    def test_calculus_domain_triggers_precompute(self):
        from guard.precompute import local_precompute
        raw = "计算 ∫ 3*x^2 dx 的值"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        assert isinstance(result["symbolic_candidates"], list)

    def test_algebra_system_with_equality_constraints(self):
        from guard.precompute import local_precompute
        raw = "求解方程组 {x + y = 3, x - y = 1}"
        graph, classification = self._build(raw)
        result = local_precompute(graph, classification)
        assert "symbolic_candidates" in result
        assert "numeric_sanity" in result
        assert "verification_hooks" in result


# ── CalibratedRouter ───────────────────────────────────────────────


class TestCalibratedRouter:
    def _make_router(self):
        from guard.router import CalibratedRouter
        return CalibratedRouter()

    def test_simple_route(self):
        router = self._make_router()
        features = {
            "type_confidence": 0.95,
            "complexity_score": 0.1,
            "retrieval_score": 0.9,
            "tool_success": 1.0,
        }
        result = router.predict(features)
        assert result["route"] == "simple"
        assert result["n_candidates"] == 1
        assert result["pre_llm_confidence"] > 0.8
        assert isinstance(result["conflict_flags"], list)

    def test_complex_route(self):
        router = self._make_router()
        features = {
            "type_confidence": 0.3,
            "complexity_score": 0.7,
            "retrieval_score": 0.2,
            "tool_success": 0.0,
        }
        result = router.predict(features)
        assert result["route"] in ("complex", "safe_fallback")
        assert result["n_candidates"] == 3

    def test_safe_fallback_on_parse_failure(self):
        router = self._make_router()
        features = {
            "type_confidence": 0.95,
            "complexity_score": 0.1,
            "retrieval_score": 0.9,
            "tool_success": 1.0,
            "guard_parse_failed": True,
        }
        result = router.predict(features)
        assert result["route"] == "safe_fallback"
        assert result["n_candidates"] == 3
        assert "guard_parse_failed" in result["conflict_flags"]

    def test_conflict_detection(self):
        router = self._make_router()
        features = {
            "type_confidence": 0.6,
            "complexity_score": 0.3,
            "top1_top2_method_conflict": True,
        }
        result = router.predict(features)
        assert "method_conflict" in result["conflict_flags"]
        assert result["route"] == "safe_fallback"

    def test_standard_route(self):
        router = self._make_router()
        features = {
            "type_confidence": 0.7,
            "complexity_score": 0.3,
            "retrieval_score": 0.5,
            "tool_success": 0.5,
        }
        result = router.predict(features)
        assert result["route"] == "standard"
        assert result["n_candidates"] == 1

    def test_classification_conflict_triggers_fallback(self):
        router = self._make_router()
        features = {
            "type_confidence": 0.7,
            "complexity_score": 0.3,
            "top1_top2_classification_conflict": True,
        }
        result = router.predict(features)
        assert result["route"] == "safe_fallback"
        assert "classification_conflict" in result["conflict_flags"]
        assert "signal_conflict" in result["conflict_flags"]

    def test_precompute_failure_flag(self):
        router = self._make_router()
        features = {
            "type_confidence": 0.95,
            "complexity_score": 0.1,
            "retrieval_score": 0.9,
            "tool_success": 1.0,
            "precompute_failure": True,
        }
        result = router.predict(features)
        assert "precompute_failure" in result["conflict_flags"]
        assert "signal_conflict" in result["conflict_flags"]
        assert result["route"] == "safe_fallback"

    def test_confidence_blending(self):
        router = self._make_router()
        features = {
            "type_confidence": 1.0,
            "retrieval_score": 1.0,
            "tool_success": 1.0,
        }
        result = router.predict(features)
        assert result["pre_llm_confidence"] == 1.0

    def test_empty_features(self):
        router = self._make_router()
        result = router.predict({})
        assert result["route"] == "complex"
        assert result["pre_llm_confidence"] == 0.0
        assert result["n_candidates"] == 3
        assert result["conflict_flags"] == []


# ── build_presolve_context ─────────────────────────────────────────


class TestBuildPresolveContext:
    def test_returns_all_keys(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("求解方程 x + 1 = 3")
        for key in (
            "problem_id", "raw_problem", "normalized", "constraint_graph",
            "risk", "classification", "retrieval", "precompute", "fusion",
        ):
            assert key in ctx, f"missing key: {key}"

    def test_problem_id_is_uuid(self):
        from guard.context_builder import build_presolve_context
        import uuid
        ctx = build_presolve_context("计算 2 + 3")
        uuid.UUID(ctx["problem_id"])

    def test_raw_problem_preserved(self):
        from guard.context_builder import build_presolve_context
        raw = "求解方程 x^2 - 4 = 0"
        ctx = build_presolve_context(raw)
        assert ctx["raw_problem"] == raw

    def test_normalized_has_clean_text(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("计算 2 + 3")
        assert "clean_text" in ctx["normalized"]

    def test_constraint_graph_has_variables(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("求解方程 x + y = 3")
        assert "variables" in ctx["constraint_graph"]

    def test_risk_has_complexity_score(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("证明：勾股定理")
        assert "complexity_score" in ctx["risk"]
        assert ctx["risk"]["complexity_score"] > 0.3

    def test_classification_has_domain(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("计算定积分 ∫₀¹ x² dx")
        assert ctx["classification"]["domain"] in ("微积分", "calculus")

    def test_precompute_has_candidates(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("求解方程 2*x + 3 = 7")
        assert "symbolic_candidates" in ctx["precompute"]

    def test_fusion_has_route(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("计算 2 + 3")
        assert ctx["fusion"]["route"] in ("simple", "standard", "complex", "safe_fallback")

    def test_retrieval_has_similar_cases(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("计算 2 + 3")
        assert ctx["retrieval"] is not None
        assert "similar_cases" in ctx["retrieval"]
        assert "method_templates" in ctx["retrieval"]

    def test_unique_problem_ids(self):
        from guard.context_builder import build_presolve_context
        ctx1 = build_presolve_context("计算 2 + 3")
        ctx2 = build_presolve_context("计算 2 + 3")
        assert ctx1["problem_id"] != ctx2["problem_id"]

    def test_empty_input(self):
        from guard.context_builder import build_presolve_context
        ctx = build_presolve_context("")
        assert ctx["raw_problem"] == ""
        assert ctx["normalized"]["clean_text"] == ""
        assert ctx["classification"]["domain"] == "未知"


# ── ProblemCache ───────────────────────────────────────────────────


class TestProblemCache:
    def _make_cache(self):
        from guard.cache import ProblemCache
        return ProblemCache()

    def _build_context(self, raw):
        from guard.context_builder import build_presolve_context
        return build_presolve_context(raw)

    def test_set_and_get_same_problem(self):
        cache = self._make_cache()
        ctx = self._build_context("求解方程 x + 1 = 3")
        pid = ctx["problem_id"]
        cache.set(pid, ctx)
        result = cache.get(pid, ctx)
        assert result is ctx

    def test_get_miss_returns_none(self):
        cache = self._make_cache()
        ctx = self._build_context("求解方程 x + 1 = 3")
        result = cache.get("nonexistent", ctx)
        assert result is None

    def test_different_constants_no_reuse(self):
        """Problems with same text but different constants should NOT be reused."""
        cache = self._make_cache()
        ctx1 = self._build_context("求解方程 x + 1 = 3")
        ctx2 = self._build_context("求解方程 x + 1 = 5")
        cache.set(ctx1["problem_id"], ctx1)
        # Different knowns → different constraint signature → reuse_ok=False
        result = cache.get(ctx1["problem_id"], ctx2)
        assert result is None

    def test_same_problem_reuse_ok(self):
        """Identical problems should pass reuse_ok."""
        cache = self._make_cache()
        ctx1 = self._build_context("求解方程 x + 1 = 3")
        ctx2 = self._build_context("求解方程 x + 1 = 3")
        cache.set(ctx1["problem_id"], ctx1)
        result = cache.get(ctx1["problem_id"], ctx2)
        assert result is ctx1

    def test_different_domain_no_reuse(self):
        """Different domain → reuse_ok=False."""
        cache = self._make_cache()
        ctx1 = self._build_context("求解方程 x + 1 = 3")
        ctx2 = self._build_context("求解偏微分方程 ∂u/∂t = ∂²u/∂x²")
        cache.set(ctx1["problem_id"], ctx1)
        result = cache.get(ctx1["problem_id"], ctx2)
        assert result is None

    def test_invalidate(self):
        cache = self._make_cache()
        ctx = self._build_context("计算 2 + 3")
        cache.set(ctx["problem_id"], ctx)
        assert cache.size == 1
        cache.invalidate(ctx["problem_id"])
        assert cache.size == 0

    def test_clear(self):
        cache = self._make_cache()
        ctx1 = self._build_context("计算 2 + 3")
        ctx2 = self._build_context("计算 5 + 7")
        cache.set(ctx1["problem_id"], ctx1)
        cache.set(ctx2["problem_id"], ctx2)
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0

    def test_build_key_deterministic(self):
        from guard.cache import ProblemCache
        ctx = self._build_context("求解方程 x + 1 = 3")
        k1 = ProblemCache.build_key(ctx)
        k2 = ProblemCache.build_key(ctx)
        assert k1 == k2

    def test_build_key_differs_for_different_problems(self):
        from guard.cache import ProblemCache
        ctx1 = self._build_context("求解方程 x + 1 = 3")
        ctx2 = self._build_context("求解方程 x + 1 = 5")
        k1 = ProblemCache.build_key(ctx1)
        k2 = ProblemCache.build_key(ctx2)
        assert k1 != k2

    def test_reuse_ok_static_method(self):
        from guard.cache import ProblemCache
        ctx1 = self._build_context("求解方程 x + 1 = 3")
        ctx2 = self._build_context("求解方程 x + 1 = 3")
        assert ProblemCache.reuse_ok(ctx1, ctx2) is True

    def test_reuse_ok_different_answer_type(self):
        from guard.cache import ProblemCache
        ctx1 = self._build_context("计算 2 + 3")
        ctx2 = self._build_context("证明：勾股定理")
        assert ProblemCache.reuse_ok(ctx1, ctx2) is False

    def test_reuse_ok_different_range(self):
        """Same text, different range constants → reuse_ok=False."""
        from guard.cache import ProblemCache
        ctx1 = self._build_context("在区间 [0, 1] 上求解 sin(x) = 1/2")
        ctx2 = self._build_context("在区间 [0, 2π] 上求解 sin(x) = 1/2")
        assert ProblemCache.reuse_ok(ctx1, ctx2) is False
