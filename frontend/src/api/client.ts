import axios from 'axios';
import type { MathAgentOutput, HealthResponse, ConfigResponse, SSEStageEvent, SSEStepEvent, SSECompleteEvent } from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 300000, // 5 minutes for long-running solves
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Solve a math problem with SSE streaming.
 * Returns an EventSource-like object for real-time progress updates.
 */
export function solveProblemSSE(
  problem: string,
  mode: string = 'single',
  debateAgents: number = 1,
  callbacks: {
    onStage?: (event: SSEStageEvent) => void;
    onStep?: (event: SSEStepEvent) => void;
    onComplete?: (event: SSECompleteEvent) => void;
    onResult?: (result: MathAgentOutput) => void;
    onError?: (error: string) => void;
  }
): AbortController {
  const controller = new AbortController();

  fetch('/api/solve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      problem,
      mode,
      debate_agents: debateAgents,
      stream: true,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEventType = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              switch (currentEventType) {
                case 'stage':
                  callbacks.onStage?.(data as SSEStageEvent);
                  break;
                case 'step':
                  callbacks.onStep?.(data as SSEStepEvent);
                  break;
                case 'complete':
                  callbacks.onComplete?.(data as SSECompleteEvent);
                  break;
                case 'result':
                  callbacks.onResult?.(data as MathAgentOutput);
                  break;
                case 'error':
                  callbacks.onError?.(data.error || 'Unknown error');
                  break;
              }
            } catch {
              // Skip non-JSON data
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        callbacks.onError?.(err.message);
      }
    });

  return controller;
}

/**
 * Solve a problem without streaming (returns final result).
 */
export async function solveProblem(
  problem: string,
  mode: string = 'single',
  debateAgents: number = 1
): Promise<MathAgentOutput> {
  const response = await api.post<MathAgentOutput>('/solve', {
    problem,
    mode,
    debate_agents: debateAgents,
    stream: false,
  });
  return response.data;
}

/**
 * Health check.
 */
export async function getHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>('/health');
  return response.data;
}

/**
 * Get current configuration.
 */
export async function getConfig(): Promise<ConfigResponse> {
  const response = await api.get<ConfigResponse>('/config');
  return response.data;
}

/**
 * Update configuration.
 */
export async function updateConfig(updates: Record<string, unknown>): Promise<ConfigResponse> {
  const response = await api.put<ConfigResponse>('/config', updates);
  return response.data;
}

export default api;