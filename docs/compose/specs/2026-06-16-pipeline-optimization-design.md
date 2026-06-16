# 自适应流水线优化设计文档

## [S1] 整体架构

将 Pre-LLM Guard Layer 从"轻量预处理器"升级为**"本地证据汇编器"**——一个类型化、可校准、带证据预算的先验生成层。核心原则链：

1. **本地规范化与约束抽取** → 2. **复杂度与风险评估** → 3. **相似题/方法模板检索** → 4. **本地符号/数值预演算** → 5. **压缩成有限长度、带置信度和冲突标记的 PreSolveContext** → 6. **交给 LLM**

```
问题输入 → Pre-LLM Guard Layer (本地证据汇编器)
          ↓
          Route Policy (四条路由)
          ├─ simple:       solver → tool_check_light → format           (1次LLM, 15-30s)
          ├─ standard:     planner → solver → verifier+tool → format     (3次LLM, 45-90s)
          ├─ complex:      planner → solver×N → canonicalize → verifier → consensus → targeted_reflect → format (7-16次LLM, 2-5min)
          └─ safe_fallback: planner → solver×N → mandatory_tool_crosscheck → verifier → abstain_or_flag → format
```

**三条核心设计约束**：

1. **双通道策略**：控制平面（Guard、Router、Verifier、Formatter）用严格 JSON；推理平面（Solver）保持自由自然语言推理。结构化输出研究表明严格 schema 能提升结构可靠性，但会压低推理表现。
2. **RAG 用于检索，不代替求解**：检索增强比纯参数记忆更具事实性，但单纯向量相似度容易引入语义噪声，必须用结构引导重排。
3. **定向修订替代纯自反思**：没有外部反馈时，纯 intrinsic self-correction 往往不稳甚至退化。Reflection 必须由 Verifier/工具触发。

## [S2] Pre-LLM Guard Layer

全部本地执行，零 LLM 调用，延迟 <100ms。对外只暴露一次 `guard(problem) -> PreSolveContext` 调用。

### 2.1 Problem Normalizer + Constraint Graph

不只是字符串清洗，还要输出**约束图**。

```python
def normalize_problem(raw: str) -> dict:
    norm = {
        "clean_text": clean_unicode(raw),
        "latex_blocks": extract_latex(raw),
        "symbols": extract_symbols(raw),
        "keywords": extract_keywords(raw),
        "answer_type": predict_answer_type(raw),
        "is_proof": detect_proof_intent(raw),
    }
    return norm

def build_constraint_graph(norm: dict) -> dict:
    return {
        "variables": extract_variables(norm),
        "unknowns": extract_unknowns(norm),
        "knowns": extract_knowns(norm),
        "domain_constraints": extract_domain(norm),
        "equality_constraints": extract_equalities(norm),
        "inequality_constraints": extract_inequalities(norm),
        "boundary_constraints": extract_boundary(norm),
        "initial_constraints": extract_initial(norm),
        "target": extract_target(norm),
        "answer_shape": predict_answer_shape(norm),
    }
```

### 2.2 Complexity & Risk Estimator

从离散分段升级为**风险路由 + 价值函数**。判断依据不止题目内容，还包括 Guard 自身是否"看懂了题"。

```python
def estimate_risk(norm, graph):
    score = 0.0
    # 内容维度
    score += 0.2 if graph["has_pde"] else 0
    score += 0.2 if norm["is_proof"] else 0
    score += 0.1 if len(graph["variables"]) > 8 else 0
    score += 0.2 if graph["requires_case_split"] else 0
    score += 0.2 if graph["requires_tool"] else 0

    # Guard 自身不确定性（不能解析 ≈ 高风险）
    score += 0.15 if not graph["target"] else 0
    score += 0.15 if len(graph["domain_constraints"]) == 0 and len(graph["equality_constraints"]) == 0 else 0
    score += 0.1 if graph["answer_shape"] == "unknown" else 0

    risk_tags = []
    if score > 0.5: risk_tags.append("high_complexity")
    if not graph["target"]: risk_tags.append("unclear_target")
    if graph["answer_shape"] == "unknown": risk_tags.append("uncertain_answer_form")

    return {
        "complexity_score": min(1.0, score),
        "risk_tags": risk_tags,
        "needs_tool": score > 0.3,
        "needs_verifier": score > 0.2,
        "answer_shape_certainty": 1.0 - (0.2 if "uncertain_answer_form" in risk_tags else 0),
    }
```

### 2.3 Hybrid Type Matcher

从纯 fuzzy match 升级为**规则 + 稀疏检索 + 致密检索 + 轻量重排**。

