import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { MathAgentOutput, SolveState } from '../types';

interface SolveStore extends SolveState {
  setProblem: (problem: string) => void;
  setIsSolving: (isSolving: boolean) => void;
  setResult: (result: MathAgentOutput | null) => void;
  setProgress: (progress: number) => void;
  setCurrentStage: (stage: string) => void;
  setError: (error: string | null) => void;
  addToHistory: (result: MathAgentOutput) => void;
  clearHistory: () => void;
  reset: () => void;
}

export const useSolveStore = create<SolveStore>()(
  persist(
    (set) => ({
      problem: '',
      isSolving: false,
      result: null,
      progress: 0,
      currentStage: '',
      error: null,
      history: [],

      setProblem: (problem) => set({ problem }),
      setIsSolving: (isSolving) => set({ isSolving }),
      setResult: (result) => set({ result }),
      setProgress: (progress) => set({ progress }),
      setCurrentStage: (stage) => set({ currentStage: stage }),
      setError: (error) => set({ error }),
      addToHistory: (result) =>
        set((state) => ({
          history: [result, ...state.history].slice(0, 50),
        })),
      clearHistory: () => set({ history: [] }),
      reset: () =>
        set({
          problem: '',
          isSolving: false,
          result: null,
          progress: 0,
          currentStage: '',
          error: null,
        }),
    }),
    {
      name: 'math-agent-solve-history',
      partialize: (state) => ({ history: state.history }),
    }
  )
);