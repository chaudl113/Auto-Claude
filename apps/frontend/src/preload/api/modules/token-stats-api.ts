/**
 * Token Stats Preload API
 *
 * Provides API for token statistics operations from renderer process.
 */

import { ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../../../shared/constants';
import type { IPCResult } from '../../../shared/types';

export interface TokenRequest {
  timestamp: string;
  operation: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cache_hit: boolean;
  cost: number;
  duration_ms?: number;
  task_id?: string;
}

export interface TokenStats {
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  total_cost: number;
  cache_hits: number;
  cache_misses: number;
  cache_hit_rate: number;
  tokens_saved_by_cache: number;
  cost_saved_by_cache: number;
  avg_response_time_ms: number;
  by_operation: Record<string, {
    requests: number;
    input_tokens: number;
    output_tokens: number;
    cached_tokens: number;
    cost: number;
  }>;
  by_model: Record<string, {
    requests: number;
    input_tokens: number;
    output_tokens: number;
    cost: number;
  }>;
  by_hour: Record<string, {
    requests: number;
    tokens: number;
    cost: number;
  }>;
  recent_requests: TokenRequest[];
}

export interface TokenStatsAPI {
  tokenStats: {
    get: (projectId?: string) => Promise<IPCResult<TokenStats>>;
    reset: () => Promise<IPCResult<void>>;
    record: (
      inputTokens: number,
      outputTokens: number,
      model: string,
      operation: string,
      cachedTokens?: number,
      durationMs?: number,
      taskId?: string
    ) => Promise<IPCResult<TokenRequest>>;
  };
}

export const createTokenStatsAPI = (): TokenStatsAPI => ({
  tokenStats: {
    get: (projectId?: string) =>
      ipcRenderer.invoke(IPC_CHANNELS.TOKEN_STATS_GET, projectId),
    reset: () =>
      ipcRenderer.invoke(IPC_CHANNELS.TOKEN_STATS_RESET),
    record: (
      inputTokens: number,
      outputTokens: number,
      model: string,
      operation: string,
      cachedTokens?: number,
      durationMs?: number,
      taskId?: string
    ) =>
      ipcRenderer.invoke(
        IPC_CHANNELS.TOKEN_STATS_RECORD,
        inputTokens,
        outputTokens,
        model,
        operation,
        cachedTokens,
        durationMs,
        taskId
      )
  }
});
