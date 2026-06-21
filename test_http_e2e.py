"""HTTP-level end-to-end test of the backend API."""
import requests
import json
import time

BASE = "http://localhost:8000/api"

# Test: simple algebra problem
problem = "求解方程 2x + 3 = 7，求 x 的值。"
print(f"问题: {problem}")
print(f"发送 POST /api/solve ...")

start = time.time()
resp = requests.post(f"{BASE}/solve", json={
    "problem": problem,
    "stream": False,
}, timeout=120)
elapsed = time.time() - start

print(f"状态码: {resp.status_code}")
print(f"耗时: {elapsed:.1f}s")

if resp.status_code == 200:
    data = resp.json()
    print(f"\n--- 结果 ---")
    print(f"problem_id: {data.get('problem_id', 'N/A')}")
    print(f"final_answer: {data.get('final_answer', 'N/A')}")
    print(f"domain: {data.get('domain', 'N/A')}")
    print(f"problem_type: {data.get('problem_type', 'N/A')}")
    print(f"difficulty: {data.get('difficulty', 'N/A')}")
    print(f"confidence: {data.get('confidence', 'N/A')}")
    print(f"verification: {data.get('verification_status', 'N/A')}")
    print(f"processing_time_ms: {data.get('processing_time_ms', 'N/A')}")
    
    metadata = data.get("metadata", {})
    if metadata:
        print(f"\n--- 元数据 ---")
        print(f"mode: {metadata.get('mode', 'N/A')}")
        print(f"pre_llm_confidence: {metadata.get('pre_llm_confidence', 'N/A')}")
    
    print(f"\n--- reasoning_steps ({len(data.get('reasoning_steps', []))}) ---")
    for i, step in enumerate(data.get("reasoning_steps", [])[:5]):
        desc = step.get("description", "")[:80]
        print(f"  [{i}] {desc}")
else:
    print(f"错误: {resp.text[:500]}")
