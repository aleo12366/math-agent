# Implementation Plan

## Overview

Build a complete multi-agent math problem-solving system from scratch, consisting of a Python/FastAPI backend with 9-agent pipeline and a React 18/TypeScript frontend with "Magic Paste" smart content rendering. The system takes mathematical problems as input, processes them through a multi-agent pipeline using the Intern-S1 LLM API, and outputs structured JSON with verified solutions, step-by-step reasoning, and educational explanations.

The system targets a competition evaluating: answer correctness (60%), presentation quality (20%), innovation & scalability (10%), and reasoning strategy (10%). The architecture prioritizes correctness through 6-dimension verification and debate-mode multi-agent consensus, presentation quality through a polished React frontend with LaTeX rendering and SSE streaming, and innovation through configurable debate agents, domain-adaptive strategies, and a Mogan-inspired "Magic Paste" content transformer.

## Types

The system uses Pydantic v2 models for backend validation and TypeScript interfaces for frontend type safety, unified by a shared JSON schema for the output format.

### Backend Pydantic Models (Python)

```python
# backend/config/schemas.py

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import uuid
from datetime import datetime

# --- Enums ---

class Domain(str, Enum):
    CALCULUS = "微积分"
    LINEAR_ALGEBRA = "线性代数"
    PROBABILITY = "概率论"
    PDE = "偏微分方程"
    COMPLEX_ANALYSIS = "复分析"
    TOPOLOGY = "拓扑学"
    OPERATIONS_RESEARCH = "运筹学"
    NUMBER_THEORY = "数论"
    COMBINATORICS = "组合数学"
    REAL_ANALYSIS = "实分析"
    ABSTRACT_ALGEBRA = "抽象代数"
    DIFFERENTIAL_GEOMETRY = "微分几何"
    FUNCTIONAL_ANALYSIS = "泛函分析"
    NUMERICAL_ANALYSIS = "数值分析"
    DISCRETE_MATH = "离散数学"
    OPTIMIZATION = "最优化理论"
    INFORMATION_THEORY = "信息论"
    STOCHASTIC_PROCESS = "随机过程"

class ProblemType(str, Enum):
    COMPUTATION = "计算题"
    PROOF = "证明题"
    SOLVING = "求解题"
    JUDGMENT = "判断题"
    CONSTRUCTION = "构造题"
    APPLICATION = "应用题"

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class AnswerFormat(str, Enum):
    NUMBER = "number"
    EXPRESSION = "expression"
    EQUATION = "equation"
    INEQUALITY = "inequality"
    SET = "set"
    MATRIX = "matrix"
    VECTOR = "vector"
    INTERVAL = "interval"
    BOOLEAN = "boolean"
    PROOF = "proof"
    SEQUENCE = "sequence"
    FUNCTION = "function"
    PARAMETRIC = "parametric"
    TEXT = "text"
    MULTIPLE = "multiple"

class VerificationCheckName(str, Enum):
    FORMULA_CONSISTENCY = "formula_consistency"
    BOUNDARY_CONDITIONS = "boundary_conditions"
    LOGICAL_CONSISTENCY = "logical_consistency"
    SPECIAL_CASES = "special_cases"
    DIMENSION_CHECK = "dimension_check"
    COMPLETENESS = "completeness"

class VerificationStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNCERTAIN = "uncertain"

class StepStatus(str, Enum):
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"

class ErrorType(str, Enum):
    LLM_ERROR = "llm_error"
    TOOL_ERROR = "tool_error"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT = "timeout"
    PARSE_ERROR = "parse_error"

class PipelineMode(str, Enum):
    SINGLE = "single"
    MULTI_DEBATE = "multi_debate"

class ModuleName(str, Enum):
    PROBLEM_UNDERSTANDING = "problem_understanding"
    CLASSIFIER = "classifier"
    KNOWLEDGE_LOCATOR = "knowledge_locator"
    PLANNER = "planner"
    SOLVER = "solver"
    VERIFIER = "verifier"
    REFLECTION = "reflection"
    EXPLAINER = "explainer"
    FORMATTER = "formatter"
    TOOL_AGENT = "tool_agent"
    COORDINATOR = "coordinator"

# --- Sub-models ---

class PlanStep(BaseModel):
    step_id: int = Field(ge=1)
    description: str
    method: str
    expected_outcome: Optional[str] = None
    tools_needed: list[str] = Field(default_factory=list)
    knowledge_applied: Optional[str] = None

class ToolResult(BaseModel):
    value: Optional[str] = None
    numeric: Optional[float] = None
    latex: Optional[str] = None

class KeyStep(BaseModel):
    step_id: int = Field(ge=1)
    description: str
    mathematical_expression: str
    justification: Optional[str] = None
    result: str
    tool_used: Optional[str] = None
    tool_result: Optional[ToolResult] = None
    status: StepStatus = StepStatus.COMPLETE

class VerificationCheck(BaseModel):
    passed: bool
    detail: str
    score: float = Field(ge=0.0, le=1.0)

class VerificationDetails(BaseModel):
    formula_consistency: VerificationCheck
    boundary_conditions: VerificationCheck
    logical_consistency: VerificationCheck
    special_cases: VerificationCheck
    dimension_check: VerificationCheck
    completeness: VerificationCheck

class TokenUsage(BaseModel):
    input: int = Field(ge=0)
    output: int = Field(ge=0)
    total: int = Field(ge=0)

class ErrorLog(BaseModel):
    timestamp: datetime
    module: ModuleName
    error_type: ErrorType
    message: str
    retry_count: int = Field(ge=0, default=0)
    resolved: bool = False

class PipelineMetadata(BaseModel):
    model: str = "Intern-S1"
    mode: PipelineMode = PipelineMode.SINGLE
    debate_agents: int = Field(ge=1, default=1)
    retry_count: int = Field(ge=0, default=0)
    created_at: datetime = Field(default_factory=datetime.now)

# --- Main Output Schema ---

class MathAgentOutput(BaseModel):
    problem_id: str = Field(default_factory=lambda: f"prob_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:4]}")
    domain: Domain
    problem_type: ProblemType
    difficulty: Difficulty
    difficulty_score: float = Field(ge=0.0, le=1.0)
    reasoning_plan: list[PlanStep]
    key_steps: list[KeyStep]
    final_answer: str
    final_answer_latex: Optional[str] = None
    answer_format: AnswerFormat
    confidence: float = Field(ge=0.0, le=1.0)
    verification_status: VerificationStatus
    verification_details: VerificationDetails
    educational_explanation: str
    knowledge_points: list[str] = Field(default_factory=list)
    theorems_applied: list[str] = Field(default_factory=list)
    alternative_methods: list[str] = Field(default_factory=list)
    error_logs: list[ErrorLog] = Field(default_factory=list)
    token_usage_estimate: TokenUsage
    processing_time_ms: int = Field(ge=0)
    pipeline_version: str = "2.0.0"
    metadata: Optional[PipelineMetadata] = None
```

