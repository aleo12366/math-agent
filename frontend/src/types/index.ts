// Math Agent System TypeScript Interfaces

// --- Enums / Union Types ---

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

export type PipelineMode = "single" | "multi_debate";

export type StepStatus = "complete" | "failed" | "skipped";

// --- Sub-models ---

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
  status: StepStatus;
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
  mode: PipelineMode;
  debate_agents: number;
  retry_count: number;
  created_at: string;
}

// --- Main Output Schema ---

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

// --- SSE Event Types ---

export interface SSEStageEvent {
  stage: string;
  status: "started" | "complete" | "error";
  progress: number;
  message?: string;
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

export interface SSEResultEvent {
  data: MathAgentOutput;
}

// --- API Types ---

export interface SolveRequest {
  problem: string;
  mode: PipelineMode;
  debate_agents: number;
  stream: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
  model: string;
  uptime_seconds: number;
}

export interface ConfigResponse {
  api_url: string;
  api_key_masked: string;
  model_name: string;
  has_api_key: boolean;
  temperature: number;
  max_tokens: number;
  pipeline_mode: string;
  debate_agents: number;
  max_retries: number;
  verification_threshold: number;
  confidence_threshold: number;
}

// --- Content Detection Types (Magic Paste) ---

export type ContentType = "latex" | "markdown" | "html" | "code" | "mixed" | "plain";

export interface ContentDetectionResult {
  type: ContentType;
  confidence: number;
  latexRegions: LatexRegion[];
}

export interface LatexRegion {
  start: number;
  end: number;
  content: string;
  displayMode: boolean;
}

// --- Store Types ---

export interface SolveState {
  problem: string;
  isSolving: boolean;
  result: MathAgentOutput | null;
  progress: number;
  currentStage: string;
  error: string | null;
  history: MathAgentOutput[];
}

export interface ConfigState {
  mode: PipelineMode;
  debateAgents: number;
  temperature: number;
  maxTokens: number;
}