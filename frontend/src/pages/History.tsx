import { Clock, Trash2, ChevronRight } from 'lucide-react';
import { useSolveStore } from '../store/solveStore';
import { DomainBadge, ProblemTypeBadge, VerificationBadge } from '../components/DomainBadge';
import type { MathAgentOutput } from '../types';

export default function HistoryPage() {
  const { history, setResult, clearHistory } = useSolveStore();

  const handleSelect = (item: MathAgentOutput) => {
    setResult(item);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">求解历史</h2>
        {history.length > 0 && (
          <button onClick={clearHistory} className="btn-secondary text-sm flex items-center gap-1">
            <Trash2 className="w-4 h-4" />
            清空历史
          </button>
        )}
      </div>

      {history.length === 0 ? (
        <div className="card text-center py-12">
          <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">暂无求解历史</p>
          <p className="text-sm text-gray-400 mt-1">求解数学问题后将在此显示</p>
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((item) => (
            <button
              key={item.problem_id}
              onClick={() => handleSelect(item)}
              className="card w-full text-left hover:shadow-md transition-shadow cursor-pointer group"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <DomainBadge domain={item.domain} />
                    <ProblemTypeBadge type={item.problem_type} />
                    <VerificationBadge status={item.verification_status} />
                  </div>
                  <p className="text-sm text-gray-800 font-medium truncate">
                    {item.final_answer}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    置信度: {(item.confidence * 100).toFixed(0)}% ·
                    耗时: {(item.processing_time_ms / 1000).toFixed(1)}s ·
                    ID: {item.problem_id}
                  </p>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-primary-500 transition-colors flex-shrink-0 mt-1" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}