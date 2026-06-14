import { useCallback, useEffect, useRef } from 'react';
import { solveProblemSSE } from '../api/client';
import { useSolveStore } from '../store/solveStore';
import { useConfigStore } from '../store/configStore';
import type { MathAgentOutput } from '../types';

/**
 * Hook for SSE streaming solve with automatic store updates.
 */
export function useSSE() {
  const abortRef = useRef<AbortController | null>(null);
  const {
    setProblem,
    setIsSolving,
    setResult,
    setProgress,
    setCurrentStage,
    setError,
    addToHistory,
    reset,
  } = useSolveStore();
  const { mode, debateAgents } = useConfigStore();

  const solve = useCallback(
    (problem: string) => {
      // Reset state
      reset();
      setProblem(problem);
      setIsSolving(true);
      setCurrentStage('starting');
      setError(null);

      abortRef.current = solveProblemSSE(problem, mode, debateAgents, {
        onStage: (event) => {
          setCurrentStage(event.stage);
          setProgress(event.progress);
          if (event.status === 'error') {
            setError(event.message || `Error in stage: ${event.stage}`);
          }
        },
        onStep: (event) => {
          setProgress(event.progress);
        },
        onComplete: (event) => {
          setProgress(100);
          if (event.status === 'error') {
            setError('Pipeline completed with errors');
          }
        },
        onResult: (result: MathAgentOutput) => {
          setResult(result);
          addToHistory(result);
          setIsSolving(false);
          setCurrentStage('complete');
        },
        onError: (error: string) => {
          setError(error);
          setIsSolving(false);
        },
      });
    },
    [mode, debateAgents, reset, setProblem, setIsSolving, setResult, setProgress, setCurrentStage, setError, addToHistory]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setIsSolving(false);
    setCurrentStage('cancelled');
  }, [setIsSolving, setCurrentStage]);

  // Cleanup: abort on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return { solve, cancel };
}