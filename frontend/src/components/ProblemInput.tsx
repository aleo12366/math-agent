import { useRef, useState } from 'react';
import { Send, Loader2, StopCircle } from 'lucide-react';
import { useSolveStore } from '../store/solveStore';
import { useConfigStore } from '../store/configStore';
import { useSSE } from '../hooks/useSSE';
import { useMagicPaste } from '../hooks/useMagicPaste';

export default function ProblemInput() {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { problem, isSolving, setProblem } = useSolveStore();
  const { mode, debateAgents } = useConfigStore();
  const { solve, cancel } = useSSE();
  const { handlePaste, detectedType } = useMagicPaste(textareaRef);
  const [localProblem, setLocalProblem] = useState('');

  const handleSubmit = () => {
    const text = localProblem.trim() || problem;
    if (!text || isSolving) return;
    setProblem(text);
    solve(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold text-gray-900">输入数学问题</h2>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="badge-blue">{mode === 'multi_debate' ? `辩论模式 (${debateAgents} agents)` : '单智能体模式'}</span>
          {detectedType !== 'plain' && (
            <span className="badge-purple">检测到: {detectedType}</span>
          )}
        </div>
      </div>

      <textarea
        ref={textareaRef}
        value={localProblem}
        onChange={(e) => setLocalProblem(e.target.value)}
        onPaste={handlePaste}
        onKeyDown={handleKeyDown}
        placeholder="请输入数学问题，支持 LaTeX、Markdown 等格式...&#10;&#10;例如：求 ∫₀¹ x² dx 的值&#10;&#10;按 Ctrl+Enter 快速提交"
        className="input-field min-h-[160px] resize-y font-mono text-sm"
        disabled={isSolving}
      />

      <div className="flex items-center justify-between mt-4">
        <p className="text-xs text-gray-400">
          Ctrl+Enter 提交 · 支持粘贴 LaTeX/Markdown/代码
        </p>
        <div className="flex gap-2">
          {isSolving ? (
            <button onClick={cancel} className="btn-secondary flex items-center gap-2">
              <StopCircle className="w-4 h-4" />
              停止
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!localProblem.trim() && !problem}
              className="btn-primary flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
              求解
            </button>
          )}
        </div>
      </div>
    </div>
  );
}