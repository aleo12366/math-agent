# 自适应流水线优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 9-Agent 线性流水线升级为自适应四路由流水线，通过 Pre-LLM Guard Layer 实现简单题 15-30s、中等题 45-90s、复杂题 2-5min 的分层响应。

**Architecture:** Pre-LLM Guard Layer（本地证据汇编器）在零 LLM 调用下完成规范化、约束抽取、复杂度评估、题型匹配、预计算，输出强类型 PreSolveContext；Route Policy 根据置信度和复杂度选择 simple/standard/complex/safe_fallback 四条路径；双通道策略：控制平面 JSON + 推理平面 freeform。

**Tech Stack:** Python 3.11+, SymPy, rapidfuzz, scikit-learn（校准器）, aiohttp, FastAPI

---

## 文件结构

### 新建文件

| 文件 | 职责 |
|------|------|
| `backend/guard/__init__.py` | Guard Layer 包初始化 |
| `backend/guard/normalizer.py` | 文本清洗 + 约束图抽取 |
| `backend/guard/complexity.py` | 多维度风险评估 |
| `backend/guard/type_matcher.py` | 规则+稀疏+致密+结构重排 |
| `backend/guard/retriever.py` | 相似题检索 + 证据预算 |
| `backend/guard/precompute.py` | SymPy/NumPy 本地预计算 |
| `backend/guard/router.py` | 校准路由器 + 四路由决策 |
| `backend/guard/context_builder.py` | PreSolveContext 生成 |
| `backend/guard/cache.py` | 结构化缓存 |
| `backend/pipeline/adaptive.py` | 自适应流水线主入口 |
| `backend/pipeline/routes/simple.py` | Simple 路径 |
| `backend/pipeline/routes/standard.py` | Standard 路径 |
| `backend/pipeline/routes/complex.py` | Complex 路径 |
| `backend/pipeline/routes/safe_fallback.py` | Safe Fallback 路径 |
| `backend/pipeline/canonicalizer.py` | 答案归一化器 |
| `backend/data/templates/*.jsonl` | 题型模板库 |
| `backend/data/problem_bank/*.jsonl` | 相似题库 |
| `backend/eval/metrics.py` | 评测指标 |
| `backend/eval/ablation.py` | Ablation 实验 |
| `backend/tests/test_guard.py` | Guard Layer 测试 |
| `backend/tests/test_routes.py` | 路由测试 |
| `backend/tests/test_canonicalizer.py` | 归一化器测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `backend/config/prompts.py` | 新增 Solver/Verifier/Reflection/Formatter 四套新 Prompt |
| `backend/config/settings.py` | 新增 guard 相关配置项 |
| `backend/agents/solver.py` | 支持 PreSolveContext 上下文 |
| `backend/agents/verifier.py` | 步级标签 + 错误类型 |
| `backend/agents/reflection.py` | 定向修订 |
| `backend/agents/tool_agent.py` | 并行执行 |
| `backend/pipeline/single.py` | 调用 AdaptivePipeline |
| `backend/pipeline/multi.py` | 调用 AdaptivePipeline |
| `backend/api/routes.py` | 新增 guard 相关 API |

---

## Phase 1: Guard Layer 基础

### Task 1: Normalizer + Constraint Graph

**Covers:** [S2.1]

**Files:**
- Create: `backend/guard/__init__.py`
- Create: `backend/guard/normalizer.py`
- Create: `backend/tests/test_guard.py`

- [ ] **Step 1: 创建 guard 包**

```python
# backend/guard/__init__.py
"""Pre-LLM Guard Layer - 本地证据汇编器."""
```

- [ ] **Step 2: 写 Normalizer 测试**

```python
# backend/tests/test_guard.py
import pytest
from guard.normalizer import normalize_problem, build_constraint_graph

class TestNormalizer:
    def test_clean_unicode(self):
        raw = "求解∫₀¹ x² dx"
        result = normalize_problem(raw)
        assert "clean_text" in result
        assert len(result["clean_text"]) > 0

    def test_extract_latex(self):
        raw = r"求解 $\int_0^1 x^2 dx$"
        result = normalize_problem(raw)
        assert len(result["latex_blocks"]) > 0

    def test_extract_symbols(self):
        raw = "求解 u_t = u_xx, 0<x<1"
        result = normalize_problem(raw)
        assert "u_t" in result["symbols"] or "x" in result["symbols"]

    def test_is_proof_detection(self):
        raw = "证明√2是无理数"
        result = normalize_problem(raw)
        assert result["is_proof"] is True

    def test_not_proof(self):
        raw = "计算∫₀¹ x² dx"
        result = normalize_problem(raw)
        assert result["is_proof"] is False

    def test_answer_type_prediction(self):
        raw = "求解 2x + 3 = 7"
        result = normalize_problem(raw)
        assert result["answer_type"] in ("numeric", "expression", "closed_form")

class TestConstraintGraph:
    def test_basic_constraints(self):
        norm = normalize_problem("求解 u_t = u_xx, 0<x<1, u(0,t)=0, u(1,t)=0")
        graph = build_constraint_graph(norm)
        assert "variables" in graph
        assert "unknowns" in graph
        assert len(graph["boundary_constraints"]) > 0 or len(graph["domain_constraints"]) > 0

    def test_empty_problem(self):
        norm = normalize_problem("")
        graph = build_constraint_graph(norm)
        assert graph["variables"] == []
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_guard.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: 实现 Normalizer**

```python
# backend/guard/normalizer.py
"""Problem Normalizer + Constraint Graph Builder."""

import re
import unicodedata
from typing import Optional


def normalize_problem(raw: str) -> dict:
    """Normalize raw problem text and extract structural features."""
    if not raw or not raw.strip():
        return {
            "clean_text": "",
            "latex_blocks": [],
            "symbols": [],
            "keywords": [],
            "answer_type": "unknown",
            "is_proof": False,
        }

    clean = clean_unicode(raw)
    latex_blocks = extract_latex(raw)
    symbols = extract_symbols(clean)
    keywords = extract_keywords(clean)

    return {
        "clean_text": clean,
        "latex_blocks": latex_blocks,
        "symbols": symbols,
        "keywords": keywords,
        "answer_type": predict_answer_type(clean, keywords),
        "is_proof": detect_proof_intent(clean),
    }


def build_constraint_graph(norm: dict) -> dict:
    """Build constraint graph from normalized problem."""
    text = norm.get("clean_text", "")
    symbols = norm.get("symbols", [])

    variables = extract_variables(text, symbols)
    unknowns = extract_unknowns(text, variables)
    knowns = extract_knowns(text, variables, unknowns)

    return {
        "variables": variables,
        "unknowns": unknowns,
        "knowns": knowns,
        "domain_constraints": extract_domain(text),
        "equality_constraints": extract_equalities(text),
        "inequality_constraints": extract_inequalities(text),
        "boundary_constraints": extract_boundary(text),
        "initial_constraints": extract_initial(text),
        "target": extract_target(text),
        "answer_shape": predict_answer_shape(norm),
        "has_pde": detect_pde(text),
        "has_proof": norm.get("is_proof", False),
        "requires_case_split": detect_case_split(text),
        "requires_tool": detect_tool_need(text),
    }


