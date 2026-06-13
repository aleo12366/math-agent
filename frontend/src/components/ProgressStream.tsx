import { Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { useSolveStore } from '../store/solveStore';

const STAGE_LABELS: Record<string, string> = {
  understanding: '问题理解',
  classification: '问题分类',
  knowledge: '知识定位',
  planning: '解题规划',
  solving: '求解推理',
  consensus: '共识投票',
  verification: '结果验证',
  reflection: '反思纠错',
  explanation: '教育解释',
  formatting: '格式化输出',
  complete: '完成',
  starting: '准备中',
};

export default function ProgressStream() {
  const { isSolving, progress, currentStage, error } = useSolveStore();

  if (!isSolving && !currentStage) return null;

  const label = STAGE_LABELS[currentStage] || currentStage;
  const isError = !!error;
  const isComplete = currentStage === 'complete';

  return (
    <div className="card animate-slide-in">
      <div className="flex items-center gap-3 mb-3">
        {isComplete ? (
          <CheckCircle className="w-5 h-5 text-green-500" />
        ) : isError ? (
          <AlertCircle className="w-5 h-5 text-red-500" />
        ) : (
          <Loader2 className="w-5 h-5 text-primary-500 animate-spin" />
        )}
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-gray-900">
            {isComplete ? '求解完成' : isError ? '求解出错' : '正在求解...'}
          </h3>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
        <span className="text-sm font-mono font-semibold text-primary-600">
          {progress}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            isError ? 'bg-red-500' : isComplete ? 'bg-green-500' : 'bg-primary-500 progress-bar-animate'
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Error message */}
      {error && (
        <p className="mt-2 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
      )}
    </div>
  );
}