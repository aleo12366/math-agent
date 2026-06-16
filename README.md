# Math Agent System v3.0

基于 Intern-S1 的自适应多智能体数学推理系统。通过 Pre-LLM Guard Layer 实现问题自动分级，按复杂度选择最优求解路径。

## 架构

```
数学问题
  ↓
Pre-LLM Guard Layer（本地 <100ms，零 LLM 调用）
  ├─ 文本规范化 + 约束图抽取
  ├─ 复杂度评估 + 风险路由
  ├─ 题型匹配（规则 + 模板 + 模糊检索）
  ├─ 本地符号/数值预计算
  └─ 相似题检索（BM25 + TF-IDF + 结构重排）
  ↓
路由决策
  ├─ simple:       solver → format                （1 次 LLM，15-30s）
  ├─ standard:     planner → solver → verifier    （3 次 LLM，45-90s）
  ├─ complex:      solver×N → canonicalize → verify → consensus → reflect（6 次 LLM，2-3min）
  └─ safe_fallback: solver×N → tool crosscheck → verify → flag uncertainty
  ↓
结构化输出
```

**双通道策略**：控制平面（Guard/Router/Verifier/Formatter）用严格 JSON；推理平面（Solver）用自由自然语言推理。

## 快速开始

### 1. 配置 API

```bash
cd backend
cp .env.example .env
```

编辑 `.env`，填入 3 个必填项：

```env
MATH_AGENT_API_URL=https://internlm.intern-ai.org.cn/api/v1/chat/completions
MATH_AGENT_API_KEY=sk-xxxxxxxx
MATH_AGENT_MODEL_NAME=Intern-S1
```

### 2. 启动后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
python main.py
```

后端启动后访问 http://localhost:8000/docs 查看 API 文档。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 使用。

### 4. Docker 部署（可选）

```bash
docker-compose up --build
```

- 前端: http://localhost:3000
- 后端: http://localhost:8000

## 项目结构

```
math-agent/
├── user_agent.py               # 竞赛入口（ReasoningAgent）
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── guard/                  # Pre-LLM Guard Layer（零 LLM 调用）
│   │   ├── normalizer.py       #   文本规范化 + 约束图抽取
│   │   ├── complexity.py       #   多维度风险评估
│   │   ├── type_matcher.py     #   规则 + 模板 + 模糊匹配
│   │   ├── precompute.py       #   SymPy/NumPy 本地预计算
│   │   ├── retriever.py        #   BM25 + TF-IDF 检索
│   │   ├── router.py           #   校准路由器（四路由决策）
│   │   ├── context_builder.py  #   PreSolveContext 生成（主入口）
│   │   └── cache.py            #   结构化缓存
│   ├── pipeline/
│   │   ├── adaptive.py         #   自适应流水线
│   │   ├── canonicalizer.py    #   答案归一化器
│   │   └── routes/             #   四条路由实现
│   │       ├── simple.py
│   │       ├── standard.py
│   │       ├── complex.py
│   │       ├── safe_fallback.py
│   │       └── _common.py
│   ├── agents/                 # LLM 智能体
│   │   ├── solver.py           #   求解器（freeform + JSON 双模式）
│   │   ├── verifier.py         #   验证器（6 维度）
│   │   ├── reflection.py       #   反思纠错
│   │   ├── planner.py          #   解题规划
│   │   ├── tool_agent.py       #   工具执行（并行）
│   │   └── formatter.py        #   格式化输出
│   ├── tools/                  # 数学工具
│   │   ├── symbolic.py         #   SymPy 符号计算
│   │   └── numerical.py        #   SciPy 数值计算
│   ├── data/
│   │   ├── templates/          #   题型模板库（18 学科）
│   │   └── problem_bank/       #   相似题库
│   ├── config/                 # 配置 + Prompt 模板
│   ├── api/                    # REST + SSE 端点
│   ├── eval/                   # 评测框架
│   └── tests/                  # 118 个测试
└── frontend/                   # React 18 + TypeScript
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/solve` | 求解数学问题（支持 SSE 流式） |
| POST | `/api/batch` | 批量求解（最多 10 题） |
| GET | `/api/config` | 获取配置 |
| PUT | `/api/config` | 更新配置 |
| POST | `/api/config/test` | 测试 API 连接 |
| GET | `/api/health` | 健康检查 |

## 竞赛集成

`user_agent.py` 提供竞赛平台所需的 `ReasoningAgent` 接口：

```python
from user_agent import ReasoningAgent

agent = ReasoningAgent(client=platform_client)
result = agent.solve("设f在凸区域Ω上全纯，且Re f'(z)>0...", metadata={})
# result = {"final_response": "...", "trace": [...]}
```

## 测试

```bash
cd backend
python -m pytest tests/ -v
```

118 个测试，覆盖 Guard Layer、路由、归一化器、缓存等模块。

## 技术栈

- **后端**: Python 3.11+ / FastAPI / SymPy / SciPy / rapidfuzz
- **前端**: React 18 / TypeScript / Vite / Zustand / Tailwind CSS / KaTeX
- **LLM**: Intern-S1（兼容 OpenAI 格式）

## License

MIT