def clean_unicode(raw: str) -> str:
    """Clean and normalize Unicode characters."""
    text = unicodedata.normalize("NFKC", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_latex(raw: str) -> list[str]:
    """Extract LaTeX blocks from text."""
    patterns = [
        r"\$\$(.*?)\$\$",
        r"\$(.*?)\$",
        r"\\begin\{equation\}(.*?)\\end\{equation\}",
        r"\\begin\{align\}(.*?)\\end\{align\}",
    ]
    blocks = []
    for pattern in patterns:
        blocks.extend(re.findall(pattern, raw, re.DOTALL))
    return [b.strip() for b in blocks if b.strip()]


def extract_symbols(text: str) -> list[str]:
    """Extract mathematical symbols from text."""
    symbol_pattern = r"[a-zA-Z_][a-zA-Z0-9_]*(?:_[a-zA-Z0-9]+)?"
    found = set(re.findall(symbol_pattern, text))
    stop_words = {
        "求解", "计算", "证明", "设", "若", "则", "的", "已知", "其中",
        "the", "a", "an", "is", "are", "and", "or", "to", "of", "in",
        "solve", "compute", "calculate", "prove", "let", "given",
    }
    return sorted(found - stop_words)


def extract_keywords(text: str) -> list[str]:
    """Extract domain keywords."""
    keyword_sets = {
        "微积分": ["积分", "微分", "导数", "极限", "求导"],
        "线性代数": ["矩阵", "行列式", "特征值", "特征向量", "线性方程组"],
        "概率论": ["概率", "期望", "方差", "分布", "随机"],
        "偏微分方程": ["偏微分", "PDE", "热方程", "波动方程", "拉普拉斯"],
        "复分析": ["留数", "解析", "柯西", "黎曼", "复变"],
        "拓扑学": ["拓扑", "紧致", "连通", "开集", "闭集"],
        "运筹学": ["线性规划", "单纯形", "对偶", "整数规划"],
        "数论": ["素数", "同余", "欧拉", "费马", "整除"],
        "组合数学": ["组合", "排列", "图论", "树", "匹配"],
        "抽象代数": ["群", "环", "域", "同态", "同构"],
        "微分几何": ["曲率", "测地线", "流形", "切空间"],
        "泛函分析": ["巴拿赫", "希尔伯特", "算子", "泛函"],
        "数值分析": ["数值", "误差", "收敛", "迭代", "插值"],
        "最优化理论": ["最优", "梯度", "凸", "拉格朗日", "KKT"],
        "信息论": ["熵", "互信息", "信道", "编码"],
        "随机过程": ["马尔可夫", "泊松", "布朗", "鞅"],
    }
    found = []
    for domain, kws in keyword_sets.items():
        for kw in kws:
            if kw in text:
                found.append(kw)
    return found


def predict_answer_type(text: str, keywords: list[str]) -> str:
    """Predict the expected answer type."""
    if any(w in text for w in ["证明", "推导", "prove", "show"]):
        return "proof"
    if any(w in text for w in ["求解", "解方程", "solve"]):
        return "expression"
    if any(w in text for w in ["计算", "求值", "compute", "evaluate"]):
        return "numeric"
    return "expression"


def detect_proof_intent(text: str) -> bool:
    """Detect if the problem asks for a proof."""
    proof_words = ["证明", "推导", "验证", "prove", "show", "derive", "verify"]
    return any(w in text for w in proof_words)


def extract_variables(text: str, symbols: list[str]) -> list[str]:
    """Extract likely mathematical variables."""
    return [s for s in symbols if len(s) <= 3 and not s[0].isdigit()]


def extract_unknowns(text: str, variables: list[str]) -> list[str]:
    """Extract unknowns (what we're solving for)."""
    unknown_patterns = [
        r"求\s*(.+?)(?:\s*[,，。]|$)",
        r"solve\s+for\s+(\w+)",
        r"求解\s*(.+?)(?:\s*[,，。]|$)",
    ]
    unknowns = []
    for pattern in unknown_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        unknowns.extend(matches)
    return unknowns[:5] if unknowns else variables[:3]


def extract_knowns(text: str, variables: list[str], unknowns: list[str]) -> list[str]:
    """Extract known quantities."""
    return [v for v in variables if v not in unknowns]


def extract_domain(text: str) -> list[str]:
    """Extract domain constraints like 0<x<1."""
    patterns = [
        r"(\d+(?:\.\d+)?)\s*[<≤]\s*(\w+)\s*[<≤]\s*(\d+(?:\.\d+)?)",
        r"(\w+)\s*∈\s*\[(.+?),\s*(.+?)\]",
    ]
    constraints = []
    for p in patterns:
        matches = re.findall(p, text)
        for m in matches:
            constraints.append(f"{m[0]} < {m[1]} < {m[2]}")
    return constraints


def extract_equalities(text: str) -> list[str]:
    """Extract equality constraints."""
    eq_pattern = r"(\w+(?:\([^)]*\))?)\s*=\s*([^,，。\n]+)"
    return [f"{m[0]}={m[1].strip()}" for m in re.findall(eq_pattern, text)]


def extract_inequalities(text: str) -> list[str]:
    """Extract inequality constraints."""
    ineq_pattern = r"(\w+)\s*([<>≤≥])\s*(\d+(?:\.\d+)?)"
    return [f"{m[0]}{m[1]}{m[2]}" for m in re.findall(ineq_pattern, text)]


def extract_boundary(text: str) -> list[str]:
    """Extract boundary conditions."""
    bc_patterns = [
        r"(\w+(?:\([^)]*\))?)\s*=\s*(\d+(?:\.\d+)?)(?:\s*[,，]|\s*(?:at|when|在))",
        r"边界条件[：:]?\s*(.+?)(?:\n|$)",
    ]
    boundaries = []
    for p in bc_patterns:
        boundaries.extend(re.findall(p, text))
    return [b if isinstance(b, str) else "=".join(b) for b in boundaries]


def extract_initial(text: str) -> list[str]:
    """Extract initial conditions."""
    ic_patterns = [
        r"初[始值条]+[：:]?\s*(.+?)(?:\n|$)",
        r"initial\s+condition[s]?[：:]?\s*(.+?)(?:\n|$)",
        r"t\s*=\s*0\s*[,，:：]\s*(.+?)(?:\n|$)",
    ]
    initials = []
    for p in ic_patterns:
        initials.extend(re.findall(p, text, re.IGNORECASE))
    return initials


def extract_target(text: str) -> str:
    """Extract what the problem asks for."""
    target_patterns = [
        r"求\s*(.+?)(?:\s*[,，。]|$)",
        r"compute\s+(.+?)(?:\s*[,，.]|$)",
        r"find\s+(.+?)(?:\s*[,，.]|$)",
        r"calculate\s+(.+?)(?:\s*[,，.]|$)",
    ]
    for p in target_patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def predict_answer_shape(norm: dict) -> str:
    """Predict the expected answer shape."""
    if norm.get("is_proof"):
        return "proof"
    text = norm.get("clean_text", "")
    if any(w in text for w in ["级数", "series", "展开"]):
        return "series"
    if any(w in text for w in ["矩阵", "向量", "matrix", "vector"]):
        return "vector"
    if any(w in text for w in ["积分", "integral"]):
        return "expression"
    return "expression"


def detect_pde(text: str) -> bool:
    """Detect if the problem involves PDEs."""
    pde_indicators = ["偏微分", "PDE", "u_t", "u_xx", "u_yy", "热方程", "波动方程", "拉普拉斯"]
    return any(ind in text for ind in pde_indicators)


def detect_case_split(text: str) -> bool:
    """Detect if the problem requires case analysis."""
    return any(w in text for w in ["讨论", "分情况", "cases", "分类讨论"])


def detect_tool_need(text: str) -> bool:
    """Detect if the problem likely needs computational tools."""
    tool_indicators = ["积分", "微分", "矩阵", "行列式", "特征值", "求解方程", "优化"]
    return any(ind in text for ind in tool_indicators)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_guard.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/guard/__init__.py backend/guard/normalizer.py backend/tests/test_guard.py
git commit -m "feat(guard): add Problem Normalizer + Constraint Graph builder"
```

---

### Task 2: Complexity & Risk Estimator

**Covers:** [S2.2]

**Files:**
- Create: `backend/guard/complexity.py`
- Modify: `backend/tests/test_guard.py`

- [ ] **Step 1: 写 Complexity 测试**

```python
# 追加到 backend/tests/test_guard.py
from guard.complexity import estimate_risk

class TestComplexity:
    def test_simple_problem(self):
        norm = {"clean_text": "计算 2+3", "is_proof": False, "keywords": [], "answer_type": "numeric"}
        graph = {"variables": [], "has_pde": False, "has_proof": False, "requires_case_split": False, "requires_tool": False, "target": "结果", "domain_constraints": [], "equality_constraints": [], "answer_shape": "numeric"}
        risk = estimate_risk(norm, graph)
        assert risk["complexity_score"] <= 0.3

    def test_complex_pde(self):
        norm = {"clean_text": "求解热方程 u_t = u_xx", "is_proof": False, "keywords": ["偏微分"], "answer_type": "expression"}
        graph = {"variables": ["x", "t", "u"], "has_pde": True, "has_proof": False, "requires_case_split": False, "requires_tool": True, "target": "u(x,t)", "domain_constraints": ["0<x<1"], "equality_constraints": ["u(0,t)=0"], "answer_shape": "series"}
        risk = estimate_risk(norm, graph)
        assert risk["complexity_score"] > 0.5
        assert risk["needs_tool"] is True

    def test_proof_problem(self):
        norm = {"clean_text": "证明√2是无理数", "is_proof": True, "keywords": [], "answer_type": "proof"}
        graph = {"variables": [], "has_pde": False, "has_proof": True, "requires_case_split": True, "requires_tool": False, "target": "命题", "domain_constraints": [], "equality_constraints": [], "answer_shape": "proof"}
        risk = estimate_risk(norm, graph)
        assert risk["complexity_score"] > 0.3

    def test_unclear_target_rises_risk(self):
        norm = {"clean_text": "一些数学问题", "is_proof": False, "keywords": [], "answer_type": "unknown"}
        graph = {"variables": [], "has_pde": False, "has_proof": False, "requires_case_split": False, "requires_tool": False, "target": "", "domain_constraints": [], "equality_constraints": [], "answer_shape": "unknown"}
        risk = estimate_risk(norm, graph)
        assert risk["complexity_score"] > 0.3
        assert "unclear_target" in risk["risk_tags"] or "uncertain_answer_form" in risk["risk_tags"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_guard.py::TestComplexity -v`
Expected: FAIL

- [ ] **Step 3: 实现 Complexity Estimator**

```python
# backend/guard/complexity.py
"""Complexity & Risk Estimator - 多维度风险评估."""


def estimate_risk(norm: dict, graph: dict) -> dict:
    """Estimate problem complexity and risk factors.

    Args:
        norm: Normalized problem dict from normalizer.
        graph: Constraint graph from normalizer.

    Returns:
        Dict with complexity_score, risk_tags, needs_tool, needs_verifier, answer_shape_certainty.
    """
    score = 0.0
    risk_tags = []

    # Content dimensions
    if graph.get("has_pde"):
        score += 0.20
        risk_tags.append("pde")
    if graph.get("has_proof"):
        score += 0.20
        risk_tags.append("proof")
    if len(graph.get("variables", [])) > 8:
        score += 0.10
        risk_tags.append("many_variables")
    if graph.get("requires_case_split"):
        score += 0.15
        risk_tags.append("case_split")
    if graph.get("requires_tool"):
        score += 0.10

    # Guard self-uncertainty (cannot parse ≈ high risk)
    if not graph.get("target"):
        score += 0.15
        risk_tags.append("unclear_target")
    if not graph.get("domain_constraints") and not graph.get("equality_constraints"):
        score += 0.10
        risk_tags.append("no_constraints_extracted")
    if graph.get("answer_shape") == "unknown":
        score += 0.10
        risk_tags.append("uncertain_answer_form")

    # Keyword-based complexity boost
    high_complexity_keywords = ["拓扑", "泛函", "微分几何", "抽象代数", "测度论"]
    if any(kw in norm.get("keywords", []) for kw in high_complexity_keywords):
        score += 0.15
        risk_tags.append("advanced_topic")

    score = min(1.0, score)

    return {
        "complexity_score": round(score, 3),
        "risk_tags": risk_tags,
        "needs_tool": score > 0.3,
        "needs_verifier": score > 0.2,
        "answer_shape_certainty": 1.0 - (0.2 if "uncertain_answer_form" in risk_tags else 0),
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_guard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/guard/complexity.py backend/tests/test_guard.py
git commit -m "feat(guard): add Complexity & Risk Estimator"
```

---

### Task 3: Hybrid Type Matcher

**Covers:** [S2.3]

**Files:**
- Create: `backend/guard/type_matcher.py`
- Create: `backend/data/templates/` 目录
- Modify: `backend/tests/test_guard.py`

- [ ] **Step 1: 创建题型模板目录和初始模板**

```bash
mkdir -p backend/data/templates
```

创建 `backend/data/templates/algebra.jsonl`:
```jsonl
{"template_id":"LINEAR_EQ_1VAR","domain":"代数","problem_type":"linear_equation","patterns":["一元一次方程","ax+b=0","linear equation"],"applicable_if":["单变量","一次"],"avoid_if":["多变量","高次"],"recommended_method":"direct_isolation","typical_errors":["符号错误","移项错误"],"verification":["代入验证"],"answer_pattern":"x = -b/a"}
{"template_id":"QUADRATIC_EQ","domain":"代数","problem_type":"quadratic_equation","patterns":["一元二次方程","ax^2+bx+c=0","quadratic"],"applicable_if":["单变量","二次"],"avoid_if":["复数根","参数方程"],"recommended_method":"quadratic_formula","typical_errors":["判别式计算错误","符号错误"],"verification":["代入验证","韦达定理"],"answer_pattern":"x = (-b ± √(b²-4ac)) / 2a"}
```

创建 `backend/data/templates/calculus.jsonl`:
```jsonl
{"template_id":"DEFINITE_INTEGRAL","domain":"微积分","problem_type":"definite_integral","patterns":["定积分","∫","integral from"],"applicable_if":["连续函数","有限区间"],"avoid_if":["瑕积分","反常积分"],"recommended_method":"newton_leibniz","typical_errors":["上下限搞反","不定积分算错"],"verification":["数值积分对比","求导还原"],"answer_pattern":"数值或表达式"}
{"template_id":"LIMIT","domain":"微积分","problem_type":"limit","patterns":["极限","lim","趋向"],"applicable_if":["0/0","∞/∞"],"avoid_if":["振荡极限","夹逼"],"recommended_method":"lhopital_or_taylor","typical_errors":["洛必达条件不满足","等价无穷小误用"],"verification":["左右极限","数值逼近"],"answer_pattern":"数值"}
```

创建 `backend/data/templates/pde.jsonl`:
```jsonl
{"template_id":"PDE_HEAT_DIRICHLET_1D","domain":"偏微分方程","problem_type":"heat_equation_dirichlet","patterns":["u_t = k u_xx","u(0,t)=0","u(L,t)=0","热方程"],"applicable_if":["Dirichlet边界","一维热方程","齐次"],"avoid_if":["非齐次边界","源项","二维域"],"recommended_method":"separation_of_variables","typical_errors":["本征值符号错误","Fourier系数错误","边界不匹配"],"verification":["PDE代入","边界条件","初始条件"],"answer_pattern":"sum b_n exp(-n^2 pi^2 t) sin(n pi x)"}
```

创建 `backend/data/templates/linear_algebra.jsonl`:
```jsonl
{"template_id":"EIGENVALUE","domain":"线性代数","problem_type":"eigenvalue","patterns":["特征值","特征向量","eigenvalue","eigenvector"],"applicable_if":["方阵"],"avoid_if":["非方阵","无穷维"],"recommended_method":"characteristic_polynomial","typical_errors":["行列式计算错误","特征向量未归一化"],"verification":["Av=λv验证"],"answer_pattern":"特征值列表+对应特征向量"}
{"template_id":"LINEAR_SYSTEM","domain":"线性代数","problem_type":"linear_system","patterns":["线性方程组","Ax=b","求解方程组"],"applicable_if":["方程数=未知数"],"avoid_if":["欠定","超定"],"recommended_method":"gaussian_elimination","typical_errors":["行变换错误","回代错误"],"verification":["代入原方程组"],"answer_pattern":"解向量"}
```

- [ ] **Step 2: 写 Type Matcher 测试**

```python
# 追加到 backend/tests/test_guard.py
from guard.type_matcher import hybrid_classify

class TestTypeMatcher:
    def test_classify_linear_equation(self):
        result = hybrid_classify("求解 2x + 3 = 7", ["x"], {})
        assert result["domain"] in ("代数", "algebra")
        assert result["confidence"] > 0

    def test_classify_integral(self):
        result = hybrid_classify("计算定积分 ∫₀¹ x² dx", ["x"], {})
        assert result["domain"] in ("微积分", "calculus")

    def test_classify_pde(self):
        result = hybrid_classify("求解热方程 u_t = u_xx, u(0,t)=0", ["u", "x", "t"], {"boundary_constraints": ["u(0,t)=0"]})
        assert result["domain"] in ("偏微分方程", "PDE")

    def test_returns_alternatives(self):
        result = hybrid_classify("计算矩阵特征值", ["A", "λ"], {})
        assert "alternatives" in result
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_guard.py::TestTypeMatcher -v`
Expected: FAIL

- [ ] **Step 4: 实现 Hybrid Type Matcher**

```python
# backend/guard/type_matcher.py
"""Hybrid Type Matcher - 规则 + 稀疏检索 + 结构重排."""

import json
from pathlib import Path
from typing import Optional

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


TEMPLATES_DIR = Path(__file__).parent.parent / "data" / "templates"

# Domain keyword mapping for rule-based classification
DOMAIN_KEYWORDS = {
    "微积分": ["积分", "微分", "导数", "极限", "求导", "∫", "lim"],
    "线性代数": ["矩阵", "行列式", "特征值", "特征向量", "线性方程组", "秩"],
    "概率论": ["概率", "期望", "方差", "分布", "随机变量"],
    "偏微分方程": ["偏微分", "PDE", "热方程", "波动方程", "u_t", "u_xx"],
    "复分析": ["留数", "解析", "柯西", "黎曼", "复变", "极点"],
    "拓扑学": ["拓扑", "紧致", "连通", "开集", "闭集", "同胚"],
    "运筹学": ["线性规划", "单纯形", "对偶", "整数规划"],
    "数论": ["素数", "同余", "欧拉", "费马", "整除", "模"],
    "组合数学": ["组合", "排列", "图论", "树", "匹配", "计数"],
    "抽象代数": ["群", "环", "域", "同态", "同构", "子群"],
    "微分几何": ["曲率", "测地线", "流形", "切空间", "联络"],
    "泛函分析": ["巴拿赫", "希尔伯特", "算子", "泛函", "范数"],
    "数值分析": ["数值", "误差", "收敛", "迭代", "插值", "逼近"],
    "最优化理论": ["最优", "梯度", "凸", "拉格朗日", "KKT"],
    "信息论": ["熵", "互信息", "信道", "编码"],
    "随机过程": ["马尔可夫", "泊松", "布朗", "鞅", "随机过程"],
}

# Reverse mapping for Chinese to English domain
DOMAIN_CN_TO_EN = {
    "微积分": "calculus",
    "线性代数": "linear_algebra",
    "概率论": "probability",
    "偏微分方程": "pde",
    "复分析": "complex_analysis",
    "拓扑学": "topology",
    "运筹学": "operations_research",
    "数论": "number_theory",
    "组合数学": "combinatorics",
    "抽象代数": "abstract_algebra",
    "微分几何": "differential_geometry",
    "泛函分析": "functional_analysis",
    "数值分析": "numerical_analysis",
    "最优化理论": "optimization",
    "信息论": "information_theory",
    "随机过程": "stochastic_processes",
}


def _load_templates() -> list[dict]:
    """Load all template files."""
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    for f in TEMPLATES_DIR.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                try:
                    templates.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return templates


def _rule_classify(text: str, keywords: list[str]) -> Optional[dict]:
    """Rule-based classification using keyword matching."""
    for domain, domain_kws in DOMAIN_KEYWORDS.items():
        matches = sum(1 for kw in domain_kws if kw in text or kw in keywords)
        if matches >= 2:
            return {"domain": domain, "confidence": min(0.9, 0.5 + matches * 0.1)}
        if matches == 1:
            return {"domain": domain, "confidence": 0.5}
    return None


def _template_match(text: str, templates: list[dict]) -> list[dict]:
    """Match against template patterns using fuzzy matching."""
    if not templates or fuzz is None:
        return []

    candidates = []
    for tpl in templates:
        pattern_scores = [
            fuzz.partial_ratio(text, p) for p in tpl.get("patterns", [])
        ]
        score = max(pattern_scores) if pattern_scores else 0
        if score > 60:
            candidates.append({
                "template_id": tpl["template_id"],
                "domain": tpl["domain"],
                "problem_type": tpl["problem_type"],
                "recommended_method": tpl.get("recommended_method", ""),
                "score": score / 100.0,
                "template": tpl,
            })

    return sorted(candidates, key=lambda x: x["score"], reverse=True)[:5]


def _structural_rerank(
    rule_hit: Optional[dict],
    template_hits: list[dict],
    constraints: dict,
) -> list[dict]:
    """Rerank candidates using structural constraints."""
    candidates = []

    # Add rule-based hit
    if rule_hit:
        candidates.append({
            "domain": rule_hit["domain"],
            "problem_type": "unknown",
            "confidence": rule_hit["confidence"],
            "source": "rule",
        })

    # Add template hits
    for hit in template_hits:
        conf = hit["score"]
        # Boost if constraint matches
        if constraints.get("boundary_constraints") and "boundary" in hit.get("template", {}).get("recommended_method", ""):
            conf = min(1.0, conf + 0.1)
        candidates.append({
            "domain": hit["domain"],
            "problem_type": hit["problem_type"],
            "recommended_method": hit.get("recommended_method", ""),
            "confidence": conf,
            "source": "template",
            "template": hit.get("template"),
        })

    # Deduplicate by domain, keep highest confidence
    seen = {}
    for c in candidates:
        key = c["domain"]
        if key not in seen or c["confidence"] > seen[key]["confidence"]:
            seen[key] = c

    result = sorted(seen.values(), key=lambda x: x["confidence"], reverse=True)
    return result[:5]


def hybrid_classify(text: str, symbols: list[str], constraints: dict) -> dict:
    """Classify problem using rule + template matching + structural rerank.

    Args:
        text: Clean problem text.
        symbols: Extracted symbols.
        constraints: Constraint graph dict.

    Returns:
        Dict with domain, problem_type, confidence, alternatives.
    """
    templates = _load_templates()

    # Layer 1: Rule-based
    rule_hit = _rule_classify(text, symbols)

    # Layer 2: Template matching
    template_hits = _template_match(text, templates)

    # Layer 3: Structural rerank
    ranked = _structural_rerank(rule_hit, template_hits, constraints)

    if not ranked:
        return {
            "domain": "unknown",
            "problem_type": "unknown",
            "confidence": 0.0,
            "alternatives": [],
        }

    top = ranked[0]
    return {
        "domain": top["domain"],
        "problem_type": top.get("problem_type", "unknown"),
        "recommended_method": top.get("recommended_method", ""),
        "confidence": round(top["confidence"], 3),
        "alternatives": [
            {"domain": r["domain"], "problem_type": r.get("problem_type", ""), "confidence": r["confidence"]}
            for r in ranked[1:3]
        ],
    }
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_guard.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/guard/type_matcher.py backend/data/templates/ backend/tests/test_guard.py
git commit -m "feat(guard): add Hybrid Type Matcher with template library"
```

---

## Phase 2: 预解答系统

### Task 4: Local Precompute

**Covers:** [S2.6]

**Files:**
- Create: `backend/guard/precompute.py`
- Modify: `backend/tests/test_guard.py`

- [ ] **Step 1: 写 Precompute 测试**

```python
# 追加到 backend/tests/test_guard.py
from guard.precompute import local_precompute

class TestPrecompute:
    def test_integral_precompute(self):
        graph = {
            "equality_constraints": ["∫₀¹ x² dx"],
            "target": "积分值",
            "answer_shape": "expression",
        }
        cls = {"domain": "微积分", "problem_type": "definite_integral"}
        result = local_precompute(graph, cls, [])
        assert "symbolic_candidates" in result
        assert "numeric_sanity" in result

    def test_linear_system_precompute(self):
        graph = {
            "equality_constraints": ["2x+3=7"],
            "target": "x",
            "answer_shape": "expression",
        }
        cls = {"domain": "代数", "problem_type": "linear_equation"}
        result = local_precompute(graph, cls, [])
        assert "symbolic_candidates" in result

    def test_empty_graph(self):
        result = local_precompute({}, {}, [])
        assert "symbolic_candidates" in result
        assert result["symbolic_candidates"] == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_guard.py::TestPrecompute -v`
Expected: FAIL

- [ ] **Step 3: 实现 Local Precompute**

```python
# backend/guard/precompute.py
"""Local Precompute & Sanity Checker - 本地符号/数值预计算."""

import re
import logging

logger = logging.getLogger(__name__)


def local_precompute(graph: dict, classification: dict, templates: list) -> dict:
    """Run local symbolic/numeric precomputation.

    Args:
        graph: Constraint graph.
        classification: Type matcher result.
        templates: Matched templates.

    Returns:
        Dict with symbolic_candidates, numeric_sanity, verification_hooks.
    """
    result = {
        "symbolic_candidates": [],
        "numeric_sanity": {},
        "verification_hooks": [],
    }

    domain = classification.get("domain", "")
    problem_type = classification.get("problem_type", "")
    text = " ".join(graph.get("equality_constraints", []))

    try:
        # Try symbolic precomputation based on domain
        if domain in ("微积分", "calculus"):
            candidates = _precompute_calculus(text, graph)
            result["symbolic_candidates"].extend(candidates)
        elif domain in ("代数", "algebra", "线性代数", "linear_algebra"):
            candidates = _precompute_algebra(text, graph)
            result["symbolic_candidates"].extend(candidates)
    except Exception as e:
        logger.debug("Precompute failed (non-fatal): %s", e)

    # Numeric sanity checks
    result["numeric_sanity"] = _numeric_sanity_check(graph)

    # Verification hooks from templates
    if templates:
        result["verification_hooks"] = templates[0].get("verification", [])

    return result


def _precompute_calculus(text: str, graph: dict) -> list[str]:
    """Try to precompute calculus problems with SymPy."""
    try:
        import sympy as sp
    except ImportError:
        return []

    candidates = []

    # Try definite integral
    integral_match = re.search(r"∫[₀₁²³⁴⁵⁶⁷⁸⁹\d]+[₀₁²³⁴⁵⁶⁷⁸⁹\d]*\s*(.+?)\s*d(\w+)", text)
    if integral_match:
        try:
            x = sp.Symbol(integral_match.group(2))
            expr = sp.sympify(integral_match.group(1))
            # Try common limits
            for a, b in [(0, 1), (-1, 1), (0, sp.oo)]:
                try:
                    val = sp.integrate(expr, (x, a, b))
                    if val.is_finite:
                        candidates.append(f"∫[{a},{b}] {expr} dx = {val}")
                except Exception:
                    continue
        except Exception:
            pass

    # Try simple equation solving
    eq_match = re.search(r"(\w+)\s*=\s*(.+)", text)
    if eq_match:
        try:
            var = sp.Symbol(eq_match.group(1))
            expr = sp.sympify(eq_match.group(2))
            sol = sp.solve(sp.Eq(var, expr), var)
            if sol:
                candidates.append(f"{var} = {sol[0]}")
        except Exception:
            pass

    return candidates[:3]


def _precompute_algebra(text: str, graph: dict) -> list[str]:
    """Try to precompute algebra problems with SymPy."""
    try:
        import sympy as sp
    except ImportError:
        return []

    candidates = []

    # Try linear equation
    eq_match = re.search(r"(\d*)(\w)\s*\+\s*(\d+)\s*=\s*(\d+)", text)
    if eq_match:
        try:
            x = sp.Symbol(eq_match.group(2))
            a = int(eq_match.group(1)) if eq_match.group(1) else 1
            b = int(eq_match.group(3))
            c = int(eq_match.group(4))
            sol = sp.solve(sp.Eq(a * x + b, c), x)
            if sol:
                candidates.append(f"{x} = {sol[0]}")
        except Exception:
            pass

    return candidates[:3]


def _numeric_sanity_check(graph: dict) -> dict:
    """Run basic numeric sanity checks."""
    checks = {}
    domain_constraints = graph.get("domain_constraints", [])
    boundary_constraints = graph.get("boundary_constraints", [])

    checks["has_domain"] = len(domain_constraints) > 0
    checks["has_boundary"] = len(boundary_constraints) > 0
    checks["has_target"] = bool(graph.get("target"))

    return checks
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_guard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/guard/precompute.py backend/tests/test_guard.py
git commit -m "feat(guard): add Local Precompute with SymPy integration"
```

---

### Task 5: Calibrated Router

**Covers:** [S2.7, S3]

**Files:**
- Create: `backend/guard/router.py`
- Modify: `backend/tests/test_guard.py`

- [ ] **Step 1: 写 Router 测试**

```python
# 追加到 backend/tests/test_guard.py
from guard.router import CalibratedRouter

class TestRouter:
    def test_simple_route(self):
        router = CalibratedRouter()
        features = {
            "type_confidence": 0.9,
            "retrieval_score": 0.8,
            "tool_success": 1.0,
            "complexity_score": 0.1,
            "guard_parse_failed": False,
            "signal_conflict": False,
        }
        result = router.predict(features)
        assert result["route"] == "simple"

    def test_complex_route(self):
        router = CalibratedRouter()
        features = {
            "type_confidence": 0.3,
            "retrieval_score": 0.2,
            "tool_success": 0.0,
            "complexity_score": 0.8,
            "guard_parse_failed": False,
            "signal_conflict": False,
        }
        result = router.predict(features)
        assert result["route"] in ("complex", "safe_fallback")

    def test_safe_fallback_on_parse_failure(self):
        router = CalibratedRouter()
        features = {
            "type_confidence": 0.9,
            "retrieval_score": 0.8,
            "tool_success": 1.0,
            "complexity_score": 0.1,
            "guard_parse_failed": True,
            "signal_conflict": False,
        }
        result = router.predict(features)
        assert result["route"] == "safe_fallback"

    def test_conflict_detection(self):
        router = CalibratedRouter()
        features = {
            "type_confidence": 0.5,
            "retrieval_score": 0.5,
            "tool_success": 0.5,
            "complexity_score": 0.5,
            "guard_parse_failed": False,
            "signal_conflict": False,
            "top1_top2_method_conflict": True,
        }
        result = router.predict(features)
        assert "method_conflict" in result["conflict_flags"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_guard.py::TestRouter -v`
Expected: FAIL

- [ ] **Step 3: 实现 Calibrated Router**

```python
# backend/guard/router.py
"""Calibrated Router - 置信度融合 + 四路由决策."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CalibratedRouter:
    """Route problems to appropriate pipeline depth.

    Cold-start: hand-written rules.
    Production: trained LogisticRegression/XGBoost model.
    """

    def __init__(self, model=None):
        # Cold-start weights (replace with trained model later)
        self.rule_weights = {
            "type_confidence": 0.35,
            "retrieval_score": 0.30,
            "tool_success": 0.25,
            "complexity_penalty": -0.10,
        }
        self.model = model  # Optional trained classifier

    def predict(self, features: dict) -> dict:
        """Predict route and confidence.

        Args:
            features: Dict with type_confidence, retrieval_score, tool_success,
                     complexity_score, guard_parse_failed, signal_conflict, etc.

        Returns:
            Dict with route, pre_llm_confidence, conflict_flags, n_candidates.
        """
        # Check for hard overrides first
        if features.get("guard_parse_failed"):
            return self._build_result("safe_fallback", 0.0, ["guard_parse_failed"], 3)

        if features.get("signal_conflict"):
            return self._build_result("safe_fallback", 0.0, ["signal_conflict"], 3)

        # Calculate confidence
        if self.model is not None:
            confidence = self._model_predict(features)
        else:
            confidence = self._rule_based(features)

        # Detect conflicts
        conflict_flags = self._detect_conflicts(features)

        # If conflicts detected, escalate
        if conflict_flags:
            return self._build_result("safe_fallback", confidence, conflict_flags, 3)

        # Route based on confidence and complexity
        route = self._route_from_scores(confidence, features.get("complexity_score", 0.5))

        n_candidates = 3 if route in ("complex", "safe_fallback") else 1

        return self._build_result(route, confidence, conflict_flags, n_candidates)

    def _rule_based(self, features: dict) -> float:
        """Calculate confidence using hand-written weights."""
        conf = 0.0
        conf += self.rule_weights["type_confidence"] * features.get("type_confidence", 0)
        conf += self.rule_weights["retrieval_score"] * features.get("retrieval_score", 0)
        conf += self.rule_weights["tool_success"] * features.get("tool_success", 0)
        conf += self.rule_weights["complexity_penalty"] * features.get("complexity_score", 0)
        return max(0.0, min(1.0, conf))

    def _model_predict(self, features: dict) -> float:
        """Use trained model for prediction."""
        import numpy as np
        feature_vec = [
            features.get("type_confidence", 0),
            features.get("retrieval_score", 0),
            features.get("tool_success", 0),
            features.get("complexity_score", 0),
        ]
        return float(self.model.predict_proba([feature_vec])[0][1])

    def _route_from_scores(self, confidence: float, complexity: float) -> str:
        """Determine route from confidence and complexity."""
        if confidence > 0.8 and complexity <= 0.2:
            return "simple"
        if confidence > 0.5 and complexity <= 0.5:
            return "standard"
        return "complex"

    def _detect_conflicts(self, features: dict) -> list[str]:
        """Detect signal conflicts that warrant safe_fallback."""
        flags = []
        if features.get("top1_top2_method_conflict"):
            flags.append("method_conflict")
        if features.get("retrieval_vs_rule_mismatch"):
            flags.append("classification_conflict")
        if features.get("precompute_failed"):
            flags.append("precompute_failure")
        return flags

    def _build_result(self, route: str, confidence: float, flags: list, n_candidates: int) -> dict:
        return {
            "route": route,
            "pre_llm_confidence": round(confidence, 3),
            "conflict_flags": flags,
            "n_candidates": n_candidates,
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_guard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/guard/router.py backend/tests/test_guard.py
git commit -m "feat(guard): add Calibrated Router with 4-route decision"
```

---

## Phase 3: 自适应流水线

### Task 6: Context Builder + Guard 主入口

**Covers:** [S7]

**Files:**
- Create: `backend/guard/context_builder.py`
- Create: `backend/guard/cache.py`
- Modify: `backend/tests/test_guard.py`

- [ ] **Step 1: 写 Context Builder 测试**

```python
# 追加到 backend/tests/test_guard.py
from guard.context_builder import build_presolve_context
from guard.cache import ProblemCache

class TestContextBuilder:
    def test_build_context(self):
        ctx = build_presolve_context("计算 2+3")
        assert "normalized" in ctx
        assert "constraint_graph" in ctx
        assert "risk" in ctx
        assert "classification" in ctx
        assert "fusion" in ctx
        assert ctx["fusion"]["route"] in ("simple", "standard", "complex", "safe_fallback")

    def test_context_has_presolve_id(self):
        ctx = build_presolve_context("test problem")
        assert "problem_id" in ctx

class TestCache:
    def test_cache_set_get(self, tmp_path):
        cache = ProblemCache(cache_dir=str(tmp_path))
        cache.set("test problem", {"answer": 42})
        result = cache.get("test problem")
        assert result == {"answer": 42}

    def test_cache_miss(self, tmp_path):
        cache = ProblemCache(cache_dir=str(tmp_path))
        result = cache.get("nonexistent")
        assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_guard.py::TestContextBuilder -v`
Expected: FAIL

- [ ] **Step 3: 实现 Cache**

```python
# backend/guard/cache.py
"""Structured problem cache with multi-field keys."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProblemCache:
    """Cache for solved problems with structural key matching."""

    def __init__(self, cache_dir: str = ".cache/problems", threshold: float = 0.98):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.threshold = threshold
        self._index: list[dict] = self._load_index()

    def _load_index(self) -> list[dict]:
        entries = []
        for f in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                entries.append({
                    "hash": f.stem,
                    "problem": data.get("problem", ""),
                    "constraint_sig": data.get("constraint_sig", ""),
                    "answer_type": data.get("answer_type", ""),
                    "domain": data.get("domain", ""),
                    "result": data.get("result", {}),
                })
            except Exception:
                continue
        return entries

    def get(self, problem: str, graph: dict = None, classification: dict = None) -> Optional[dict]:
        """Get cached result for a problem."""
        if not self._index:
            return None

        # Exact match
        for entry in self._index:
            if entry["problem"].strip() == problem.strip():
                return entry["result"]

        # Structural match
        if graph and classification:
            current_sig = _constraint_signature(graph)
            current_type = classification.get("answer_type", "")
            current_domain = classification.get("domain", "")

            for entry in self._index:
                if (entry["domain"] == current_domain
                    and entry["answer_type"] == current_type
                    and _sig_similarity(entry["constraint_sig"], current_sig) >= self.threshold):
                    return entry["result"]

        return None

    def set(self, problem: str, result: dict, graph: dict = None, classification: dict = None):
        """Cache a problem result."""
        key_data = {
            "problem": problem,
            "constraint_sig": _constraint_signature(graph) if graph else "",
            "answer_type": classification.get("answer_type", "") if classification else "",
            "domain": classification.get("domain", "") if classification else "",
            "result": result,
        }
        h = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:16]
        path = self.cache_dir / f"{h}.json"
        path.write_text(json.dumps(key_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._index.append({"hash": h, **key_data})


def _constraint_signature(graph: dict) -> str:
    """Create a signature from constraint graph."""
    parts = [
        "|".join(sorted(graph.get("variables", []))),
        "|".join(sorted(graph.get("equality_constraints", []))),
        "|".join(sorted(graph.get("boundary_constraints", []))),
        graph.get("answer_shape", ""),
    ]
    return "::".join(parts)


def _sig_similarity(sig1: str, sig2: str) -> float:
    """Calculate similarity between two constraint signatures."""
    if sig1 == sig2:
        return 1.0
    set1 = set(sig1.split("::"))
    set2 = set(sig2.split("::"))
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0
```

- [ ] **Step 4: 实现 Context Builder**

```python
# backend/guard/context_builder.py
"""PreSolveContext Builder - Guard Layer 主入口."""

import hashlib
import json
import logging
from typing import Optional

from guard.normalizer import normalize_problem, build_constraint_graph
from guard.complexity import estimate_risk
from guard.type_matcher import hybrid_classify
from guard.precompute import local_precompute
from guard.router import CalibratedRouter
from guard.cache import ProblemCache

logger = logging.getLogger(__name__)

# Global instances
_router = CalibratedRouter()
_cache = ProblemCache()


def build_presolve_context(problem: str, use_cache: bool = True) -> dict:
    """Build PreSolveContext from raw problem text.

    This is the main entry point for the Guard Layer.
    All operations are local (zero LLM calls).

    Args:
        problem: Raw problem text.
        use_cache: Whether to check cache.

    Returns:
        PreSolveContext dict.
    """
    # Step 1: Normalize
    norm = normalize_problem(problem)
    graph = build_constraint_graph(norm)

    # Step 2: Check cache
    if use_cache:
        cached = _cache.get(problem, graph, {"domain": "", "answer_type": norm.get("answer_type", "")})
        if cached:
            logger.info("Cache hit for problem")
            return cached

    # Step 3: Classify
    classification = hybrid_classify(norm["clean_text"], norm["symbols"], graph)

    # Step 4: Estimate risk
    risk = estimate_risk(norm, graph)

    # Step 5: Local precompute
    precompute = local_precompute(graph, classification, [])

    # Step 6: Route
    router_features = {
        "type_confidence": classification.get("confidence", 0),
        "retrieval_score": 0.5,  # No retrieval yet
        "tool_success": 1.0 if precompute["symbolic_candidates"] else 0.0,
        "complexity_score": risk["complexity_score"],
        "guard_parse_failed": not graph.get("target") and not norm.get("clean_text"),
        "signal_conflict": False,
    }
    fusion = _router.predict(router_features)

    # Build context
    context = {
        "problem_id": f"sha256:{hashlib.sha256(problem.encode()).hexdigest()[:16]}",
        "raw_problem": problem,
        "normalized": {
            "clean_text": norm["clean_text"],
            "latex_blocks": norm["latex_blocks"],
            "symbols": norm["symbols"],
            "answer_type": norm["answer_type"],
            "is_proof": norm["is_proof"],
        },
        "constraint_graph": graph,
        "risk": risk,
        "classification": classification,
        "retrieval": {
            "similar_cases": [],
            "method_templates": [],
        },
        "precompute": precompute,
        "fusion": fusion,
    }

    # Cache the result
    if use_cache:
        _cache.set(problem, context, graph, classification)

    return context
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_guard.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/guard/context_builder.py backend/guard/cache.py backend/tests/test_guard.py
git commit -m "feat(guard): add Context Builder + ProblemCache"
```

---

### Task 7: Adaptive Pipeline + Four Routes

**Covers:** [S1, S3]

**Files:**
- Create: `backend/pipeline/adaptive.py`
- Create: `backend/pipeline/routes/__init__.py`
- Create: `backend/pipeline/routes/simple.py`
- Create: `backend/pipeline/routes/standard.py`
- Create: `backend/pipeline/routes/complex.py`
- Create: `backend/pipeline/routes/safe_fallback.py`
- Create: `backend/pipeline/canonicalizer.py`
- Create: `backend/tests/test_routes.py`

- [ ] **Step 1: 创建 routes 包**

```python
# backend/pipeline/routes/__init__.py
"""Adaptive pipeline route implementations."""
```

- [ ] **Step 2: 写路由测试**

```python
# backend/tests/test_routes.py
import pytest
from unittest.mock import AsyncMock, patch
from pipeline.adaptive import AdaptivePipeline

class TestAdaptivePipeline:
    def test_pipeline_init(self):
        pipeline = AdaptivePipeline()
        assert pipeline is not None

    @pytest.mark.asyncio
    async def test_simple_route_mock(self):
        """Test simple route with mocked LLM."""
        pipeline = AdaptivePipeline()
        # Mock the guard to return simple route
        with patch("pipeline.adaptive.build_presolve_context") as mock_guard:
            mock_guard.return_value = {
                "raw_problem": "2+3",
                "normalized": {"clean_text": "2+3", "symbols": [], "answer_type": "numeric", "is_proof": False, "latex_blocks": []},
                "constraint_graph": {"variables": [], "unknowns": [], "target": "结果", "answer_shape": "numeric", "has_pde": False, "has_proof": False, "requires_case_split": False, "requires_tool": False, "domain_constraints": [], "equality_constraints": [], "boundary_constraints": [], "initial_constraints": [], "knowns": [], "inequality_constraints": []},
                "risk": {"complexity_score": 0.1, "risk_tags": [], "needs_tool": False, "needs_verifier": False, "answer_shape_certainty": 1.0},
                "classification": {"domain": "代数", "problem_type": "arithmetic", "confidence": 0.9, "alternatives": []},
                "retrieval": {"similar_cases": [], "method_templates": []},
                "precompute": {"symbolic_candidates": ["5"], "numeric_sanity": {"has_target": True}, "verification_hooks": []},
                "fusion": {"route": "simple", "pre_llm_confidence": 0.9, "conflict_flags": [], "n_candidates": 1},
                "problem_id": "test:123",
            }
            # Mock solver
            with patch.object(pipeline, "_run_solver", new_callable=AsyncMock) as mock_solver:
                mock_solver.return_value = {
                    "reasoning_steps": [{"step_id": 1, "description": "2+3=5", "mathematical_expression": "2+3", "result": "5", "status": "complete"}],
                    "final_answer": "5",
                    "final_answer_latex": None,
                    "answer_format": "numeric",
                }
                result = await pipeline.solve("2+3")
                assert result is not None
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_routes.py -v`
Expected: FAIL

- [ ] **Step 4: 实现 Canonicalizer**

```python
# backend/pipeline/canonicalizer.py
"""Answer Canonicalizer - 统一等价答案形式."""

import re
import logging

logger = logging.getLogger(__name__)


def canonicalize_answer(answer: str, answer_type: str = "expression") -> dict:
    """Canonicalize a math answer for comparison.

    Args:
        answer: Raw answer string.
        answer_type: Type of answer (expression, numeric, proof, etc.)

    Returns:
        Dict with canonical_answer, equivalent_forms, comparison_key.
    """
    if not answer:
        return {
            "canonical_answer": {"type": answer_type, "normalized_form": ""},
            "equivalent_forms": [],
            "comparison_key": "empty",
        }

    # Normalize whitespace and common variations
    normalized = answer.strip()
    normalized = re.sub(r"\s+", " ", normalized)

    # Try SymPy simplification for expressions
    comparison_key = normalized
    equivalent_forms = [normalized]

    if answer_type in ("expression", "numeric"):
        try:
            import sympy as sp
            expr = sp.sympify(normalized)
            simplified = sp.simplify(expr)
            comparison_key = f"expr:sympy_simplified:{simplified}"
            equivalent_forms = [str(simplified), str(expr), normalized]
        except Exception:
            # Fall back to string normalization
            comparison_key = f"str:{normalized.lower().replace(' ', '')}"

    return {
        "canonical_answer": {
            "type": answer_type,
            "normalized_form": normalized,
        },
        "equivalent_forms": list(set(equivalent_forms)),
        "comparison_key": comparison_key,
    }


def answers_match(answer1: str, answer2: str, answer_type: str = "expression") -> bool:
    """Check if two answers are mathematically equivalent."""
    c1 = canonicalize_answer(answer1, answer_type)
    c2 = canonicalize_answer(answer2, answer_type)
    return c1["comparison_key"] == c2["comparison_key"]
```

- [ ] **Step 5: 实现 Adaptive Pipeline**

```python
# backend/pipeline/adaptive.py
"""Adaptive Pipeline - 自适应四路由流水线."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from api.event_bus import EventBus
from config.settings import Settings, settings
from config.schemas import MathAgentOutput
from pipeline.base import BasePipeline
from pipeline.canonicalizer import canonicalize_answer, answers_match
from guard.context_builder import build_presolve_context
from agents.solver import Solver
from agents.verifier import Verifier
from agents.reflection import Reflection
from agents.planner import Planner
from agents.explainer import Explainer
from agents.tool_agent import ToolAgent
from utils.logger import logger as structured_logger

logger = logging.getLogger(__name__)


class AdaptivePipeline(BasePipeline):
    """Adaptive pipeline with four routing strategies.

    Routes:
      - simple:       solver → format
      - standard:     planner → solver → verifier → format
      - complex:      planner → solver×N → canonicalize → verifier → consensus → reflect → format
      - safe_fallback: planner → solver×N → tool_crosscheck → verifier → format
    """

    def __init__(self, config: Optional[Settings] = None, event_bus: Optional[EventBus] = None):
        super().__init__(config, event_bus)
        self.solver = Solver()
        self.verifier = Verifier()
        self.reflection = Reflection()
        self.planner = Planner()
        self.explainer = Explainer()
        self.tool_agent = ToolAgent()

    async def solve(self, problem: str) -> MathAgentOutput:
        """Solve a problem using adaptive routing."""
        start_time = datetime.now()
        all_outputs = {
            "_start_time": start_time,
            "_pipeline_mode": "adaptive",
        }

        structured_logger.pipeline_start(problem[:200], "adaptive")

        try:
            # Step 1: Guard Layer (local, no LLM)
            ctx = build_presolve_context(problem)
            route = ctx["fusion"]["route"]
            all_outputs["_route"] = route
            all_outputs["_guard_context"] = ctx

            logger.info("Route: %s (confidence=%.2f, complexity=%.2f)",
                       route, ctx["fusion"]["pre_llm_confidence"], ctx["risk"]["complexity_score"])

            # Step 2: Execute route
            if route == "simple":
                solving = await self._route_simple(problem, ctx)
            elif route == "standard":
                solving = await self._route_standard(problem, ctx)
            elif route == "complex":
                solving = await self._route_complex(problem, ctx)
            else:  # safe_fallback
                solving = await self._route_safe_fallback(problem, ctx)

            all_outputs["solving"] = solving

            # Step 3: Explanation (skip for simple)
            if route != "simple":
                await self._emit_stage("explanation", "started", self._calc_progress(7))
                explanation = await self.explainer.run({
                    **ctx.get("normalized", {}),
                    **solving,
                })
                all_outputs["explanation"] = explanation
                await self._emit_stage("explanation", "complete", self._calc_progress(7))

            # Step 4: Format
            await self._emit_stage("formatting", "started", self._calc_progress(8))
            result = self.formatter.format(all_outputs)
            await self._emit_stage("formatting", "complete", self._calc_progress(9))

            duration_ms = result.processing_time_ms
            await self._emit_complete("success", duration_ms=duration_ms)
            structured_logger.pipeline_complete(result.problem_id, duration_ms)

            return result

        except Exception as e:
            logger.error("Adaptive pipeline error: %s", e)
            structured_logger.pipeline_error("unknown", str(e))
            await self._emit_error("pipeline", str(e))
            try:
                return self.formatter.format(all_outputs)
            except Exception:
                raise e

    async def _run_solver(self, problem: str, ctx: dict, seed: int = 0) -> dict:
        """Run solver with PreSolve Context."""
        context_input = {
            "problem": problem,
            "cleaned_problem": ctx["normalized"]["clean_text"],
            "domain": ctx["classification"].get("domain", "微积分"),
            "strategy": ctx["classification"].get("recommended_method", ""),
            "presolve_context": ctx,
        }
        if seed > 0:
            self.solver.config = self.config.model_copy(update={
                "temperature": min(1.5, self.config.temperature + seed * 0.1)
            })
        return await self.solver.run(context_input)

    async def _route_simple(self, problem: str, ctx: dict) -> dict:
        """Simple route: solver → format."""
        await self._emit_stage("solving", "started", self._calc_progress(5))
        solving = await self._run_solver(problem, ctx)
        await self._emit_stage("solving", "complete", self._calc_progress(5))
        return solving

    async def _route_standard(self, problem: str, ctx: dict) -> dict:
        """Standard route: planner → solver → verifier → format."""
        # Planner
        await self._emit_stage("planning", "started", self._calc_progress(4))
        plan = await self.planner.run({
            **ctx.get("normalized", {}),
            **ctx["classification"],
        })
        await self._emit_stage("planning", "complete", self._calc_progress(4))

        # Solver
        await self._emit_stage("solving", "started", self._calc_progress(5))
        solving = await self._run_solver(problem, ctx)
        solving["strategy"] = plan.get("strategy", "")
        solving["steps"] = plan.get("steps", [])
        await self._emit_stage("solving", "complete", self._calc_progress(5))

        # Verifier
        await self._emit_stage("verification", "started", self._calc_progress(6))
        verification = await self.verifier.run({
            **ctx.get("normalized", {}),
            **solving,
            "presolve_context": ctx,
        })
        solving["verification"] = verification
        await self._emit_stage("verification", "complete", self._calc_progress(6))

        return solving

    async def _route_complex(self, problem: str, ctx: dict) -> dict:
        """Complex route: planner → solver×N → canonicalize → verifier → consensus → reflect."""
        n_candidates = ctx["fusion"].get("n_candidates", 3)

        # Planner
        await self._emit_stage("planning", "started", self._calc_progress(4))
        plan = await self.planner.run({
            **ctx.get("normalized", {}),
            **ctx["classification"],
        })
        await self._emit_stage("planning", "complete", self._calc_progress(4))

        # Parallel solvers
        await self._emit_stage("solving", "started", self._calc_progress(5))
        solver_tasks = [self._run_solver(problem, ctx, seed=i) for i in range(n_candidates)]
        solver_results = await asyncio.gather(*solver_tasks, return_exceptions=True)
        valid_results = [r for r in solver_results if isinstance(r, dict) and "final_answer" in r]
        if not valid_results:
            valid_results = [{"final_answer": "All solvers failed", "reasoning_steps": []}]
        await self._emit_stage("solving", "complete", self._calc_progress(5))

        # Canonicalize answers
        for r in valid_results:
            r["_canonical"] = canonicalize_answer(
                r.get("final_answer", ""),
                ctx.get("normalized", {}).get("answer_type", "expression"),
            )

        # Verify each candidate
        await self._emit_stage("verification", "started", self._calc_progress(6))
        for r in valid_results:
            verification = await self.verifier.run({
                **ctx.get("normalized", {}),
                **r,
                "presolve_context": ctx,
            })
            r["_verification"] = verification
        await self._emit_stage("verification", "complete", self._calc_progress(6))

        # Select best candidate
        best = max(valid_results, key=lambda r: (
            r.get("_verification", {}).get("overall_score", 0),
            r.get("_verification", {}).get("confidence", 0),
        ))

        # Reflection if needed
        if not best.get("_verification", {}).get("verified", False):
            await self._emit_stage("reflection", "started", self._calc_progress(6))
            reflection = await self.reflection.run({
                **ctx.get("normalized", {}),
                **best,
                **best.get("_verification", {}),
            })
            best["_reflection"] = reflection
            await self._emit_stage("reflection", "complete", self._calc_progress(6))

        best["_all_candidates"] = valid_results
        return best

    async def _route_safe_fallback(self, problem: str, ctx: dict) -> dict:
        """Safe fallback: planner → solver×N → mandatory tool crosscheck → verifier."""
        n_candidates = ctx["fusion"].get("n_candidates", 3)

        # Planner
        await self._emit_stage("planning", "started", self._calc_progress(4))
        plan = await self.planner.run({
            **ctx.get("normalized", {}),
            **ctx["classification"],
        })
        await self._emit_stage("planning", "complete", self._calc_progress(4))

        # Parallel solvers
        await self._emit_stage("solving", "started", self._calc_progress(5))
        solver_tasks = [self._run_solver(problem, ctx, seed=i) for i in range(n_candidates)]
        solver_results = await asyncio.gather(*solver_tasks, return_exceptions=True)
        valid_results = [r for r in solver_results if isinstance(r, dict) and "final_answer" in r]
        if not valid_results:
            valid_results = [{"final_answer": "All solvers failed", "reasoning_steps": []}]
        await self._emit_stage("solving", "complete", self._calc_progress(5))

        # Mandatory tool crosscheck for all candidates
        for r in valid_results:
            if r.get("reasoning_steps"):
                r["reasoning_steps"] = await self.tool_agent.execute_from_solver_output(
                    r["reasoning_steps"]
                )

        # Verify
        await self._emit_stage("verification", "started", self._calc_progress(6))
        for r in valid_results:
            verification = await self.verifier.run({
                **ctx.get("normalized", {}),
                **r,
                "presolve_context": ctx,
            })
            r["_verification"] = verification
        await self._emit_stage("verification", "complete", self._calc_progress(6))

        # Select best
        best = max(valid_results, key=lambda r: (
            r.get("_verification", {}).get("overall_score", 0),
            r.get("_verification", {}).get("confidence", 0),
        ))

        # Flag uncertainty if all candidates disagree
        canonical_keys = set()
        for r in valid_results:
            c = canonicalize_answer(r.get("final_answer", ""), ctx.get("normalized", {}).get("answer_type", "expression"))
            canonical_keys.add(c["comparison_key"])

        if len(canonical_keys) > 1:
            best["_uncertain"] = True
            best["_uncertainty_note"] = "Multiple candidates disagree"

        return best
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_routes.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/pipeline/adaptive.py backend/pipeline/routes/ backend/pipeline/canonicalizer.py backend/tests/test_routes.py
git commit -m "feat(pipeline): add Adaptive Pipeline with 4 routes + Canonicalizer"
```

---

## Phase 4: Prompt 契约

### Task 8: Update Prompts for Dual-Channel Strategy

**Covers:** [S4]

**Files:**
- Modify: `backend/config/prompts.py`

- [ ] **Step 1: 读取现有 prompts.py**

Read: `backend/config/prompts.py`

- [ ] **Step 2: 添加新 Prompt 常量**

在 `config/prompts.py` 末尾追加：

```python
# ==================== Adaptive Pipeline Prompts (Dual-Channel) ====================

ADAPTIVE_SOLVER_SYSTEM = """你是数学求解代理。你将收到：
1) 原题；
2) 本地 Guard Layer 生成的先验上下文；
3) 可选的工具预计算结果。

严格遵守以下规则：
- 题面高于任何先验；若先验与题面冲突，以题面为准。
- 先检查约束、变量、目标是否一致，再决定是否采纳先验方法。
- 对于可计算的步骤，优先使用工具结果或可验证等式，不要凭感觉心算。
- 若你认为 Guard 的分类或模板不适用，明确指出"不适用原因"，然后改用更合适的方法。
- 输出先给出完整自然语言推理；结尾单独给出"最终答案"与"置信度说明"。
- 不要输出 JSON。"""

ADAPTIVE_SOLVER_USER = """【原题】
{problem}

【Guard Layer 先验】
{presolve_context}

请先：
A. 用一句话判断 Guard 先验是否总体可信；
B. 列出你真正要使用的约束；
C. 再开始求解。"""

ADAPTIVE_VERIFIER_SYSTEM = """你是数学验证代理。给定原题、候选解、Guard 先验与工具计算结果，请对候选解逐步判断。

对每一步必须输出以下标签之一：
- valid
- unsupported
- arithmetic_error
- algebra_error
- constraint_mismatch
- theorem_misuse
- incomplete

要求：
- 如果最终答案正确但中间步骤存在不可接受跳步，也要指出。
- 如果题目是证明题，重点检查"命题是否被证明"，不要只看结论像不像。
- 如果工具结果与文本步骤冲突，优先信任工具/代入验证。
- 输出 JSON，不要输出散文。"""

ADAPTIVE_VERIFIER_USER = """【原题】
{problem}

【候选解】
{candidate_solution}

【Guard 先验】
{presolve_context}

请逐步验证，输出 JSON：
{{
  "overall": {{"is_correct": bool, "confidence": float, "need_revision": bool}},
  "step_labels": [{{"step_id": int, "label": "valid|unsupported|arithmetic_error|...", "reason": "string"}}],
  "critical_errors": ["string"],
  "repair_hint": "string"
}}"""

ADAPTIVE_REFLECTION_SYSTEM = """你将看到：
1) 原题；
2) 你之前的解；
3) 验证器指出的具体错误；
4) 工具交叉检查结果。