### Frontend TypeScript Interfaces

```typescript
// frontend/src/types/index.ts

export interface MathAgentOutput {
  problem_id: string;
  domain: Domain;
  problem_type: ProblemType;
  difficulty: Difficulty;
  difficulty_score: number;
  reasoning_plan: PlanStep[];
  key_steps: KeyStep[];
  final_answer: string;
  final_answer_latex?: string;
  answer_format: AnswerFormat;
  confidence: number;
  verification_status: VerificationStatus;
  verification_details: VerificationDetails;
  educational_explanation: string;
  knowledge_points: string[];
  theorems_applied: string[];
  alternative_methods: string[];
  error_logs: ErrorLog[];
  token_usage_estimate: TokenUsage;
  processing_time_ms: number;
  pipeline_version: string;
  metadata?: PipelineMetadata;
}

export type Domain =
  | "微积分" | "线性代数" | "概率论" | "偏微分方程" | "复分析"
  | "拓扑学" | "运筹学" | "数论" | "组合数学" | "实分析"
  | "抽象代数" | "微分几何" | "泛函分析" | "数值分析"
  | "离散数学" | "最优化理论" | "信息论" | "随机过程";

export type ProblemType = "计算题" | "证明题" | "求解题" | "判断题" | "构造题" | "应用题";
export type Difficulty = "easy" | "medium" | "hard";
export type VerificationStatus = "pass" | "fail" | "uncertain";

export type AnswerFormat =
  | "number" | "expression" | "equation" | "inequality"
  | "set" | "matrix" | "vector" | "interval" | "boolean"
  | "proof" | "sequence" | "function" | "parametric"
  | "text" | "multiple";

export interface PlanStep {
  step_id: number;
  description: string;
  method: string;
  expected_outcome?: string;
  tools_needed: string[];
  knowledge_applied?: string;
}

export interface KeyStep {
  step_id: number;
  description: string;
  mathematical_expression: string;
  justification?: string;
  result: string;
  tool_used?: string;
  tool_result?: ToolResult;
  status: "complete" | "failed" | "skipped";
}

export interface ToolResult {
  value?: string;
  numeric?: number;
  latex?: string;
}

export interface VerificationCheck {
  passed: boolean;
  detail: string;
  score: number;
}

export interface VerificationDetails {
  formula_consistency: VerificationCheck;
  boundary_conditions: VerificationCheck;
  logical_consistency: VerificationCheck;
  special_cases: VerificationCheck;
  dimension_check: VerificationCheck;
  completeness: VerificationCheck;
}

export interface TokenUsage {
  input: number;
  output: number;
  total: number;
}

export interface ErrorLog {
  timestamp: string;
  module: string;
  error_type: string;
  message: string;
  retry_count: number;
  resolved: boolean;
}

export interface PipelineMetadata {
  model: string;
  mode: "single" | "multi_debate";
  debate_agents: number;
  retry_count: number;
  created_at: string;
}

// SSE Event Types
export interface SSEStageEvent {
  stage: string;
  status: "started" | "complete" | "error";
  progress: number;
  [key: string]: unknown;
}

export interface SSEStepEvent {
  step: number;
  total: number;
  description: string;
  expression: string;
  progress: number;
}

export interface SSECompleteEvent {
  status: "success" | "error";
  total_tokens: number;
  duration_ms: number;
  progress: 100;
}
```

