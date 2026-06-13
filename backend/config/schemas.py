"""All Pydantic models for the math agent system."""

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
    problem_id: str = Field(
        default_factory=lambda: f"prob_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:4]}"
    )
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


# --- API Request/Response Models ---


class SolveRequest(BaseModel):
    problem: str = Field(..., min_length=1, description="The math problem to solve")
    mode: PipelineMode = PipelineMode.SINGLE
    debate_agents: int = Field(default=1, ge=1, le=10)
    stream: bool = Field(default=True, description="Whether to stream SSE events")


class BatchSolveRequest(BaseModel):
    problems: list[str] = Field(..., min_length=1, max_length=10)
    mode: PipelineMode = PipelineMode.SINGLE
    debate_agents: int = Field(default=1, ge=1, le=10)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0.0"
    model: str = "Intern-S1"
    uptime_seconds: float


class ConfigResponse(BaseModel):
    api_url: str
    api_key_masked: str = ""
    model_name: str
    has_api_key: bool = False
    temperature: float
    max_tokens: int
    pipeline_mode: str
    debate_agents: int
    max_retries: int
    verification_threshold: float
    confidence_threshold: float


class ConfigUpdateRequest(BaseModel):
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32768)
    pipeline_mode: Optional[str] = None
    debate_agents: Optional[int] = Field(default=None, ge=1, le=10)
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    verification_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    confidence_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