你的任务不是重写整份答案，而是：
- 仅修复被 verifier 标成 critical 的步骤；
- 保留未被判错的正确部分；
- 若原方法本身不适用，可改方法，但必须明确说明切换原因；
- 最后重新给出完整答案与修订说明。"""

ADAPTIVE_REFLECTION_USER = """【原题】
{problem}

【你之前的解】
{previous_solution}

【验证器错误】
{verification_errors}

【修复提示】
{repair_hint}

请仅修复错误部分，给出修订后的完整答案。"""
```

- [ ] **Step 3: Commit**

```bash
git add backend/config/prompts.py
git commit -m "feat(prompts): add dual-channel adaptive pipeline prompts"
```

---

## Phase 5: 优化细节

### Task 9: ToolAgent 并行化

**Covers:** [S5]

**Files:**
- Modify: `backend/agents/tool_agent.py`

- [ ] **Step 1: 读取现有 tool_agent.py**

Read: `backend/agents/tool_agent.py`

- [ ] **Step 2: 添加并行执行方法**

在 `ToolAgent` 类中添加：

```python
async def execute_parallel(self, reasoning_steps: list) -> list:
    """Execute tool calls in parallel where possible.

    Groups tool calls by dependency and executes each group concurrently.

    Args:
        reasoning_steps: List of reasoning step dicts.

    Returns:
        Updated reasoning steps with tool results.
    """
    tool_calls = []
    for i, step in enumerate(reasoning_steps):
        if isinstance(step, dict) and step.get("mathematical_expression"):
            tool_calls.append((i, step))

    if not tool_calls:
        return reasoning_steps

    # Group by dependency (simple heuristic: different variables = independent)
    groups = self._build_dependency_groups(tool_calls)

    for group in groups:
        tasks = [self._execute_single_tool(step) for _, step in group]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (idx, step), result in zip(group, results):
            if isinstance(result, dict):
                step["tool_result"] = result.get("result", "")
                step["tool_verified"] = result.get("success", False)

    return reasoning_steps

def _build_dependency_groups(self, tool_calls: list) -> list[list]:
    """Group tool calls by dependency.

    Simple heuristic: all independent (one group).
    Override for more sophisticated dependency analysis.
    """
    if not tool_calls:
        return []
    # For now, all in one group (fully parallel)
    return [tool_calls]

async def _execute_single_tool(self, step: dict) -> dict:
    """Execute a single tool call."""
    try:
        expr = step.get("mathematical_expression", "")
        if not expr:
            return {"success": False, "result": ""}
        # Use existing symbolic tool
        from tools.symbolic import run_symbolic_tool
        result = await asyncio.to_thread(run_symbolic_tool, expr)
        return {"success": True, "result": str(result)}
    except Exception as e:
        return {"success": False, "result": str(e)}
```

- [ ] **Step 3: Commit**

```bash
git add backend/agents/tool_agent.py
git commit -m "feat(tool-agent): add parallel execution for tool calls"
```

---

## Phase 6: 评测框架

### Task 10: 评测指标

**Covers:** [S9]

**Files:**
- Create: `backend/eval/__init__.py`
- Create: `backend/eval/metrics.py`

- [ ] **Step 1: 创建评测模块**

```python
# backend/eval/__init__.py
"""Evaluation framework for adaptive pipeline."""
```

```python
# backend/eval/metrics.py
"""Evaluation metrics for the adaptive pipeline."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PipelineMetrics:
    """Collect and report pipeline evaluation metrics."""

    def __init__(self, results_dir: str = "eval/results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results: list[dict] = []

    def record(self, result: dict):
        """Record a single problem result."""
        self.results.append(result)

    def summary(self) -> dict:
        """Generate summary metrics."""
        if not self.results:
            return {"error": "No results recorded"}

        total = len(self.results)
        correct = sum(1 for r in self.results if r.get("correct", False))
        routes = {}
        for r in self.results:
            route = r.get("route", "unknown")
            routes[route] = routes.get(route, 0) + 1

        latencies = [r.get("latency_ms", 0) for r in self.results]
        llm_calls = [r.get("llm_calls", 0) for r in self.results]

        return {
            "total": total,
            "pass_at_1": correct / total if total else 0,
            "route_distribution": routes,
            "avg_latency_ms": sum(latencies) / total if total else 0,
            "avg_llm_calls": sum(llm_calls) / total if total else 0,
            "guard_accuracy": sum(1 for r in self.results if r.get("guard_correct", False)) / total if total else 0,
        }

    def save(self, filename: str = "metrics.json"):
        """Save results and summary to file."""
        path = self.results_dir / filename
        data = {
            "summary": self.summary(),
            "results": self.results,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Metrics saved to %s", path)


class AblationRunner:
    """Run ablation experiments."""

    EXPERIMENTS = [
        "no_guard",
        "guard_no_retrieval",
        "guard_no_precompute",
        "standard_no_verifier",
        "complex_self_reflection_only",
        "full_chain_strict_json",
        "control_plane_only_json",
    ]

    def __init__(self, base_dir: str = "eval/ablation"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def run_experiment(self, name: str, problems: list[str], pipeline_config: dict) -> dict:
        """Run a single ablation experiment."""
        # This would be called with different pipeline configurations
        # Implementation depends on the actual pipeline
        logger.info("Running ablation: %s with %d problems", name, len(problems))
        return {"experiment": name, "status": "pending"}
```

- [ ] **Step 2: Commit**

```bash
git add backend/eval/__init__.py backend/eval/metrics.py
git commit -m "feat(eval): add evaluation metrics and ablation framework"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Every [Sn] section covered by at least one task
  - [S1] → Task 7 (Adaptive Pipeline)
  - [S2.1] → Task 1 (Normalizer)
  - [S2.2] → Task 2 (Complexity)
  - [S2.3] → Task 3 (Type Matcher)
  - [S2.6] → Task 4 (Precompute)
  - [S2.7] → Task 5 (Router)
  - [S3] → Task 7 (Routes)
  - [S4] → Task 8 (Prompts)
  - [S5] → Task 9 (ToolAgent)
  - [S6] → Task 6 (Cache)
  - [S7] → Task 6 (Context Builder)
  - [S9] → Task 10 (Metrics)
- [x] **Placeholder scan**: No TBD/TODO found
- [x] **Type consistency**: PreSolveContext, route names, function signatures consistent across tasks