```python
def hybrid_classify(clean_text, symbols, constraints):
    # Layer 1: 规则匹配（关键词、符号模式）
    rule_hits = rule_based_classify(clean_text, symbols)

    # Layer 2: 稀疏检索（BM25）
    sparse_hits = bm25_index.search(clean_text, top_k=20)

    # Layer 3: 致密检索（embedding）
    dense_hits = embedding_index.search(clean_text, top_k=20)

    # Layer 4: 结构重排（约束匹配 + 语义分数）
    merged = structural_rerank(
        rule_hits, sparse_hits, dense_hits,
        constraints=constraints,
        top_k=5
    )

    return {
        "domain": merged[0]["domain"],
        "problem_type": merged[0]["problem_type"],
        "confidence": merged[0]["score"],
        "alternatives": merged[1:3],
    }
```

题型模板库增加**适用条件 / 禁用条件 / 典型错误 / 验证要求**：

```json
{
  "template_id": "PDE_HEAT_DIRICHLET_1D",
  "domain": "PDE",
  "problem_type": "heat_equation_dirichlet",
  "patterns": ["u_t = k u_xx", "u(0,t)=0", "u(L,t)=0", "initial condition"],
  "applicable_if": ["Dirichlet boundary", "1D heat equation", "homogeneous"],
  "avoid_if": ["non-homogeneous boundary", "source term", "2D domain"],
  "recommended_method": "separation_of_variables",
  "typical_errors": ["wrong eigenvalue sign", "missing Fourier coefficient", "boundary mismatch"],
  "verification": ["PDE substitution", "boundary conditions", "initial condition"],
  "answer_pattern": "sum b_n exp(-n^2 pi^2 t) sin(n pi x)"
}
```

### 2.4 Hybrid Retriever + Evidence Budget

三段式检索（稀疏+致密+结构重排），并引入**证据预算器**限制给 LLM 的上下文量。

```python
EVIDENCE_BUDGET = {
    "simple":   {"similar_cases": 0, "templates": 1, "precompute": 1},
    "standard": {"similar_cases": 1, "templates": 1, "precompute": 1},
    "complex":  {"similar_cases": 2, "templates": 2, "precompute": 2},
}

def compress_evidence(retrieved_cases, templates, precompute, route, token_budget=512):
    budget = EVIDENCE_BUDGET[route]
    evidence = {
        "similar_cases": retrieved_cases[:budget["similar_cases"]],
        "templates": templates[:budget["templates"]],
        "precompute": precompute,
    }
    # 截断到 token_budget
    return truncate_to_tokens(evidence, token_budget)
```

### 2.5 Method Router

根据题型匹配结果选择解法模板。

```python
ROUTE_TABLE = {
    "heat_equation_dirichlet": {
        "method": "separation_of_variables",
        "tools": ["sympy", "fourier"],
        "verifier": ["pde_substitution", "boundary_check"],
        "answer_shape": "fourier_series",
    },
    "residue_integral": {
        "method": "residue_theorem",
        "tools": ["sympy_residue"],
        "verifier": ["pole_check", "contour_check"],
        "answer_shape": "closed_form",
    },
    "linear_programming": {
        "method": "simplex_or_scipy_linprog",
        "tools": ["scipy.optimize.linprog"],
        "verifier": ["constraint_check", "objective_check"],
        "answer_shape": "numeric_vector",
    },
    "compactness_proof": {
        "method": "open_cover_or_sequence_compactness",
        "tools": [],
        "verifier": ["logical_consistency", "counterexample_search"],
        "answer_shape": "proof",
    },
}
```

### 2.6 Local Precompute & Sanity Checker

本地预解答升级为**"局部可验证先验生产器"**，产出四类先验：

- **symbolic_candidates**: SymPy 可算的符号结果
- **numeric_sanity**: 数值近似、边界验证、特值采样
- **answer_shape**: 答案形态预测（表达式/级数/向量/证明）
- **verification_hooks**: 代入检验、逆向条件恢复

```python
def local_precompute(graph, classification, templates):
    results = {
        "symbolic_candidates": [],
        "numeric_sanity": {},
        "verification_hooks": [],
    }

    # 符号预计算
    if classification["domain"] in ("algebra", "calculus", "linear_algebra"):
        try:
            symbolic = sympy_precompute(graph)
            results["symbolic_candidates"].append(symbolic)
        except Exception:
            pass

    # 数值 sanity check
    if graph["answer_shape"] in ("numeric", "expression"):
        results["numeric_sanity"] = numeric_sanity_check(graph)

    # 验证钩子
    results["verification_hooks"] = templates[0]["verification"] if templates else []

    return results
```