## Files

### Project Root Structure

```
math-agent/
├── implementation_plan.md          # This file
├── README.md                       # Project documentation
├── docker-compose.yml              # Docker orchestration
├── .gitignore
├── backend/                        # Python backend
│   ├── main.py                     # FastAPI app entry point
│   ├── requirements.txt            # Python dependencies
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py             # Pydantic Settings (env-based config)
│   │   ├── schemas.py              # All Pydantic models (Types section above)
│   │   └── prompts.py              # All prompt templates for agents
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseAgent class with LLM call
│   │   ├── coordinator.py          # Pipeline orchestration
│   │   ├── problem_understander.py # Module 1: Problem understanding
│   │   ├── classifier.py           # Module 2: Domain/type/difficulty
│   │   ├── knowledge_locator.py    # Module 3: Knowledge point locating
│   │   ├── planner.py              # Module 4: Solution planning
│   │   ├── solver.py               # Module 5: Step-by-step reasoning
│   │   ├── tool_agent.py           # Tool execution (SymPy/SciPy)
│   │   ├── verifier.py             # Module 6: 6-dimension verification
│   │   ├── reflection.py           # Module 6.5: Error analysis & retry
│   │   ├── explainer.py            # Module 7: Educational explanation
│   │   └── formatter.py            # Module 8: JSON output formatting
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── base.py                 # BasePipeline abstract class
│   │   ├── single.py               # Single-agent pipeline (linear)
│   │   └── multi.py                # Multi-agent debate pipeline
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py               # API endpoints
│   │   └── event_bus.py            # SSE event emitter
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── llm_client.py           # Intern-S1 API client (async)
│   │   ├── json_parser.py          # JSON extraction from LLM output
│   │   └── logger.py               # Module 9: Structured logging
│   └── tools/
│       ├── __init__.py
│       ├── symbolic.py             # SymPy operations
│       └── numerical.py            # SciPy/NumPy operations
├── frontend/                       # React frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   ├── public/
│   │   └── favicon.ico
│   └── src/
│       ├── main.tsx                # React entry
│       ├── App.tsx                 # Root component with router
│       ├── types/
│       │   └── index.ts            # TypeScript interfaces
│       ├── api/
│       │   └── client.ts           # Axios + SSE client
│       ├── store/
│       │   ├── solveStore.ts       # Zustand store for solve state
│       │   └── configStore.ts      # Zustand store for config
│       ├── hooks/
│       │   ├── useSSE.ts           # SSE streaming hook
│       │   └── useMagicPaste.ts    # Magic Paste hook
│       ├── utils/
│       │   ├── contentDetector.ts  # Content type detection
│       │   ├── contentTransformer.ts # Content format transformation
│       │   ├── latexCleaner.ts     # LaTeX sanitization
│       │   └── markdownParser.ts   # Markdown → React components
│       ├── components/
│       │   ├── Layout.tsx          # App shell with sidebar
│       │   ├── ProblemInput.tsx    # Problem input area
│       │   ├── FileUpload.tsx      # File upload (PDF/DOCX/image)
│       │   ├── SolutionDisplay.tsx # Main result display
│       │   ├── ReasoningSteps.tsx  # Step-by-step visualization
│       │   ├── VerificationPanel.tsx # 6-dimension verification UI
│       │   ├── ExplanationPanel.tsx # Educational explanation
│       │   ├── LatexRenderer.tsx   # KaTeX rendering component
│       │   ├── MagicPasteArea.tsx  # Smart paste input area
│       │   ├── ProgressStream.tsx  # SSE progress indicator
│       │   ├── DomainBadge.tsx     # Domain/type badges
│       │   ├── ConfidenceMeter.tsx # Confidence gauge
│       │   ├── ErrorLogPanel.tsx   # Error log viewer
│       │   └── JsonViewer.tsx      # Raw JSON viewer
│       ├── pages/
│       │   ├── Home.tsx            # Main solve page
│       │   ├── History.tsx         # Solve history
│       │   └── Settings.tsx        # Config settings
│       └── styles/
│           └── globals.css         # Tailwind + custom styles
└── tests/
    ├── test_agents.py              # Agent unit tests
    ├── test_pipeline.py            # Pipeline integration tests
    ├── test_api.py                 # API endpoint tests
    └── test_tools.py               # Tool agent tests
```

