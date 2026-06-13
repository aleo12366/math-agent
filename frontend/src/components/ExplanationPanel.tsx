import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';

interface ExplanationPanelProps {
  explanation: string;
}

export default function ExplanationPanel({ explanation }: ExplanationPanelProps) {
  if (!explanation) {
    return <p className="text-gray-500 text-sm">暂无解释</p>;
  }

  return (
    <div className="markdown-content prose prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[rehypeKatex]}
      >
        {explanation}
      </ReactMarkdown>
    </div>
  );
}