"""Full 180-problem test runner with real API."""
import sys
import json
import time
import os
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from user_agent import ReasoningAgent
from agents.base import BaseAgent
from config.settings import settings

class RealClient:
    """Async LLM client that works within the pipeline's event loop."""
    def __init__(self):
        from utils.llm_client import LLMClient
        self._client = LLMClient()

    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        return await self._client.chat(messages, temperature, max_tokens)

OUTPUT_DIR = Path(__file__).parent / "test_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

with open(Path(__file__).parent / "test_problems.json", encoding="utf-8") as f:
    data = json.load(f)

problems = data["problems"]
total = len(problems)

print(f"Loading {total} problems...", flush=True)
print(f"Model: {settings.model_name}", flush=True)
print(f"API: {settings.api_url}", flush=True)
print(f"Output: {OUTPUT_DIR}", flush=True)
print("=" * 60, flush=True)

client = RealClient()
agent = ReasoningAgent(client=client)
# Override adapter: RealClient.chat is already async, no need for to_thread wrapper
BaseAgent._shared_llm = client

results_summary = {"total": total, "success": 0, "error": 0, "skipped": 0}
start_all = time.time()

for i, prob in enumerate(problems):
    idx = prob["idx"]
    out_file = OUTPUT_DIR / f"{idx}.json"

    if out_file.exists() and out_file.stat().st_size > 0:
        results_summary["skipped"] += 1
        continue

    subject = prob.get("subject", "unknown")
    problem_text = prob["problem"]
    expected = prob["answer"]

    print(f"\n[{i+1}/{total}] idx={idx} [{subject}]", flush=True)
    print(f"  Problem: {problem_text[:80]}...", flush=True)

    start = time.time()
    try:
        result = agent.solve(problem_text, {"idx": idx})
        elapsed = time.time() - start

        fr = result.get("final_response", "")
        output = {
            "idx": idx,
            "subject": subject,
            "problem": problem_text,
            "expected_answer": expected,
            "final_response": fr,
            "trace": result.get("trace", []),
            "elapsed_seconds": round(elapsed, 1),
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        status = "OK" if fr.strip() else "EMPTY"
        print(f"  Result: {status} ({elapsed:.1f}s) -> {fr[:100]}", flush=True)
        results_summary["success"] += 1

    except Exception as e:
        elapsed = time.time() - start
        output = {
            "idx": idx,
            "subject": subject,
            "problem": problem_text,
            "expected_answer": expected,
            "error": str(e),
            "elapsed_seconds": round(elapsed, 1),
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  ERROR: {e}", flush=True)
        results_summary["error"] += 1

total_time = time.time() - start_all
print("\n" + "=" * 60, flush=True)
print(f"DONE in {total_time/60:.1f} minutes", flush=True)
print(f"Total: {results_summary['total']}", flush=True)
print(f"Success: {results_summary['success']}", flush=True)
print(f"Error: {results_summary['error']}", flush=True)
print(f"Skipped: {results_summary['skipped']}", flush=True)

summary_file = OUTPUT_DIR / "_summary.json"
with open(summary_file, "w", encoding="utf-8") as f:
    json.dump(results_summary, f, ensure_ascii=False, indent=2)
print(f"\nSummary saved to {summary_file}", flush=True)