### New Files to Create

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app with CORS, lifespan, router mount |
| `backend/requirements.txt` | Python dependencies |
| `backend/config/__init__.py` | Config package init |
| `backend/config/settings.py` | Pydantic Settings: API key, model, temp, thresholds |
| `backend/config/schemas.py` | All Pydantic models (see Types section) |
| `backend/config/prompts.py` | 20+ prompt templates for all agents |
| `backend/agents/__init__.py` | Agents package init |
| `backend/agents/base.py` | BaseAgent with async LLM call, JSON extraction |
| `backend/agents/coordinator.py` | Pipeline orchestrator, SSE event push |
| `backend/agents/problem_understander.py` | Module 1: clean/parse input |
| `backend/agents/classifier.py` | Module 2: 18 domains, 6 types, difficulty |
| `backend/agents/knowledge_locator.py` | Module 3: knowledge points & theorems |
| `backend/agents/planner.py` | Module 4: step-by-step plan |
| `backend/agents/solver.py` | Module 5: execute plan, generate LaTeX steps |
| `backend/agents/tool_agent.py` | SymPy/SciPy tool execution |
| `backend/agents/verifier.py` | Module 6: 6-dimension verification |
| `backend/agents/reflection.py` | Module 6.5: error analysis & correction |
| `backend/agents/explainer.py` | Module 7: Markdown+LaTeX explanation |
| `backend/agents/formatter.py` | Module 8: final JSON assembly |
| `backend/pipeline/__init__.py` | Pipeline package init |
| `backend/pipeline/base.py` | BasePipeline with event hooks |
| `backend/pipeline/single.py` | Single-agent linear pipeline |
| `backend/pipeline/multi.py` | Multi-agent debate pipeline |
| `backend/api/__init__.py` | API package init |
| `backend/api/routes.py` | /api/solve, /api/batch, /api/config, /health |
| `backend/api/event_bus.py` | SSE event emitter with async queues |
| `backend/utils/__init__.py` | Utils package init |
| `backend/utils/llm_client.py` | Async Intern-S1 API client with retry |
| `backend/utils/json_parser.py` | Extract JSON from LLM text output |
| `backend/utils/logger.py` | Module 9: structured logging to JSON |
| `backend/tools/__init__.py` | Tools package init |
| `backend/tools/symbolic.py` | SymPy: simplify, solve, integrate, diff, etc. |
| `backend/tools/numerical.py` | SciPy: optimize, linalg, integrate |
| `frontend/package.json` | React + Vite + Tailwind dependencies |
| `frontend/vite.config.ts` | Vite config with proxy to backend |
| `frontend/tailwind.config.js` | Tailwind config |
| `frontend/index.html` | HTML entry with KaTeX CSS |
| `frontend/src/main.tsx` | React entry point |
| `frontend/src/App.tsx` | Root with React Router |
| `frontend/src/types/index.ts` | TypeScript interfaces |
| `frontend/src/api/client.ts` | Axios + EventSource SSE |
| `frontend/src/store/solveStore.ts` | Zustand solve state |
| `frontend/src/store/configStore.ts` | Zustand config state |
| `frontend/src/hooks/useSSE.ts` | SSE streaming hook |
| `frontend/src/hooks/useMagicPaste.ts` | Magic Paste hook |
| `frontend/src/utils/contentDetector.ts` | Detect content type |
| `frontend/src/utils/contentTransformer.ts` | Transform content formats |
| `frontend/src/utils/latexCleaner.ts` | Clean/sanitize LaTeX |
| `frontend/src/utils/markdownParser.ts` | Parse markdown to JSX |
| `frontend/src/components/*.tsx` | 14 UI components |
| `frontend/src/pages/*.tsx` | 3 pages |
| `frontend/src/styles/globals.css` | Global styles |
| `tests/test_agents.py` | Agent tests |
| `tests/test_pipeline.py` | Pipeline tests |
| `tests/test_api.py` | API tests |
| `tests/test_tools.py` | Tool tests |
| `README.md` | Project documentation |
| `docker-compose.yml` | Docker setup |
| `.gitignore` | Git ignore rules |

