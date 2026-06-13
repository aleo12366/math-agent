interface ConfidenceMeterProps {
  confidence: number;
  className?: string;
}

export default function ConfidenceMeter({ confidence, className = '' }: ConfidenceMeterProps) {
  const percentage = Math.round(confidence * 100);
  const color =
    percentage >= 80 ? 'text-green-600' :
    percentage >= 60 ? 'text-yellow-600' :
    'text-red-600';
  const bgColor =
    percentage >= 80 ? 'bg-green-500' :
    percentage >= 60 ? 'bg-yellow-500' :
    'bg-red-500';

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-gray-500">置信度</span>
        <span className={`text-sm font-bold ${color}`}>{percentage}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-700 ${bgColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}