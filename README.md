# Math Agent System v2.0

基于 Intern-S1 的多智能体数学推理系统，支持9步流水线、6维验证、辩论共识模式。

## 🏗️ 架构概览

```
数学问题输入
    ↓
┌─────────────────────────────────────────────┐
│  9-Module Multi-Agent Pipeline              │
│                                             │
│  1. 问题理解 (Problem Understanding)        │
│  2. 问题分类 (Classification)               │
│  3. 知识定位 (Knowledge Locating)           │
│  4. 解题规划 (Planning)                     │
│  5. 求解推理 (Solving)  ←→ 工具调用        │
│  6. 结果验证 (Verification) - 6维度         │
│  6.5 反思纠错 (Reflection) → 重试循环       │
│  7. 教育解释 (Explanation)                  │
│  8. 格式化输出 (Formatting)                 │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  React Frontend (Magic Paste UI)            │
│  • KaTeX 数学渲染                           │
│  • SSE 实时进度流                           │
│  • 智能粘贴内容检测                         │
│  • 5-Tab 结果展示                           │
└─────────────────────────────────────────────┘
```

## 🚀 快速开始

### 前置要求

- Python 3.11+（推荐 3.11，NumPy/SciPy 有预编译 wheel）
- Node.js 18+
- Intern-S1 API Key（见下方获取教程）

### 第 1 步：获取 API Key

本系统需要接入 Intern-S1 (或兼容 OpenAI 格式的 LLM) API。以下是几种获取方式：

