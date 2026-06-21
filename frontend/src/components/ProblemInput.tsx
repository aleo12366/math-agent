import { useEffect, useRef, useState } from 'react';
import { Send, Loader2, StopCircle, Eye, EyeOff, Lightbulb } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import { useSolveStore } from '../store/solveStore';
import { useConfigStore } from '../store/configStore';
import { useSSE } from '../hooks/useSSE';
import { useMagicPaste } from '../hooks/useMagicPaste';
import { normalizeDelimiters } from '../utils/latexCleaner';

const EXAMPLE_PROBLEMS = [
  { label: '简单方程', text: '求解 2x + 3 = 7' },
  { label: '微积分', text: '计算 $\\int_0^1 x^2 \\, dx$' },
  { label: '线性代数', text: '求矩阵 $\\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}$ 的逆矩阵' },
  { label: '级数', text: '求级数 $\\sum_{n=1}^{\\infty} \\frac{1}{n^2}$ 的和' },
];

export default function ProblemInput() {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { problem, isSolving, setProblem } = useSolveStore();
  const { mode, debateAgents } = useConfigStore();
  const { solve, cancel } = useSSE();
  const { handlePaste, detectedType } = useMagicPaste();
  const [localProblem, setLocalProblem] = useState(problem);
  const [showPreview, setShowPreview] = useState(false);

  // Sync local state when store problem changes (e.g. after reset)
  useEffect(() => {
    setLocalProblem(problem);
  }, [problem]);

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

      {/* Preview toggle */}
      {localProblem.trim() && (
        <div className="mt-3">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors mb-2"
          >
            {showPreview ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            {showPreview ? '隐藏预览' : '题目预览'}
          </button>
          {showPreview && (
            <div className="p-4 bg-white border border-gray-200 rounded-lg shadow-inner">
              <div className="markdown-content prose prose-sm max-w-none text-gray-800">
                <ReactMarkdown
                  remarkPlugins={[remarkMath, remarkGfm]}
                  rehypePlugins={[rehypeKatex]}
                >
                  {normalizeDelimiters(localProblem)}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Example problems when textarea is empty */}
      {!localProblem.trim() && !isSolving && (
        <div className="mt-3">
          <p className="flex items-center gap-1.5 text-xs text-gray-400 mb-2">
            <Lightbulb className="w-3.5 h-3.5" />
            试试这些示例：
          </p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_PROBLEMS.map((ex) => (
              <button
                key={ex.label}
                onClick={() => {
                  setLocalProblem(ex.text);
                  textareaRef.current?.focus();
                }}
                className="px-3 py-1.5 text-xs bg-gray-50 hover:bg-gray-100 text-gray-600 rounded-full border border-gray-200 transition-colors"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      )}

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