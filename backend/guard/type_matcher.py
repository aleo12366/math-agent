"""Hybrid Type Matcher — rule + template + fuzzy matching for math problem classification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "templates"

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "代数": ["方程", "求解", "求解方程", "计算", "化简", "equation", "solve", "代数", "algebra",
             "不等式", "inequality", "因式分解", "factor", "多项式", "polynomial"],
    "微积分": ["积分", "integral", "导数", "derivative", "极限", "limit", "微积分", "calculus",
              "微分", "differentiate", "求导", "∫", "∑", "级数", "series"],
    "偏微分方程": ["偏微分方程", "PDE", "pde", "热方程", "heat equation", "波动方程", "wave equation",
                 "拉普拉斯方程", "laplace equation", "∂u/∂t", "∂²u", "偏微分", "扩散方程"],
    "线性代数": ["矩阵", "matrix", "行列式", "determinant", "特征值", "eigenvalue",
               "特征向量", "eigenvector", "线性代数", "linear algebra", "向量", "vector",
               "方程组", "system of equations", "线性方程组"],
    "概率统计": ["概率", "probability", "期望", "expectation", "方差", "variance",
               "分布", "distribution", "统计", "statistics", "随机", "random"],
    "离散数学": ["组合", "combination", "排列", "permutation", "图论", "graph theory",
               "逻辑", "logic", "集合", "set", "递推", "recurrence"],
    "数论": ["素数", "prime", "整除", "divisible", "同余", "congruence", "数论",
            "number theory", "欧拉", "euler", "费马", "fermat"],
    "几何": ["三角形", "triangle", "圆", "circle", "角度", "angle", "几何", "geometry",
            "面积", "area", "体积", "volume", "坐标", "coordinate"],
    "拓扑": ["拓扑", "topology", "连续", "continuous", "同胚", "homeomorphism",
            "紧致", "compact", "连通", "connected"],
    "泛函分析": ["泛函", "functional", "希尔伯特", "hilbert", "巴拿赫", "banach",
               "算子", "operator", "范数", "norm"],
    "实分析": ["测度", "measure", "勒贝格", "lebesgue", "可测", "measurable",
              "实分析", "real analysis"],
    "复分析": ["复数", "complex", "留数", "residue", "解析", "analytic",
              "柯西", "cauchy", "黎曼", "riemann"],
    "微分方程": ["常微分方程", "ODE", "ode", "微分方程", "differential equation",
               "初值问题", "initial value", "边值问题", "boundary value"],
    "优化": ["最优化", "optimization", "拉格朗日", "lagrange", "极值", "extremum",
            "最大", "最小", "最值", "最大值", "最小值",
            "约束", "constraint", "目标函数", "objective"],
    "数值分析": ["数值", "numerical", "近似", "approximate", "迭代", "iteration",
               "误差", "error", "收敛", "convergence"],
    "数学物理": ["物理", "physics", "力学", "mechanics", "电磁", "electromagnetic",
               "量子", "quantum", "相对论", "relativity"],
}

_templates_cache: list[dict[str, Any]] | None = None


def _load_templates() -> list[dict[str, Any]]:
    global _templates_cache
    if _templates_cache is not None:
        return _templates_cache

    templates: list[dict[str, Any]] = []
    if not _TEMPLATE_DIR.is_dir():
        _templates_cache = templates
        return templates

    for jsonl_file in sorted(_TEMPLATE_DIR.glob("*.jsonl")):
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    templates.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    _templates_cache = templates
    return templates


def _rule_classify(text: str) -> list[tuple[str, float]]:
    """Rule-based keyword matching. Returns list of (domain, score)."""
    lower = text.lower()
    results: list[tuple[str, float]] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lower or kw in text)
        if hits > 0:
            score = min(hits * 0.25 + 0.3, 1.0)
            results.append((domain, score))
    return sorted(results, key=lambda x: -x[1])


def _template_match(text: str) -> list[tuple[str, str, float]]:
    """Template matching via rapidfuzz. Returns list of (domain, problem_type, score)."""
    if process is None:
        return []

    templates = _load_templates()
    if not templates:
        return []

    results: list[tuple[str, str, float]] = []
    for tmpl in templates:
        patterns = tmpl.get("patterns", [])
        best_score = 0.0
        for pat in patterns:
            score = fuzz.partial_ratio(text.lower(), pat.lower()) / 100.0
            if score > best_score:
                best_score = score
        if best_score > 0.4:
            adjusted = best_score * 0.85
            results.append((tmpl["domain"], tmpl["problem_type"], adjusted))

    return sorted(results, key=lambda x: -x[2])


def _structural_rerank(
    rule_hits: list[tuple[str, float]],
    template_hits: list[tuple[str, str, float]],
) -> dict[str, Any]:
    """Deduplicate by domain, keep highest confidence, merge results."""
    domain_scores: dict[str, tuple[float, str]] = {}

    for domain, score in rule_hits:
        if domain not in domain_scores or score > domain_scores[domain][0]:
            domain_scores[domain] = (score, "rule")

    for domain, problem_type, score in template_hits:
        if domain not in domain_scores or score > domain_scores[domain][0]:
            domain_scores[domain] = (score, "template")

    if not domain_scores:
        return {
            "domain": "未知",
            "problem_type": "未分类",
            "confidence": 0.0,
            "alternatives": [],
        }

    sorted_domains = sorted(domain_scores.items(), key=lambda x: -x[1][0])
    best_domain, (best_score, _source) = sorted_domains[0]

    best_problem_type = "未分类"
    for domain, problem_type, _score in template_hits:
        if domain == best_domain:
            best_problem_type = problem_type
            break

    alternatives = [
        {"domain": d, "confidence": round(s, 4)}
        for d, (s, _src) in sorted_domains[1:4]
    ]

    return {
        "domain": best_domain,
        "problem_type": best_problem_type,
        "confidence": round(best_score, 4),
        "alternatives": alternatives,
    }


def hybrid_classify(
    text: str,
    symbols: list[str] | None = None,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify a math problem using rule-based + template + fuzzy matching.

    Args:
        text: Problem text (typically clean_text from normalizer).
        symbols: Extracted symbols from normalizer.
        constraints: Constraint graph from build_constraint_graph.

    Returns:
        dict with keys: domain, problem_type, confidence, alternatives
    """
    rule_hits = _rule_classify(text)
    template_hits = _template_match(text)
    result = _structural_rerank(rule_hits, template_hits)

    if constraints:
        if constraints.get("has_pde") and result["domain"] != "偏微分方程":
            pde_score = 0.9
            if pde_score > result["confidence"]:
                result["domain"] = "偏微分方程"
                result["problem_type"] = "偏微分方程"
                result["confidence"] = pde_score
                result["alternatives"] = [
                    {"domain": result["domain"], "confidence": result["confidence"]}
                ]

    return result