#### 方式 A：InternLM 官方平台（推荐）
1. 访问 [InternLM 开放平台](https://internlm.intern-ai.org.cn/) 或 [书生浦语](https://chat.intern-ai.org.cn/)
2. 注册/登录账号
3. 进入 **个人中心** → **API Key 管理**
4. 点击 **创建 API Key**，复制生成的密钥
5. API 地址通常是: `https://internlm.intern-ai.org.cn/api/v1/chat/completions`（以平台实际地址为准）

#### 方式 B：自部署 Intern-S1
1. 使用 LMDeploy/vLLM 部署 Intern-S1 模型
2. 部署时设置 API 密钥（如 `--api-key your-key`）
3. API 地址为你的服务地址，如 `http://localhost:23333/v1/chat/completions`

#### 方式 C：第三方平台
以下平台提供 Intern-S1 或兼容模型的 API：
- **SiliconFlow** (硅基流动): [siliconflow.cn](https://siliconflow.cn/) → 获取 API Key
- **OpenRouter**: [openrouter.ai](https://openrouter.ai/) → 选择模型获取 Key
- **阿里云百炼/通义**: 提供兼容接口

#### 方式 D：使用其他兼容模型
本系统兼容任何 OpenAI 格式的 API，也支持：
- DeepSeek: [platform.deepseek.com](https://platform.deepseek.com/)
- OpenAI: [platform.openai.com](https://platform.openai.com/)
- 其他 OpenAI 兼容 API

### 第 2 步：配置 API Key

有两种方式配置 API Key（推荐方式 A）：

#### 方式 A：通过前端设置页面配置（推荐）

1. 先用默认配置启动后端（第 3 步）
2. 打开前端 http://localhost:5173/settings
3. 在 **🔗 API 连接配置** 区域填入：
   - **API 地址**：你的 LLM API 端点
   - **API Key**：你的密钥
   - **模型名称**：如 Intern-S1
4. 点击 **保存设置** — 配置会自动持久化到 `.env` 文件，重启后仍然生效

#### 方式 B：手动编辑 .env 文件

```bash
cd math-agent/backend
copy .env.example .env     # Windows
# cp .env.example .env     # macOS/Linux
```

然后用文本编辑器打开 `.env` 文件，**填入 3 个必填项**：

```env
# ⬇️ 修改为你自己的 API 地址
MATH_AGENT_API_URL=https://internlm.intern-ai.org.cn/api/v1/chat/completions

# ⬇️ 修改为你自己的 API Key（粘贴即可，不要加引号）
MATH_AGENT_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ⬇️ 修改为你要使用的模型名称
MATH_AGENT_MODEL_NAME=Intern-S1
```

> **💡 提示**:
> - `.env.example` 文件中有完整的中文注释说明每个配置项的含义
> - 从前端设置页面保存的配置会自动写入 `.env` 文件
> - API Key 在前端显示时会被脱敏处理（如 `sk-1234****abcd`），不会泄露完整密钥

### 第 3 步：安装依赖并启动后端

```bash
cd math-agent/backend

# (推荐) 创建虚拟环境
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # macOS/Linux

# 升级 pip（避免安装 numpy/scipy 时出错）
python -m pip install --upgrade pip setuptools wheel

# 安装依赖
pip install -r requirements.txt

# 启动后端服务
python main.py
```

后端启动成功后会显示:
```
INFO:     Starting Math Agent System v2.0.0
INFO:     Model: Intern-S1
INFO:     Uvicorn running on http://0.0.0.0:8000
```

访问 http://localhost:8000/docs 可查看 API 文档。

> **⚠️ Windows 安装问题**: 如果 `pip install` 时 NumPy/SciPy 编译失败，请确保:
> 1. Python 版本为 3.11（有预编译 wheel）
> 2. pip 已升级到最新版: `python -m pip install --upgrade pip`
> 3. 如果仍失败，尝试 `conda install numpy scipy sympy` 后再 `pip install -r requirements.txt`

### 第 4 步：启动前端

**新开一个终端窗口**:

```bash
cd math-agent/frontend
npm install
npm run dev
```

前端启动后访问 http://localhost:5173 即可使用。

### 第 5 步：Docker 部署（可选）

先在项目根目录创建 `.env` 文件（同第 2 步），然后：

```bash
cd math-agent
docker-compose up --build
```

- 后端 API: http://localhost:8000
- 前端界面: http://localhost:3000
- API 文档: http://localhost:8000/docs

### 第 6 步：Windows 服务器部署（可选）

适用于 Windows Server 生产环境，使用 Nginx 反向代理 + Windows 服务自启动。

#### 方式 A：一键脚本部署（推荐）

**以管理员身份运行 PowerShell**：

```powershell
cd math-agent

# 1. 配置 API Key（必填）
notepad backend\.env

# 2. 一键部署（构建前端 + 安装 Nginx + 创建 Windows 服务）
.\deploy-windows.ps1 -All
```

部署完成后：
- 前端界面: http://localhost
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

> 服务自动随 Windows 启动，可通过 `services.msc` 管理 `MathAgentBackend` 和 `MathAgentNginx` 两个服务。

#### 方式 B：手动部署

**1. 构建前端**
```powershell
cd frontend
npm install
npm run build
cd ..
```

**2. 配置后端**
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env 填入 API Key
cd ..
```

**3. 安装 Nginx**
- 从 https://nginx.org/en/download.html 下载 Windows 版 Nginx
- 解压到 `C:\nginx-mathagent`
- 将 `nginx-windows.conf` 复制到 `C:\nginx-mathagent\conf\nginx.conf`
- 将前端构建产物 `frontend/dist/` 复制到 `C:\nginx-mathagent\html\`

**4. 启动服务**
```powershell
# 启动后端
cd backend
venv\Scripts\activate
python main.py

# 启动 Nginx（另一个终端）
C:\nginx-mathagent\nginx.exe
```

#### 方式 C：Bat 快速启动（无需 Nginx）

双击运行 `deploy-windows.bat`，按提示操作。仅启动后端 + 前端开发服务器。

#### 管理命令

```powershell
# 启动服务
.\deploy-windows.ps1 -StartServices

# 停止服务
.\deploy-windows.ps1 -StopServices

# 重新构建前端并更新
.\deploy-windows.ps1 -BuildFrontend

# 查看服务状态
Get-Service MathAgent*
```

## 📁 项目结构

```
math-agent/
├── backend/                    # Python/FastAPI 后端
│   ├── main.py                # FastAPI 入口
│   ├── requirements.txt       # Python 依赖
│   ├── Dockerfile
│   ├── config/                # 配置
│   │   ├── settings.py        # Pydantic Settings
│   │   ├── schemas.py         # Pydantic 数据模型
│   │   └── prompts.py         # 20+ 提示词模板
│   ├── agents/                # 10 个智能体
│   │   ├── base.py            # BaseAgent 基类
│   │   ├── problem_understander.py  # 模块 1
│   │   ├── classifier.py      # 模块 2
│   │   ├── knowledge_locator.py # 模块 3
│   │   ├── planner.py         # 模块 4
│   │   ├── solver.py          # 模块 5
│   │   ├── tool_agent.py      # 工具执行
│   │   ├── verifier.py        # 模块 6
│   │   ├── reflection.py      # 模块 6.5
│   │   ├── explainer.py       # 模块 7
│   │   └── formatter.py       # 模块 8
│   ├── pipeline/              # 流水线
│   │   ├── base.py            # BasePipeline
│   │   ├── single.py          # 单智能体线性管线
│   │   └── multi.py           # 多智能体辩论管线
│   ├── api/                   # API
│   │   ├── routes.py          # REST + SSE 端点
│   │   └── event_bus.py       # SSE 事件总线
│   ├── tools/                 # 数学工具
│   │   ├── symbolic.py        # SymPy 符号计算
│   │   └── numerical.py       # SciPy 数值计算
│   └── utils/
│       ├── llm_client.py      # Intern-S1 API 客户端
│       ├── json_parser.py     # JSON 提取器
│       └── logger.py          # 结构化日志
├── frontend/                   # React 18 前端
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── Dockerfile
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── types/index.ts     # TypeScript 接口
│       ├── api/client.ts      # API + SSE 客户端
│       ├── store/             # Zustand 状态管理
│       ├── hooks/             # 自定义 Hooks
│       ├── utils/             # 工具函数
│       ├── components/        # 10 个组件
│       ├── pages/             # 3 个页面
│       └── styles/            # Tailwind CSS
├── docker-compose.yml
├── .gitignore
└── README.md
```

## 🔑 核心特性

### 9-Module Pipeline
每个问题经过9个专用智能体处理，每个智能体专注一个任务。

### 6-Dimension Verification
验证维度：公式一致性、边界条件、逻辑一致性、特殊情况、量纲检查、完整性。

### Debate Mode
N个求解器并行推理 → 共识投票 → 选择最佳答案。

### Magic Paste (灵感来源: MoganLab/mogan)
智能粘贴检测：自动识别 LaTeX、Markdown、HTML、代码等内容类型。

### SSE Streaming
实时推送流水线进度：阶段事件、步骤事件、完成事件。

## 📊 统一 JSON Schema

输出包含 14 个必需字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| domain | enum | 18个数学领域之一 |
| problem_type | enum | 6种题目类型之一 |
| difficulty | enum | easy/medium/hard |
| difficulty_score | float | 0-1 |
| reasoning_plan | list | 解题计划步骤 |
| key_steps | list | 推理步骤 |
| final_answer | string | 最终答案 |
| final_answer_latex | string | LaTeX 答案 |
| answer_format | enum | 15种格式之一 |
| confidence | float | 0-1 |
| verification_status | enum | pass/fail/uncertain |
| verification_details | object | 6维验证详情 |
| educational_explanation | string | Markdown 解释 |
| token_usage_estimate | object | Token 使用统计 |

## 🧪 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/solve | 求解数学问题（支持 SSE 流式） |
| POST | /api/batch | 批量求解 |
| GET | /api/config | 获取配置 |
| PUT | /api/config | 更新配置 |
| GET | /health | 健康检查 |
| GET | /docs | Swagger 文档 |

## 🏆 评分策略

| 维度 | 权重 | 本系统策略 |
|------|------|-----------|
| 答案正确性 | 60% | 6维验证 + 反思重试循环 + 辩论共识 |
| 展示质量 | 20% | React UI + KaTeX + SSE流式 + 5-Tab展示 |
| 创新与可扩展 | 10% | 辩论模式 + Magic Paste + 领域自适应 |
| 推理策略 | 10% | 9模块结构化管线 + 工具调用 |

## 📝 License

MIT