### 2.7 Calibrated Router

置信度融合不要手写固定权重。上线后应离线收集每道题的 Guard 特征、路由决策、最终正确性，训练轻量 Logistic Regression / XGBoost 校准器。

```python
class CalibratedRouter:
    def __init__(self):
        # cold-start: 手写规则
        self.rule_weights = {
            "type_confidence": 0.35,
            "retrieval_score": 0.30,
            "tool_success": 0.25,
            "complexity_penalty": -0.10,
        }
        # 上线后替换为训练模型
        self.model = None  # LogisticRegression / XGBoost

    def predict(self, features: dict) -> dict:
        if self.model is not None:
            prob = self.model.predict_proba([features])[0][1]
        else:
            prob = self._rule_based(features)

        route = self._route_from_prob(prob, features)
        return {
            "route": route,
            "pre_llm_confidence": prob,
            "conflict_flags": self._detect_conflicts(features),
            "n_candidates": 3 if route in ("complex", "safe_fallback") else 1,
        }

    def _route_from_prob(self, prob, features):
        if features.get("guard_parse_failed"):
            return "safe_fallback"
        if features.get("signal_conflict"):
            return "safe_fallback"
        if prob > 0.8 and features["complexity_score"] <= 0.2:
            return "simple"
        if prob > 0.5 and features["complexity_score"] <= 0.5:
            return "standard"
        return "complex"

    def _detect_conflicts(self, features):
        flags = []
        if features.get("top1_top2_method_conflict"):
            flags.append("method_conflict")
        if features.get("retrieval_vs_rule_mismatch"):
            flags.append("classification_conflict")
        if features.get("precompute_failed"):
            flags.append("precompute_failure")
        return flags
```

## [S3] 流水线各路径详细设计

### Simple 路径

**条件**: pre_llm_confidence > 0.8 且 complexity_score ≤ 0.2

**流程**: Guard → Solver(带 PreSolve Context, freeform) → tool_check_light → Format

**LLM 调用**: 1 次 (Solver)
**预计耗时**: 15-30s

### Standard 路径

**条件**: pre_llm_confidence 0.5-0.8 或 complexity_score 0.2-0.5

**流程**: Guard → Planner → Solver(freeform) → outcome_verifier + tool_crosscheck → Format

**LLM 调用**: 3 次
**预计耗时**: 45-90s

### Complex 路径

**条件**: pre_llm_confidence < 0.5 或 complexity_score > 0.5

**流程**:
```
Guard → Planner → Solver×N(freeform)
      → Answer Canonicalizer
      → process_verifier / outcome_verifier / tool_crosscheck
      → consensus_select
      → (if confidence < 0.75: targeted_reflect)
      → Format
```

**LLM 调用**: 7-16 次
**预计耗时**: 2-5min

**关键新增**：Answer Canonicalizer 在 consensus 前统一答案形式，解决"语义相同但长得不一样"的投票问题。

### Safe Fallback 路径

**条件**: Guard 自身不确定、解析失败、或多个信号强冲突

**流程**:
```
Guard → Planner → Solver×N(freeform)
      → mandatory_tool_crosscheck
      → verifier
      → if conflict persists: abstain_or_flag_uncertain
      → Format
```

**用途**：不是拒答，而是跳过单路 Solver，进入高校验预算的多路径+工具+verifier 模式。

## [S4] Prompt 契约

### Solver System Prompt

```
你是数学求解代理。你将收到：
1) 原题；
2) 本地 Guard Layer 生成的先验上下文；
3) 可选的工具预计算结果。

严格遵守以下规则：
- 题面高于任何先验；若先验与题面冲突，以题面为准。
- 先检查约束、变量、目标是否一致，再决定是否采纳先验方法。
- 对于可计算的步骤，优先使用工具结果或可验证等式，不要凭感觉心算。
- 若你认为 Guard 的分类或模板不适用，明确指出"不适用原因"，然后改用更合适的方法。
- 输出先给出完整自然语言推理；结尾单独给出"最终答案"与"置信度说明"。
- 不要输出 JSON。
```

### Solver User Prompt

```
【原题】
{{raw_problem}}

【Guard Layer 先验】
{{pre_solve_context_json}}

请先：
A. 用一句话判断 Guard 先验是否总体可信；
B. 列出你真正要使用的约束；
C. 再开始求解。
```

### Verifier Prompt

```
你是数学验证代理。给定原题、候选解、Guard 先验与工具计算结果，请对候选解逐步判断。

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
- 输出 JSON，不要输出散文。
```