## Functions

### Backend Core Functions

**BaseAgent (backend/agents/base.py)**
- `async call_llm(messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str` — Call Intern-S1 API via aiohttp
- `extract_json(text: str) -> dict | None` — Extract JSON from LLM text output
- `async run(input_data: dict) -> dict` — Abstract method for agent execution

**LLM Client (backend/utils/llm_client.py)**
- `async chat(messages: list[dict], temperature: float, max_tokens: int) -> str` — Core API call with retry
- `async chat_stream(messages, temperature, max_tokens) -> AsyncGenerator[str, None]` — Streaming variant

**JSON Parser (backend/utils/json_parser.py)**
- `extract_json_from_text(text: str) -> dict | None` — Regex + json.loads extraction
- `validate_output(data: dict) -> tuple[bool, list[str]]` — Validate against schema

**Tool Agent (backend/tools/symbolic.py)**
- `sympy_simplify(expr: str) -> ToolResult` — Symbolic simplification
- `sympy_solve(equation: str, variable: str) -> ToolResult` — Solve equation
- `sympy_integrate(expr: str, var: str, bounds: tuple | None) -> ToolResult` — Integration
- `sympy_diff(expr: str, var: str, order: int) -> ToolResult` — Differentiation
- `sympy_limit(expr: str, var: str, point: str) -> ToolResult` — Limit
- `sympy_matrix(operations: str, matrix_data: list) -> ToolResult` — Matrix ops
- `verify_equality(expr1: str, expr2: str) -> ToolResult` — Verify equivalence
- `numerical_eval(expr: str, precision: int) -> ToolResult` — Numerical evaluation

