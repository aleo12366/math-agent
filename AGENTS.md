# AGENTS.md — Math Agent System

## Project

Multi-agent math problem solver powered by Intern-S1 LLM. Python/FastAPI backend + React/Vite frontend. UI is entirely in Chinese (Simplified).

## Quick start

```bash
# Backend
cd backend
copy .env.example .env   # fill in MATH_AGENT_API_KEY and MATH_AGENT_API_URL
python -m venv venv && venv\Scripts\activate   # or source venv/bin/activate
pip install -r requirements.txt
python main.py            # runs on :8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev               # runs on :5173, proxies /api → :8000
```

## Commands

| What | Command | Where |
|------|---------|-------|
| Backend dev server | `python main.py` | `backend/` |
| Frontend dev server | `npm run dev` | `frontend/` |
| Frontend build | `npm run build` (runs `tsc && vite build`) | `frontend/` |
| Frontend preview | `npm run preview` | `frontend/` |
| Docker full stack | `docker compose up --build` | root |

**No test runner, linter, or formatter is configured.** There are no test files anywhere in the repo.

## Architecture

### Backend (`backend/`)

- **Framework**: FastAPI + Uvicorn, async throughout
- **Config**: `pydantic-settings` loaded from `.env` with prefix `MATH_AGENT_`
- **LLM client**: `utils/llm_client.py` — async aiohttp, OpenAI-compatible chat completions API
- **10 agents** in `agents/`: 8 LLM-based (extend `BaseAgent`), 2 pure-compute (`Formatter`, `ToolAgent`)
- **2 pipeline modes** in `pipeline/`:
  - `SinglePipeline` — linear 9-stage flow
  - `MultiPipeline` — N parallel solvers + consensus voting, then same verification path
- **Math tools**: `tools/symbolic.py` (SymPy), `tools/numerical.py` (SciPy/NumPy)
- **SSE streaming**: `api/event_bus.py` pub/sub, events: `stage`, `step`, `result`, `complete`, `error`
- **API routes** all under `/api`: `POST /api/solve` (SSE or JSON), `POST /api/batch`, `GET|PUT /api/config`, `POST /api/config/test`, `GET /api/health`
- **Prompts**: All in Chinese, defined in `config/prompts.py`

### Frontend (`frontend/`)

- **Stack**: React 18, TypeScript (strict), Vite 6, Tailwind CSS 3, Zustand 5
- **Routing**: `/` (Home), `/history`, `/settings` via react-router-dom v6
- **State**: `solveStore` (solve lifecycle + history), `configStore` (pipeline settings)
- **SSE client**: Manual `fetch` + `ReadableStream` parser (NOT `EventSource`) for streaming; non-streaming REST calls use axios
- **Path alias**: `@/*` → `src/*` (configured in `tsconfig.json`)
- **Math rendering**: KaTeX via `react-markdown` + `rehype-katex`, plus direct `katex.render()` in `LatexRenderer`
- **LaTeX sanitizer**: `utils/latexCleaner.ts` fixes common LLM output issues (double-escaped backslashes, delimiter normalization)

## Key gotchas

- **No `.env` in git** — must copy from `.env.example`. API key and URL are required or the LLM client will fail.
- **Python version mismatch**: Dockerfile uses Python 3.11; local venv may be 3.14. No known compat issues but be aware.
- **`implementation_plan.md` is aspirational**, not ground truth. Several files it lists don't exist (e.g., `MagicPasteArea.tsx`, `FileUpload.tsx`, `Layout.tsx`, `contentTransformer.ts`). Trust the actual filesystem.
- **All domain/type enums use Chinese strings** — e.g., `"微积分"` not `"calculus"`, `"计算"` not `"computation"`. When writing code that references these, match the Chinese values in `config/schemas.py`.
- **No database** — the system is stateless. Only persistence is `.env` for config.
- **Frontend `dist/` exists in git** — production build artifacts are committed.
- **CORS origins** default to `localhost:5173` and `localhost:3000` but are configurable via `MATH_AGENT_CORS_ORIGINS` env var (see `config/settings.py`).
- **Windows deploy**: `deploy-windows.ps1` installs Nginx + NSSM services. Not needed for local dev.

## File map (key files)

```
backend/
  main.py                    # FastAPI app + Uvicorn entrypoint
  config/settings.py         # pydantic-settings singleton
  config/schemas.py          # all Pydantic models + enums
  config/prompts.py          # all LLM prompt templates (Chinese)
  agents/base.py             # BaseAgent with call_llm(), extract_json()
  agents/solver.py           # core solving agent
  agents/verifier.py         # 6-dimension verification
  pipeline/single.py         # linear pipeline
  pipeline/multi.py          # debate pipeline
  api/routes.py              # all HTTP endpoints
  api/event_bus.py           # SSE pub/sub
  utils/llm_client.py        # async LLM HTTP client
  utils/json_parser.py       # robust JSON extraction from LLM text
  utils/logger.py            # structured JSON logger
  tools/symbolic.py          # SymPy wrappers
  tools/numerical.py         # SciPy/NumPy wrappers

frontend/
  src/App.tsx                # root component + routing
  src/api/client.ts          # REST + SSE fetch client
  src/store/solveStore.ts    # solve lifecycle state
  src/store/configStore.ts   # pipeline config state
  src/hooks/useSSE.ts        # SSE solve orchestration
  src/hooks/useMagicPaste.ts # smart paste detection
  src/utils/latexCleaner.ts  # LaTeX sanitizer for KaTeX
  src/utils/contentDetector.ts # paste content type detection (LaTeX, Markdown, HTML, code)
  src/types/index.ts         # all TypeScript types
```
