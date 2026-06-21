import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { PipelineMode, ConfigState } from '../types';

interface ConfigStore extends ConfigState {
  setMode: (mode: PipelineMode) => void;
  setDebateAgents: (n: number) => void;
  setTemperature: (t: number) => void;
  setMaxTokens: (t: number) => void;
}

export const useConfigStore = create<ConfigStore>()(
  persist(
    (set) => ({
      mode: 'single',
      debateAgents: 1,
      temperature: 0.7,
      maxTokens: 4096,

      setMode: (mode) => set({ mode }),
      setDebateAgents: (n) => set({ debateAgents: n }),
      setTemperature: (t) => set({ temperature: t }),
      setMaxTokens: (t) => set({ maxTokens: t }),
    }),
    { name: 'math-agent-config' }
  )
);