Verifier JSON 输出：

```json
{
  "overall": {
    "is_correct": false,
    "confidence": 0.91,
    "need_revision": true
  },
  "step_labels": [
    {"step_id": 1, "label": "valid", "reason": "约束抽取正确"},
    {"step_id": 2, "label": "valid", "reason": "分离变量设定合理"},
    {"step_id": 3, "label": "theorem_misuse", "reason": "边界条件下本征值论证不完整"},
    {"step_id": 4, "label": "constraint_mismatch", "reason": "最终系数与初值不一致"}
  ],
  "critical_errors": ["initial_condition_not_matched"],
  "repair_hint": "重新由初值展开得到 Fourier 系数，再代回检查 t=0"
}
```

### Reflection Prompt（定向修订）

```
你将看到：
1) 原题；
2) 你之前的解；
3) 验证器指出的具体错误；
4) 工具交叉检查结果。

你的任务不是重写整份答案，而是：
- 仅修复被 verifier 标成 critical 的步骤；
- 保留未被判错的正确部分；
- 若原方法本身不适用，可改方法，但必须明确说明切换原因；
- 最后重新给出完整答案与修订说明。
```

### Answer Canonicalizer

在进入投票或 verifier 前先把答案归一化：

```json
{
  "canonical_answer": {
    "type": "expression",
    "normalized_form": "exp(-pi^2*t)*sin(pi*x)"
  },
  "equivalent_forms": ["sin(pi*x)*exp(-pi^2*t)"],
  "comparison_key": "expr:sympy_simplified:exp(-pi^2*t)*sin(pi*x)"
}
```

### Formatter JSON（严格 schema）

```json
{
  "final_answer": "u(x,t)=e^{-\\pi^2 t}\\sin(\\pi x)",
  "answer_type": "expression",
  "confidence": 0.93,
  "method_used": "separation_of_variables",
  "tool_checks": ["PDE substitution passed", "boundary conditions passed", "initial condition passed"],
  "uncertainty_note": ""
}
```

## [S5] ToolAgent 并行优化

### 并行执行

```python
async def execute_parallel(self, reasoning_steps):
    tool_calls = extract_tool_calls(reasoning_steps)
    groups = build_dependency_groups(tool_calls)
    for group in groups:
        results = await asyncio.gather(*[
            execute_tool(call) for call in group
        ])
    return merge_results(reasoning_steps, all_results)
```

### 减少调用

- 相同参数的重复 tool 调用 → 缓存结果
- Guard Layer 的 Local Pre-Solver 已算过的结果 → 跳过

## [S6] 结构化缓存

缓存键不能只按字符串模糊相似度，否则极易误把"题干很像但常数/范围不同"的题视作同题。

```python
def make_cache_key(problem, graph, classification):
    import hashlib
    key_parts = [
        canonicalize_text(problem),
        constraint_signature(graph),
        classification.get("answer_type", ""),
        classification.get("domain", ""),
        normalize_constants(problem),
    ]
    return hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:16]

def reuse_ok(cached_entry, current_graph, current_cls):
    return (
        cached_entry["domain"] == current_cls["domain"]
        and cached_entry["answer_type"] == current_cls["answer_type"]
        and constraint_signature_similarity(
            cached_entry["constraint_sig"],
            constraint_signature(current_graph)
        ) >= 0.98
        and critical_constants_match(
            cached_entry["constants"],
            current_graph.get("knowns", [])
        )
    )
```

## [S7] PreSolve Context 最终格式

Guard Layer 输出的强类型对象，供 Router、Solver、Verifier、Formatter 共用：

