import type { Domain, ProblemType, Difficulty, VerificationStatus } from '../types';

const DOMAIN_COLORS: Record<string, string> = {
  '微积分': 'badge-blue', '线性代数': 'badge-purple', '概率论': 'badge-green',
  '偏微分方程': 'badge-yellow', '复分析': 'badge-blue', '拓扑学': 'badge-purple',
  '运筹学': 'badge-green', '数论': 'badge-yellow', '组合数学': 'badge-blue',
  '实分析': 'badge-purple', '抽象代数': 'badge-green', '微分几何': 'badge-yellow',
  '泛函分析': 'badge-blue', '数值分析': 'badge-purple', '离散数学': 'badge-green',
  '最优化理论': 'badge-yellow', '信息论': 'badge-blue', '随机过程': 'badge-purple',
};

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: 'badge-green', medium: 'badge-yellow', hard: 'badge-red',
};

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: '简单', medium: '中等', hard: '困难',
};

const VERIFICATION_COLORS: Record<string, string> = {
  pass: 'badge-green', fail: 'badge-red', uncertain: 'badge-yellow',
};

const VERIFICATION_LABELS: Record<string, string> = {
  pass: '已验证', fail: '未通过', uncertain: '待定',
};

export function DomainBadge({ domain }: { domain: Domain }) {
  return <span className={DOMAIN_COLORS[domain] || 'badge-blue'}>{domain}</span>;
}

export function ProblemTypeBadge({ type }: { type: ProblemType }) {
  return <span className="badge-purple">{type}</span>;
}

export function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  return <span className={DIFFICULTY_COLORS[difficulty] || 'badge-yellow'}>{DIFFICULTY_LABELS[difficulty] || difficulty}</span>;
}

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  return <span className={VERIFICATION_COLORS[status] || 'badge-yellow'}>{VERIFICATION_LABELS[status] || status}</span>;
}