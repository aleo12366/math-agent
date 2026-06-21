"""Quick end-to-end test of the full Guard Layer pipeline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from guard.context_builder import build_presolve_context
from guard.type_matcher import hybrid_classify
from guard.normalizer import normalize_problem, build_constraint_graph

test_cases = [
    # (problem_text, expected_domain, expected_route_hint)
    ("求解 2x + 3 = 7", "代数", "simple"),
    ("求解方程组 x+y=5, x-y=1", "代数", None),
    ("计算积分 ∫₀¹ x² dx", "微积分", None),
    ("证明三角形内角和为180度", "几何", None),
    ("求矩阵 A=[[1,2],[3,4]] 的行列式", "线性代数", None),
    ("求偏微分方程 u_t = u_xx 的通解", "偏微分方程", None),
    ("已知随机变量X服从正态分布N(0,1)，求P(X>1)", "概率统计", None),
    ("证明费马小定理", "数论", None),
    ("从10个人中选出3个人的组合数", "离散数学", None),
    ("求级数 Σ(1/n²) 的和", "微积分", None),  # series_form trigger
    ("求函数 f(x)=x³-3x 的最大值", "优化", None),  # optimization trigger
    ("hello world", None, None),  # no match — domain should be empty/first
]

print("=" * 80)
print("Guard Layer 全流程测试")
print("=" * 80)

pass_count = 0
fail_count = 0

for problem, expected_domain, expected_route in test_cases:
    print(f"\n--- {problem[:50]} ---")
    
    # Run the full guard pipeline
    ctx = build_presolve_context(problem)
    
    cls = ctx["classification"]
    fusion = ctx["fusion"]
    risk = ctx["risk"]
    normalized = ctx["normalized"]
    precompute = ctx["precompute"]
    
    domain = cls.get("domain", "unknown")
    confidence = cls.get("confidence", 0.0)
    route = fusion.get("route", "standard")
    pre_llm_conf = fusion.get("pre_llm_confidence", 0.0)
    risk_score = risk.get("complexity_score", 0.0)
    risk_tags = risk.get("risk_tags", [])
    answer_type = normalized.get("answer_type", "unknown")
    
    # Check domain
    domain_ok = True
    if expected_domain is not None:
        domain_ok = (domain == expected_domain)
        if not domain_ok:
            fail_count += 1
        else:
            pass_count += 1
    
    # Check route if expected
    route_ok = True
    if expected_route:
        route_ok = (route == expected_route)
        if not route_ok:
            fail_count += 1
        else:
            pass_count += 1
    
    status_d = "✅" if (expected_domain is None or domain_ok) else "❌"
    status_r = ""
    if expected_route:
        status_r = " ✅" if route_ok else f" ❌ (got {route})"
    
    if expected_domain is not None:
        print(f"  domain: {domain:20s} (expect {expected_domain:20s}) {status_d}")
    else:
        print(f"  domain: {domain}")
    if expected_route:
        print(f"  route:  {route:20s} (expect {expected_route:20s}){status_r}")
    else:
        print(f"  route:  {route}")
    print(f"  confidence: {confidence:.3f}, risk: {risk_score:.3f}, pre_llm: {pre_llm_conf:.3f}")
    print(f"  risk_tags: {risk_tags}")
    print(f"  answer_type: {answer_type}")
    print(f"  precompute: {list(precompute.keys())}")

print("\n" + "=" * 80)
total = pass_count + fail_count
print(f"结果: {pass_count}/{total} passed, {fail_count} failed")
print("=" * 80)