```json
{
  "problem_id": "sha256:9b2c...",
  "normalized": {
    "clean_text": "求解 u_t = u_xx, 0<x<1, u(0,t)=u(1,t)=0, u(x,0)=sin(pi x)",
    "latex_blocks": ["u_t = u_{xx}", "u(0,t)=u(1,t)=0", "u(x,0)=\\sin(\\pi x)"],
    "symbols": ["u_t", "u_xx", "x", "t", "pi"],
    "answer_type": "closed_form_or_series",
    "is_proof": false
  },
  "constraint_graph": {
    "variables": ["x", "t"],
    "unknowns": ["u(x,t)"],
    "domain_constraints": ["0 < x < 1", "t > 0"],
    "boundary_constraints": ["u(0,t)=0", "u(1,t)=0"],
    "initial_constraints": ["u(x,0)=sin(pi x)"]
  },
  "risk": {
    "complexity_score": 0.78,
    "risk_tags": ["pde", "boundary_condition", "series_form"],
    "needs_tool": true,
    "needs_verifier": true,
    "answer_shape_certainty": 0.91
  },
  "classification": {
    "domain": "PDE",
    "problem_type": "heat_equation_dirichlet_1d",
    "confidence": 0.88,
    "alternatives": [{"type": "sturm_liouville", "score": 0.31}]
  },
  "retrieval": {
    "similar_cases": [
      {
        "case_id": "PDE_HEAT_DIRICHLET_1D_014",
        "score": 0.84,
        "method": "separation_of_variables",
        "answer_pattern": "sum b_n exp(-n^2 pi^2 t) sin(n pi x)"
      }
    ],
    "method_templates": [
      {
        "template_id": "FOURIER_SINE_HEAT",
        "applicable_if": ["Dirichlet boundary", "1D heat equation"],
        "avoid_if": ["non-homogeneous boundary"],
        "key_checks": ["PDE substitution", "BC", "IC"]
      }
    ]
  },
  "precompute": {
    "symbolic_candidates": ["u(x,t)=exp(-pi^2 t) sin(pi x)"],
    "numeric_sanity": {"bc_check": true, "ic_check": true},
    "verification_hooks": ["substitute_into_pde", "check_boundary_conditions", "check_initial_condition"]
  },
  "fusion": {
    "route": "standard",
    "pre_llm_confidence": 0.86,
    "conflict_flags": []
  }
}
```

## [S8] 预期性能提升

| 指标 | 当前 (Single) | 优化后 (自适应) | 提升 |
|------|-------------|----------------|------|
| 简单题延迟 | 2-3 min | 15-30s | **6-12x** |
| 中等题延迟 | 3-4 min | 45-90s | **2-4x** |
| 复杂题延迟 | 4-5 min | 2-5 min | ~1x (不变) |
| 平均 LLM 调用 | 7-16 次 | 1-7 次 | **50-80%** |
| 180 题全测 | 6-15 小时 | 2-5 小时 | **3x** |
| 准确率 | 0.9-0.95 | ≥0.9 | **不降** |

**假设**: 180 题中约 40% 简单、40% 中等、20% 复杂。

## [S9] 评测方案

不要只看最终 pass@1，评测必须拆成五类指标：

### Guard 质量
- 题型分类准确率
- 答案形态预测准确率
- 复杂度路由准确率
- 检索命中率
- 工具预计算成功率

### 端到端效果
- pass@1、pass@k、Best-of-N uplift

### 反幻觉指标
- 步骤级 unsupported rate
- 工具打脸率
- verifier 复判翻案率

### 校准指标
- Brier score
- ECE (Expected Calibration Error)
- 路由后真实成功率对齐程度

### 效率指标
- 平均 LLM 次数
- 平均工具次数
- 平均延迟
- 缓存命中收益

### Ablation 实验

| 实验组 | 目的 |
|--------|------|
| 无 Guard，直接 Solver | 基线 |
| Guard 但无检索 | 题型/复杂度/预计算本身贡献 |
| Guard + 检索，无工具预计算 | RAG / 相似题召回贡献 |
| Guard + 工具预计算，无检索 | 工具对数值/代数类题的贡献 |
| Standard 路径无 Verifier | verifier 是否真有增益 |
| Complex 路径只做 self-reflection | 验证"纯自反思是否足够" |
| 全链路 strict JSON | 推理性能是否下降 |
| 只对控制平面 strict JSON | 对照最优工程方案 |

## 实现计划概览

### Phase 1: Guard Layer 基础
1. Problem Normalizer + Constraint Graph
2. Complexity & Risk Estimator (规则部分)
3. 题型模板库 + Hybrid Type Matcher

### Phase 2: 预解答系统
4. Local Precompute (SymPy/NumPy 集成, 四类先验)
5. Method Router + 路由表
6. Calibrated Router (cold-start 规则)

### Phase 3: 自适应流水线
7. 四条路由路径 (simple/standard/complex/safe_fallback)
8. PreSolve Context 生成 + 证据预算
9. Answer Canonicalizer

### Phase 4: Prompt 契约
10. Solver/Verifier/Reflection/Formatter 四套 Prompt
11. 双通道策略（控制平面 JSON + 推理平面 freeform）

### Phase 5: 优化细节
12. ToolAgent 并行化
13. 结构化缓存（constraint_signature + answer_type + domain）
14. Hybrid Retriever (BM25 + embedding + 结构重排)

### Phase 6: 评测与校准
15. 五类指标评测框架
16. Ablation 实验
17. Calibrated Router 离线训练
18. 端到端 180 题测试验证
