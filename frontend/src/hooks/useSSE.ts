import { useCallback, useEffect, useRef } from 'react';
import { solveProblemSSE } from '../api/client';
import { useSolveStore } from '../store/solveStore';
import { useConfigStore } from '../store/configStore';
import type { MathAgentOutput } from '../types';

const MAX_RETRIES = 2;
const SOLVE_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes (complex route with retries)

/**
 * Hook for SSE streaming solve with automatic retry, timeout, and store updates.
 */
export function useSSE() {
  const abortRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);
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

  const cleanup = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const startSolve = useCallback(
    (problem: string) => {
      // Reset state
      reset();
      setProblem(problem);
      setIsSolving(true);
      setCurrentStage('starting');
      setError(null);

      // Set up timeout
      timeoutRef.current = setTimeout(() => {
        abortRef.current?.abort();
        setIsSolving(false);
        setError('求解超时，请检查网络连接后重试');
      }, SOLVE_TIMEOUT_MS);

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
          if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
          }
          setResult(result);
          addToHistory(result);
          setIsSolving(false);
          setCurrentStage('complete');
          setError(null);
          retryCountRef.current = 0;
        },
        onError: (error: string) => {
          // Retry on transient errors
          if (retryCountRef.current < MAX_RETRIES && !error.includes('AbortError')) {
            retryCountRef.current += 1;
            console.warn(`SSE error, retrying (${retryCountRef.current}/${MAX_RETRIES})...`);
            setTimeout(() => startSolve(problem), 1000 * retryCountRef.current);
          } else {
            if (timeoutRef.current) {
              clearTimeout(timeoutRef.current);
              timeoutRef.current = null;
            }
            setIsSolving(false);
            setError(error || '连接中断，请重试');
          }
        },
      });
    },
    [mode, debateAgents, reset, setProblem, setIsSolving, setResult, setProgress, setCurrentStage, setError, addToHistory]
  );

  const cancel = useCallback(() => {
    cleanup();
    setIsSolving(false);
    setCurrentStage('');
    setError(null);
    setProgress(0);
    retryCountRef.current = 0;
  }, [cleanup, setIsSolving, setCurrentStage, setError, setProgress]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return { solve: startSolve, cancel };
}
