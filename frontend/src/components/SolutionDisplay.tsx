import { useState } from 'react';
import { CheckCircle, XCircle, HelpCircle, Clock, Cpu } from 'lucide-react';
import type { MathAgentOutput } from '../types';
import { DomainBadge, ProblemTypeBadge, DifficultyBadge, VerificationBadge } from './DomainBadge';
import ConfidenceMeter from './ConfidenceMeter';
import ReasoningSteps from './ReasoningSteps';
import VerificationPanel from './VerificationPanel';
import ExplanationPanel from './ExplanationPanel';
import JsonViewer from './JsonViewer';
import LatexRenderer from './LatexRenderer';

interface SolutionDisplayProps {
  result: MathAgentOutput;
}

type Tab = 'answer' | 'steps' | 'explanation' | 'verification' | 'json';

export default function SolutionDisplay({ result }: SolutionDisplayProps) {
  const [activeTab, setActiveTab] = useState<Tab>('answer');

  const tabs: { key: Tab; label: string }[] = [
    { key: 'answer', label: '答案' },
    { key: 'steps', label: '推理步骤' },
    { key: 'explanation', label: '解释' },
    { key: 'verification', label: '验证' },
    { key: 'json', label: 'JSON' },
  ];

  return (
    <div className="space-y-4 animate-slide-in">
      {/* Header card */}
      <div className="card">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <DomainBadge domain={result.domain} />
              <ProblemTypeBadge type={result.problem_type} />
              <DifficultyBadge difficulty={result.difficulty} />
              <VerificationBadge status={result.verification_status} />
            </div>
            <p className="text-xs text-gray-500">
              ID: {result.problem_id} · v{result.pipeline_version}
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {(result.processing_time_ms / 1000).toFixed(1)}s
            </span>
            <span className="flex items-center gap-1">
              <Cpu className="w-3 h-3" />
              {result.token_usage_estimate?.total || 0} tokens
            </span>
          </div>
        </div>

        <ConfidenceMeter confidence={result.confidence} />

        {/* Final answer */}
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">最终答案</h3>
          <p className="text-lg font-semibold text-gray-900">{result.final_answer}</p>
          {result.final_answer_latex && (
            <div className="mt-2">
              <LatexRenderer latex={result.final_answer_latex.replace(/\$/g, '')} displayMode />
            </div>
          )}
        </div>

        {/* Knowledge points & theorems */}
        {(result.knowledge_points?.length > 0 || result.theorems_applied?.length > 0) && (
          <div className="mt-4 flex flex-wrap gap-2">
            {result.knowledge_points?.map((kp, i) => (
              <span key={`kp-${i}`} className="badge bg-blue-50 text-blue-700 border border-blue-200">{kp}</span>
            ))}
            {result.theorems_applied?.map((th, i) => (
              <span key={`th-${i}`} className="badge bg-purple-50 text-purple-700 border border-purple-200">{th}</span>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="card">
        <div className="flex border-b border-gray-200 -mx-6 px-6 mb-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'answer' && (
          <div>
            <p className="text-gray-800 text-lg mb-4">{result.final_answer}</p>
            {result.final_answer_latex && (
              <div className="p-4 bg-gray-50 rounded-lg text-center">
                <LatexRenderer latex={result.final_answer_latex.replace(/\$/g, '')} displayMode />
              </div>
            )}
            {result.alternative_methods?.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">备选方法</h4>
                <ul className="list-disc pl-5 space-y-1">
                  {result.alternative_methods.map((m, i) => (
                    <li key={i} className="text-sm text-gray-600">{m}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {activeTab === 'steps' && <ReasoningSteps steps={result.key_steps} plan={result.reasoning_plan} />}
        {activeTab === 'explanation' && <ExplanationPanel explanation={result.educational_explanation} />}
        {activeTab === 'verification' && <VerificationPanel details={result.verification_details} status={result.verification_status} confidence={result.confidence} />}
        {activeTab === 'json' && <JsonViewer data={result} />}
      </div>
    </div>
  );
}