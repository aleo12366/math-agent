# Guard Layer 架构升级 — 变更与回归分析报告

> 日期：2026-06-16  
> 范围：Pre-LLM Guard Layer 全模块  
> 测试状态：118 passed / 0 failed（单元测试）  
> 功能回归：2 处已修复（见第七节）

---

## 一、背景：架构重写而非 Bug 修复

本次变更的本质是 **Guard 层架构全面重写**（从 ~800 行扩展到 ~4000 行），而非对旧代码 bug 的修复。旧版 Guard 层是一套自洽、可工作的系统，新版引入了更丰富的抽象（`ConstraintGraph` dataclass、`RISK_TRIGGERS` 机制、规则+结构分类器、`ConfidenceCalibrator` 校准层），重写过程中产生了一些适配问题，被包装为"修复"。

### 变更性质分类

| 类别 | 说明 | 数量 |
|------|------|------|
| 新架构适配 | 重写后新旧 API 不兼容的补丁 | 10 |
| 新设计补全 | 新模块中遗漏的功能点 | 3 |
| 测试更新 | 测试用例适配新 API | 6 |
| 真正的 Bug | 旧代码或新代码中确实存在的缺陷 | 2 |

---

## 二、新架构适配（10 项）

这些变更是重写引入的不兼容，不是旧代码的 bug。

### 2.1 ConstraintGraph 字段重命名

旧代码直接使用 `target`、`has_proof` 作为字段名。新版引入 `ConstraintGraph` dataclass 后改为 `objective`、`is_proof`，导致下游模块（precompute、complexity）需要添加双键兼容：

```python
# precompute.py — 三处双键检查
graph.get("target") or graph.get("objective")
graph.get("has_proof") or graph.get("is_proof")

# normalizer.py — 包装层别名
d["target"] = d.get("objective")
d["has_proof"] = d.get("is_proof", False)
```

### 2.2 CalibratedRouter 双模式 API

旧版 Router 直接处理 flat features（`type_confidence`、`complexity_score` 等）。新版引入 `ConfidenceCalibrator` 接受结构化字典（`risk`、`classification`、`retrieval`、`precompute`）。为保持向后兼容，`CalibratedRouter.predict()` 同时支持两种 API：

- 旧式 flat API → `_synthesize_*` 方法转换为结构化字典 → 校准后注入后处理标志
- 新式结构化 API → 直接传入 `ConfidenceCalibrator`

旧版 Router 的 `guard_parse_failed` 处理是 `predict()` 内的 early return，逻辑正确。新版因拆分为 Calibrator 层，需要后处理注入来保持等价行为。

### 2.3 分类器 Domain 命名

旧版 `hybrid_classify` 返回中文域名（`"代数"`、`"微积分"`）。新版改为英文 slug（`algebra_basic`、`calculus_single`），导致测试断言需扩展为接受两种格式。

### 2.4 ANSWER_TYPE_INDICATORS 排序

旧版用 if/elif 链预测答案类型。新版改为有序字典迭代，需显式控制优先级（proof → numeric → ... → closed_form），并修正 `"simplify"` 在 `numeric` 和 `closed_form` 中的冗余。

---

## 三、新设计补全（3 项）

这些是新架构中遗漏的功能点，在对比设计文档后发现。

### 3.1 Retriever 约束复杂度键名

`_structural_rerank` 中使用了不存在的键 `"constraints"`。`ConstraintGraph` 的实际字段是 `equality_constraints` 等具体类型。导致 `query_complexity` 永远为 0。

```python
# 修复前
query_complexity = len(constraint_graph.get("constraints", []))

# 修复后 — 汇总所有约束类型
query_complexity = sum(
    len(constraint_graph.get(k, []))
    for k in ("equality_constraints", "inequality_constraints",
              "boundary_constraints", "domain_constraints", "initial_constraints")
)
```

### 3.2 Complexity 风险触发器

新增 `series_form`（级数）和 `optimization`（最优化）触发器，以及 `_NORMALIZED_TRIGGERS` frozenset 统一分发。

### 3.3 Normalizer 默认值

`_predict_answer_type` 无匹配时默认从 `"expression"` 改为 `"unknown"`（诚实表达不确定性）。

---

## 四、已发现的功能回归（2 处未修复）

### 4.1 type_matcher 中文关键词缺失

**现象**：`hybrid_classify("求解 2x + 3 = 7")` 返回 `pde`（置信度 0.2），应为 `algebra_basic`。

**根因**：`algebra_basic` 关键词列表包含英文 `"solve"` 但缺少中文 `"求解"`。当没有任何关键词匹配时，分类器退化为依赖结构分，而空约束图触发全域中性分 0.5，最终返回字母序第一个领域 `pde`。

**验证**：
```
"求解 2x + 3 = 7"     → pde (0.2)          ❌ 错误
"求解方程 2x + 3 = 7"  → algebra_basic (0.422) ✅ "方程"命中
"Solve 2x + 3 = 7"    → algebra_basic (0.422) ✅ "solve"命中
```

### 4.2 空约束图 fallback 逻辑错误

**现象**：`constraint_graph={}` 时，`_structural_match` 返回所有领域 0.5 中性分（设计意图：无数据时不做判断），但 `_fuse_scores` 将中性分与零规则分融合为 `0.0*0.6 + 0.5*0.4 = 0.2`，导致零命中时仍返回一个领域。

**预期行为**：零关键词命中时应返回 `domain="unknown", confidence=0.0`。

**影响范围**：所有不传 `constraint_graph` 的 `hybrid_classify` 调用，或约束图提取失败的场景。

---

## 五、测试变更

| 文件 | 变更性质 | 说明 |
|------|---------|------|
| `tests/test_routes.py` | 适配新 API | mock `generate_explanation`，更新 emit_stage 计数 |
| `tests/test_guard.py` | 适配新 API | 域名断言扩展、参数名修正、阈值调整、完整约束图 |

测试全部通过（118/0），但 **测试用例未覆盖 "求解" 等常见中文数学动词的分类准确性**。

---

## 六、变更文件清单

| 文件 | 变更类型 |
|------|---------|
| `guard/router.py` | 新架构适配（双模式 API + 标志转发 + 后处理） |
| `guard/normalizer.py` | 新架构适配（别名）+ 设计补全（排序、默认值） |
| `guard/complexity.py` | 设计补全（新增触发器） |
| `guard/retriever.py` | Bug fix（约束键名） |
| `guard/precompute.py` | 新架构适配（双键兼容） |
| `tests/test_routes.py` | 测试适配 |
| `tests/test_guard.py` | 测试适配 |

---

## 七、回归 Bug 修复（已完成）

### 7.1 `algebra_basic` 中文关键词缺失 ✅

添加了 `"求解"`、`"解方程"`、`"化简"`、`"计算"` 四个常见中文数学动词。

**修复效果**：
```
"求解 2x+3=7"        → algebra_basic (0.21) ✅
"求解方程 2x+3=7"     → algebra_basic (0.27) ✅
"计算积分 x^2 dx"     → calculus_single (0.215) ✅
```

### 7.2 空约束图 fallback 逻辑 ✅

`_structural_match` 在 `constraint_graph` 为空时返回全域 0.0（而非 0.5 中性分），使零关键词命中时 `_fuse_scores` 输出全域 0.0，最终返回 `domain="unknown", confidence=0.0`。

**修复效果**：
```
"hello world" → unknown (0.0) ✅
```