**Tool Agent (backend/tools/numerical.py)**
- `scipy_optimize(method: str, func: str, constraints: dict) -> ToolResult` — Optimization
- `scipy_linalg(operation: str, matrix: list) -> ToolResult` — Numerical linear algebra
- `scipy_integrate(func: str, bounds: tuple) -> ToolResult` — Numerical integration

**Agent Functions (each agent module):**
- `ProblemUnderstander.run(input) -> {"cleaned_problem": str, "input_type": str, ...}`
- `Classifier.run(input) -> {"domain": str, "problem_type": str, "difficulty": str, ...}`
- `KnowledgeLocator.run(input) -> {"knowledge_points": list, "relevant_theorems": list, ...}`
- `Planner.run(input) -> {"strategy": str, "steps": list[PlanStep], ...}`
- `Solver.run(input) -> {"reasoning_steps": list[KeyStep], "final_answer": str, ...}`
- `Verifier.run(input) -> {"verified": bool, "confidence": float, "checks": dict, ...}`
- `Reflection.run(input) -> {"error_analysis": dict, "correction_strategy": dict, ...}`
- `Explainer.run(input) -> {"explanation": str}` (Markdown)
- `Formatter.run(all_outputs) -> MathAgentOutput`

**Pipeline Functions:**
- `SinglePipeline.solve(problem: str, config: dict) -> MathAgentOutput` — Linear pipeline
- `MultiPipeline.solve(problem: str, config: dict) -> MathAgentOutput` — Debate pipeline with N parallel solvers

**API Routes (backend/api/routes.py):**
- `POST /api/solve` — Solve single problem, returns SSE stream or JSON
- `POST /api/batch` — Solve batch of problems
- `GET /api/config` — Get current configuration
- `PUT /api/config` — Update configuration
- `GET /health` — Health check

**SSE Event Bus (backend/api/event_bus.py):**
- `EventBus.emit(event_type: str, data: dict)` — Emit SSE event
- `EventBus.subscribe() -> AsyncGenerator` — Subscribe to event stream

### Frontend Functions

**API Client (frontend/src/api/client.ts)**
- `solveProblem(input: string, config?: object) -> EventSource` — Start solve with SSE
- `getHealth() -> Promise<HealthResponse>` — Health check
- `getConfig() -> Promise<Config>` — Get config

**Content Detection (frontend/src/utils/contentDetector.ts)**
- `detectContentType(text: string) -> "latex" | "markdown" | "html" | "code" | "mixed" | "plain"` — Mogan-inspired format detection
- `detectLatexDelimiters(text: string) -> LatexRegion[]` — Find LaTeX regions

**Content Transformer (frontend/src/utils/contentTransformer.ts)**
- `transformContent(text: string, type: ContentType) -> ReactNode` — Main transform dispatcher
- `transformLatex(text: string) -> string` — Clean LaTeX for KaTeX
- `transformMarkdown(text: string) -> ReactNode` — Parse markdown to JSX
- `transformCode(text: string, language?: string) -> ReactNode` — Syntax highlight
- `transformMixed(text: string) -> ReactNode` — Segmented rendering

**LaTeX Cleaner (frontend/src/utils/latexCleaner.ts)**
- `cleanLatex(text: string) -> string` — Sanitize LaTeX for KaTeX compatibility
- `normalizeDelimiters(text: string) -> string` — Normalize \[ \] and \( \) to $$ and $
- `fixCommonErrors(text: string) -> string` — Fix common LLM LaTeX errors

**Hooks:**
- `useSSE(url: string) -> { data, error, isConnected, progress }` — SSE streaming hook
- `useMagicPaste(ref: RefObject) -> { handlePaste, detectedType }` — Paste handler

## Classes

### Backend Classes

**BaseAgent** (`backend/agents/base.py`)
```python
class BaseAgent:
    def __init__(self, config: Settings): ...
    async def call_llm(self, messages, temperature, max_tokens) -> str: ...
    def extract_json(self, text) -> dict | None: ...
    async def run(self, input_data: dict) -> dict: ...  # abstract
```

**ProblemUnderstander** (`backend/agents/problem_understander.py`) extends BaseAgent
- Key: `run(input: {"problem": str}) -> {"cleaned_problem": str, "input_type": str, "language": str}`

