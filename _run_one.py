"""Run a single problem through the pipeline."""
import sys, json, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from user_agent import ReasoningAgent
from agents.base import BaseAgent
from utils.llm_client import LLMClient

class RealClient:
    def __init__(self):
        self._client = LLMClient()
    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        return await self._client.chat(messages, temperature, max_tokens)

client = RealClient()
agent = ReasoningAgent(client=client)
BaseAgent._shared_llm = client

problem = (
    "4. 设 D:|z|<1 是单位圆盘，f:D->D 是全纯函数。\n"
    "(1) 证明：对任意 z1,z2 属于 D，有\n"
    "|(f(z1)-f(z2))/(1-conj(f(z2))*f(z1))| <= |(z1-z2)/(1-conj(z2)*z1)|\n"
    "(2) 证明：对任意 z1 属于 D，有\n"
    "|f'(z1)| <= (1-|f(z1)|^2) / (1-|z1|^2)"
)

print("Solving Schwarz-Pick lemma...", flush=True)
start = time.time()
result = agent.solve(problem, {"idx": "custom_schwarz_pick"})
elapsed = time.time() - start

print("", flush=True)
print("=" * 60, flush=True)
print("Time: " + str(round(elapsed, 1)) + "s", flush=True)
print("", flush=True)
fr = result.get("final_response", "")
print("final_response:", flush=True)
print(repr(fr), flush=True)
print("", flush=True)
print("All result keys:", flush=True)
for k, v in result.items():
    if k == "trace":
        continue
    print("  " + k + ": " + repr(v)[:200], flush=True)
print("", flush=True)
print("Trace:", flush=True)
for t in result.get("trace", []):
    step = t.get("step", "")
    content = str(t.get("content", ""))[:500]
    print("  [" + step + "] " + content, flush=True)

# Save full result
with open("test_outputs/custom_schwarz_pick.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("", flush=True)
print("Saved to test_outputs/custom_schwarz_pick.json", flush=True)
