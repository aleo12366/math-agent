import ProblemInput from '../components/ProblemInput';
import ProgressStream from '../components/ProgressStream';
import SolutionDisplay from '../components/SolutionDisplay';
import { useSolveStore } from '../store/solveStore';

export default function Home() {
  const { result, isSolving, currentStage } = useSolveStore();

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Hero section */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          数学智能体推理系统
        </h1>
        <p className="text-gray-500 max-w-2xl mx-auto">
          基于 Intern-S1 的多智能体数学推理管线 · 9步流水线 · 6维验证 · 辩论共识
        </p>
      </div>

      {/* Input */}
      <ProblemInput />

      {/* Progress */}
      {(isSolving || currentStage) && <ProgressStream />}

      {/* Result */}
      {result && <SolutionDisplay result={result} />}
    </div>
  );
}