**Classifier** (`backend/agents/classifier.py`) extends BaseAgent
- Key: `run(input: {"problem": str}) -> {"domain": Domain, "problem_type": ProblemType, "difficulty": Difficulty, ...}`

**KnowledgeLocator** (`backend/agents/knowledge_locator.py`) extends BaseAgent
- Key: `run(input) -> {"knowledge_points": list, "relevant_theorems": list}`

**Planner** (`backend/agents/planner.py`) extends BaseAgent
- Key: `run(input) -> {"strategy": str, "steps": list[PlanStep]}`

**Solver** (`backend/agents/solver.py`) extends BaseAgent
- Key: `run(input) -> {"reasoning_steps": list[KeyStep], "final_answer": str, "final_answer_latex": str}`

**ToolAgent** (`backend/agents/tool_agent.py`)
```python
class ToolAgent:
    async def execute(self, tool_name: str, params: dict) -> ToolResult: ...
```
- No LLM, wraps SymPy/SciPy calls

**Verifier** (`backend/agents/verifier.py`) extends BaseAgent
- Key: `run(input) -> {"verified": bool, "confidence": float, "details": VerificationDetails}`

**Reflection** (`backend/agents/reflection.py`) extends BaseAgent
- Key: `run(input) -> {"error_analysis": dict, "correction_strategy": dict}`

**Explainer** (`backend/agents/explainer.py`) extends BaseAgent
- Key: `run(input) -> {"explanation": str}` (Markdown)

**Formatter** (`backend/agents/formatter.py`)
```python
class Formatter:
    def format(self, all_module_outputs: dict) -> MathAgentOutput: ...
```
- No LLM, pure data assembly

**EventBus** (`backend/api/event_bus.py`)
```python
class EventBus:
    def __init__(self): ...
    async def emit(self, event_type: str, data: dict): ...
    async def subscribe(self) -> AsyncGenerator[str, None]: ...
```

**BasePipeline** (`backend/pipeline/base.py`)
```python
class BasePipeline(ABC):
    def __init__(self, config: Settings, event_bus: EventBus): ...
    @abstractmethod
    async def solve(self, problem: str) -> MathAgentOutput: ...
```

**SinglePipeline** extends BasePipeline
- Linear: understand → classify → locate → plan → solve → verify → (reflect+retry) → explain → format

**MultiPipeline** extends BasePipeline
- Debate: understand → classify → locate → plan → N×solve (parallel) → consensus → verify → (reflect+retry) → explain → format

### Frontend Components (key ones)

**MagicPasteArea** (`frontend/src/components/MagicPasteArea.tsx`)
- Smart paste input area inspired by Mogan's paste-widget.scm
- Auto-detects content type on paste
- Renders content with appropriate format (LaTeX/KaTeX, code highlighting, etc.)

**SolutionDisplay** (`frontend/src/components/SolutionDisplay.tsx`)
- Main result viewer with tabs: Answer, Steps, Explanation, Verification, JSON
- KaTeX rendering for all math expressions

**ProgressStream** (`frontend/src/components/ProgressStream.tsx`)
- SSE progress indicator showing current pipeline stage
- Animated stage transitions

## Dependencies

### Backend (requirements.txt)

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.3
pydantic-settings==2.7.0
aiohttp==3.11.11
sympy==1.13.3
scipy==1.14.1
numpy==1.26.4
pyyaml==6.0.2
python-multipart==0.0.18
sse-starlette==2.2.1
python-docx==1.1.2
PyPDF2==3.0.1
markdown==3.7
rich==13.9.4
```

### Frontend (package.json)

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "typescript": "^5.6.3",
    "vite": "^6.0.3",
    "@vitejs/plugin-react": "^4.3.4",
    "tailwindcss": "^3.4.17",
    "postcss": "^8.4.49",
    "autoprefixer": "^10.4.20",
    "katex": "^0.16.11",
    "react-markdown": "^9.0.1",
    "remark-math": "^6.0.0",
    "rehype-katex": "^7.0.1",
    "remark-gfm": "^4.0.0",
    "zustand": "^5.0.2",
    "axios": "^1.7.9",
    "lucide-react": "^0.468.0",
    "clsx": "^2.1.1",
    "react-syntax-highlighter": "^15.6.1",
    "@types/react-syntax-highlighter": "^15.5.13"
  }
}
```

