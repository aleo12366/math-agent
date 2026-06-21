import { CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import type { VerificationDetails, VerificationStatus } from '../types';
import ConfidenceMeter from './ConfidenceMeter';
import { normalizeDelimiters } from '../utils/latexCleaner';

interface VerificationPanelProps {
  details: VerificationDetails;
  status: VerificationStatus;
  confidence: number;
}

const CHECK_LABELS: Record<string, string> = {
  formula_consistency: '公式一致性',
  boundary_conditions: '边界条件',
  logical_consistency: '逻辑一致性',
  special_cases: '特殊情况',
  dimension_check: '量纲检查',
  completeness: '完整性',
};

export default function VerificationPanel({ details, status, confidence }: VerificationPanelProps) {
  if (!details) {
    return (
      <div className="space-y-4">
        <ConfidenceMeter confidence={confidence} className="mb-4" />
        <p className="text-gray-500 text-sm">暂无验证详情</p>
      </div>
    );
  }

  const checks = Object.entries(details);

  return (
    <div className="space-y-4">
      <ConfidenceMeter confidence={confidence} className="mb-4" />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {checks.map(([key, check]) => (
          <div
            key={key}
            className={`p-4 rounded-lg border ${
              check.passed
                ? 'border-green-200 bg-green-50'
                : 'border-red-200 bg-red-50'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              {check.passed ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500" />
              )}
              <span className="text-sm font-semibold text-gray-800">
                {CHECK_LABELS[key] || key}
              </span>
              <span className="ml-auto text-xs font-mono text-gray-500">
                {(check.score * 100).toFixed(0)}%
              </span>
            </div>
            <div className="text-xs text-gray-600 markdown-content prose prose-xs max-w-none">
              <ReactMarkdown remarkPlugins={[remarkMath, remarkGfm]} rehypePlugins={[rehypeKatex]}>
                {normalizeDelimiters(check.detail)}
              </ReactMarkdown>
            </div>
            <div className="mt-2 w-full bg-gray-200 rounded-full h-1.5">
              <div
                className={`h-1.5 rounded-full ${check.passed ? 'bg-green-500' : 'bg-red-500'}`}
                style={{ width: `${check.score * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}