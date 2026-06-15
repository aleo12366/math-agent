import { ArrowRight, Wrench } from 'lucide-react';
import type { KeyStep, PlanStep } from '../types';
import LatexRenderer from './LatexRenderer';
import { normalizeDelimiters } from '../utils/latexCleaner';

interface ReasoningStepsProps {
  steps: KeyStep[];
  plan?: PlanStep[];
}

export default function ReasoningSteps({ steps, plan }: ReasoningStepsProps) {
  return (
    <div className="space-y-6">
      {/* Solution plan */}
      {plan && plan.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3">解题计划</h4>
          <div className="space-y-2">
            {plan.map((step) => (
              <div key={step.step_id} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
                <span className="flex-shrink-0 w-6 h-6 bg-blue-200 text-blue-800 rounded-full flex items-center justify-center text-xs font-bold">
                  {step.step_id}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800">{step.description}</p>
                  <p className="text-xs text-gray-500 mt-1">方法: {step.method}</p>
                  {step.tools_needed && step.tools_needed.length > 0 && (
                    <div className="flex gap-1 mt-1">
                      {step.tools_needed.map((t, i) => (
                        <span key={i} className="badge bg-gray-100 text-gray-600 text-xs">
                          <Wrench className="w-3 h-3 inline mr-0.5" />{t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reasoning steps */}
      <div>
        <h4 className="text-sm font-semibold text-gray-700 mb-3">推理步骤</h4>
        <div className="space-y-3">
          {steps.map((step, i) => (
            <div key={step.step_id || i} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                  step.status === 'complete' ? 'bg-green-100 text-green-800' :
                  step.status === 'failed' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-600'
                }`}>
                  {step.step_id}
                </span>
                <p className="text-sm font-medium text-gray-800">{step.description}</p>
              </div>

              {step.mathematical_expression && (
                <div className="ml-8 my-2 p-3 bg-gray-50 rounded-lg">
                  <LatexRenderer latex={normalizeDelimiters(step.mathematical_expression)} displayMode />
                </div>
              )}

              <div className="ml-8 flex items-center gap-2 text-sm">
                <ArrowRight className="w-3 h-3 text-gray-400" />
                <span className="text-gray-700 font-medium">{step.result}</span>
              </div>

              {step.justification && (
                <p className="ml-8 mt-1 text-xs text-gray-500 italic">{step.justification}</p>
              )}

              {step.tool_used && (
                <div className="ml-8 mt-2 flex items-center gap-2">
                  <Wrench className="w-3 h-3 text-purple-500" />
                  <span className="text-xs text-purple-600 font-medium">{step.tool_used}</span>
                  {step.tool_result?.value && (
                    <span className="text-xs text-gray-500">= {step.tool_result.value}</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}