## Testing

### Backend Tests

| Test File | Tests | What it validates |
|-----------|-------|-------------------|
| `tests/test_agents.py` | 15+ tests | Each agent's run() with mock LLM responses |
| `tests/test_pipeline.py` | 5+ tests | SinglePipeline and MultiPipeline end-to-end |
| `tests/test_api.py` | 8+ tests | All API endpoints, SSE streaming |
| `tests/test_tools.py` | 12+ tests | All SymPy/SciPy tool functions |

### Frontend Tests

- Manual testing via browser (Web demo requirement)
- TypeScript compilation checks (`tsc --noEmit`)

### Validation Strategy

1. **Schema Validation**: Every output validated against the JSON schema via `validate_output()`
2. **LaTeX Validation**: All LaTeX expressions tested with KaTeX rendering
3. **Tool Verification**: SymPy results cross-checked with expected values
4. **End-to-End**: Run 10+ problems from each domain, verify output structure

## Implementation Order

1. **Backend Core** (Day 1-2)
   1. Create project structure, `requirements.txt`, `settings.py`
   2. Implement `llm_client.py` (async Intern-S1 API client)
   3. Implement `json_parser.py` (JSON extraction from LLM output)
   4. Implement `base.py` (BaseAgent class)
   5. Implement `schemas.py` (all Pydantic models)
   6. Implement `prompts.py` (all prompt templates)

2. **Backend Agents** (Day 2-4)
   7. Implement `problem_understander.py` (Module 1)
   8. Implement `classifier.py` (Module 2)
   9. Implement `knowledge_locator.py` (Module 3)
   10. Implement `planner.py` (Module 4)
   11. Implement `solver.py` (Module 5)
   12. Implement `tool_agent.py` + `symbolic.py` + `numerical.py`
   13. Implement `verifier.py` (Module 6)
   14. Implement `reflection.py` (Module 6.5)
   15. Implement `explainer.py` (Module 7)
   16. Implement `formatter.py` (Module 8)
   17. Implement `logger.py` (Module 9)

3. **Backend Pipeline** (Day 4-5)
   18. Implement `event_bus.py` (SSE events)
   19. Implement `base.py` (BasePipeline)
   20. Implement `single.py` (SinglePipeline)
   21. Implement `multi.py` (MultiPipeline with debate)
   22. Implement `routes.py` (API endpoints)
   23. Implement `main.py` (FastAPI app)

4. **Frontend Setup** (Day 5-6)
   24. Create Vite project with React 18 + TypeScript
   25. Install and configure Tailwind CSS 3
   26. Install KaTeX, react-markdown, zustand, axios
   27. Create `types/index.ts`
   28. Create `api/client.ts`
   29. Create `store/solveStore.ts` + `configStore.ts`

5. **Frontend Components** (Day 6-8)
   30. Implement `Layout.tsx`
   31. Implement `ProblemInput.tsx` + `FileUpload.tsx`
   32. Implement `LatexRenderer.tsx`
   33. Implement `MagicPasteArea.tsx` + `useMagicPaste.ts` + content utils
   34. Implement `ProgressStream.tsx` + `useSSE.ts`
   35. Implement `SolutionDisplay.tsx`
   36. Implement `ReasoningSteps.tsx`
   37. Implement `VerificationPanel.tsx`
   38. Implement `ExplanationPanel.tsx`
   39. Implement remaining components (DomainBadge, ConfidenceMeter, etc.)
   40. Implement pages (Home, History, Settings)

6. **Integration & Polish** (Day 8-9)
   41. Connect frontend to backend API
   42. Test SSE streaming end-to-end
   43. Test Magic Paste with various LLM outputs
   44. Polish UI/UX
   45. Write tests

7. **Deployment** (Day 9-10)
   46. Create `docker-compose.yml`
   47. Write `README.md`
   48. Final end-to-end testing