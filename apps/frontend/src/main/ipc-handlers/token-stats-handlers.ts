/**
 * Token Statistics IPC Handlers
 *
 * Handles IPC requests for token usage statistics:
 * - Get current statistics
 * - Reset statistics
 * - Record new requests (from renderer for SDK calls)
 */

import { ipcMain } from 'electron';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult } from '../../shared/types';
import path from 'path';
import fs from 'fs';
import { app } from 'electron';

interface TokenRequest {
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

interface TokenStats {
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

// AI model pricing (per 1M tokens)
const AI_PRICING: Record<string, { input: number; output: number; cached: number }> = {
  'claude-sonnet-4-20250514': { input: 3.00, output: 15.00, cached: 0.30 },
  'claude-opus-4-20250514': { input: 15.00, output: 75.00, cached: 1.50 },
  'claude-sonnet-3-5-20241022': { input: 3.00, output: 15.00, cached: 0.30 },
  'claude-haiku-3-5-20241022': { input: 0.80, output: 4.00, cached: 0.08 },
  'default': { input: 3.00, output: 15.00, cached: 0.30 }
};

class TokenStatsManager {
  private stats: TokenStats;
  private statsFile: string;
  private saveTimeout: NodeJS.Timeout | null = null;

  constructor() {
    const userDataPath = app.getPath('userData');
    const statsDir = path.join(userDataPath, 'stats');
    
    if (!fs.existsSync(statsDir)) {
      fs.mkdirSync(statsDir, { recursive: true });
    }
    
    this.statsFile = path.join(statsDir, 'token_stats.json');
    this.stats = this.loadStats();
  }

  private getDefaultStats(): TokenStats {
    return {
      total_requests: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      total_cached_tokens: 0,
      total_cost: 0,
      cache_hits: 0,
      cache_misses: 0,
      cache_hit_rate: 0,
      tokens_saved_by_cache: 0,
      cost_saved_by_cache: 0,
      avg_response_time_ms: 0,
      by_operation: {},
      by_model: {},
      by_hour: {},
      recent_requests: []
    };
  }

  private loadStats(): TokenStats {
    try {
      if (fs.existsSync(this.statsFile)) {
        const data = JSON.parse(fs.readFileSync(this.statsFile, 'utf-8'));
        return { ...this.getDefaultStats(), ...data.stats };
      }
    } catch (error) {
      console.error('[TokenStats] Failed to load stats:', error);
    }
    return this.getDefaultStats();
  }

  private scheduleSave(): void {
    if (this.saveTimeout) {
      clearTimeout(this.saveTimeout);
    }
    this.saveTimeout = setTimeout(() => this.saveStats(), 5000);
  }

  private saveStats(): void {
    try {
      const data = {
        stats: this.stats,
        saved_at: new Date().toISOString()
      };
      fs.writeFileSync(this.statsFile, JSON.stringify(data, null, 2));
    } catch (error) {
      console.error('[TokenStats] Failed to save stats:', error);
    }
  }

  private calculateCost(inputTokens: number, outputTokens: number, cachedTokens: number, model: string): number {
    const pricing = AI_PRICING[model] || AI_PRICING['default'];
    const inputCost = (inputTokens / 1_000_000) * pricing.input;
    const outputCost = (outputTokens / 1_000_000) * pricing.output;
    const cachedCost = (cachedTokens / 1_000_000) * pricing.cached;
    return inputCost + outputCost + cachedCost;
  }

  recordRequest(
    inputTokens: number,
    outputTokens: number,
    model: string,
    operation: string,
    cachedTokens: number = 0,
    durationMs?: number,
    taskId?: string
  ): TokenRequest {
    const cost = this.calculateCost(inputTokens, outputTokens, cachedTokens, model);
    const cacheHit = cachedTokens > 0;

    const request: TokenRequest = {
      timestamp: new Date().toISOString(),
      operation,
      model,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      cached_tokens: cachedTokens,
      cache_hit: cacheHit,
      cost,
      duration_ms: durationMs,
      task_id: taskId
    };

    // Update totals
    this.stats.total_requests += 1;
    this.stats.total_input_tokens += inputTokens;
    this.stats.total_output_tokens += outputTokens;
    this.stats.total_cached_tokens += cachedTokens;
    this.stats.total_cost += cost;

    if (cacheHit) {
      this.stats.cache_hits += 1;
    } else {
      this.stats.cache_misses += 1;
    }

    // Update cache hit rate
    const totalCacheOps = this.stats.cache_hits + this.stats.cache_misses;
    this.stats.cache_hit_rate = totalCacheOps > 0 
      ? (this.stats.cache_hits / totalCacheOps) * 100 
      : 0;

    // Update tokens/cost saved by cache
    this.stats.tokens_saved_by_cache = this.stats.total_cached_tokens;
    const avgInputPrice = 3.00;
    const fullCost = (this.stats.total_cached_tokens / 1_000_000) * avgInputPrice;
    const cachedCost = (this.stats.total_cached_tokens / 1_000_000) * 0.30;
    this.stats.cost_saved_by_cache = fullCost - cachedCost;

    // Update average response time
    if (durationMs) {
      const n = this.stats.total_requests;
      const oldAvg = this.stats.avg_response_time_ms;
      this.stats.avg_response_time_ms = oldAvg + (durationMs - oldAvg) / n;
    }

    // Update per-operation stats
    if (!this.stats.by_operation[operation]) {
      this.stats.by_operation[operation] = {
        requests: 0,
        input_tokens: 0,
        output_tokens: 0,
        cached_tokens: 0,
        cost: 0
      };
    }
    this.stats.by_operation[operation].requests += 1;
    this.stats.by_operation[operation].input_tokens += inputTokens;
    this.stats.by_operation[operation].output_tokens += outputTokens;
    this.stats.by_operation[operation].cached_tokens += cachedTokens;
    this.stats.by_operation[operation].cost += cost;

    // Update per-model stats
    if (!this.stats.by_model[model]) {
      this.stats.by_model[model] = {
        requests: 0,
        input_tokens: 0,
        output_tokens: 0,
        cost: 0
      };
    }
    this.stats.by_model[model].requests += 1;
    this.stats.by_model[model].input_tokens += inputTokens;
    this.stats.by_model[model].output_tokens += outputTokens;
    this.stats.by_model[model].cost += cost;

    // Update hourly stats
    const hour = new Date().toISOString().slice(0, 13) + ':00';
    if (!this.stats.by_hour[hour]) {
      this.stats.by_hour[hour] = { requests: 0, tokens: 0, cost: 0 };
    }
    this.stats.by_hour[hour].requests += 1;
    this.stats.by_hour[hour].tokens += inputTokens + outputTokens;
    this.stats.by_hour[hour].cost += cost;

    // Keep only last 24 hours
    const cutoffDate = new Date();
    cutoffDate.setHours(cutoffDate.getHours() - 24);
    const cutoff = cutoffDate.toISOString().slice(0, 13) + ':00';
    for (const hourKey of Object.keys(this.stats.by_hour)) {
      if (hourKey < cutoff) {
        delete this.stats.by_hour[hourKey];
      }
    }

    // Update recent requests (keep last 50)
    this.stats.recent_requests.push(request);
    if (this.stats.recent_requests.length > 50) {
      this.stats.recent_requests = this.stats.recent_requests.slice(-50);
    }

    this.scheduleSave();
    return request;
  }

  getStats(): TokenStats {
    return { ...this.stats };
  }

  resetStats(): void {
    this.stats = this.getDefaultStats();
    this.saveStats();
    console.log('[TokenStats] Statistics reset');
  }
}

let tokenStatsManager: TokenStatsManager | null = null;

function getTokenStatsManager(): TokenStatsManager {
  if (!tokenStatsManager) {
    tokenStatsManager = new TokenStatsManager();
  }
  return tokenStatsManager;
}

export function registerTokenStatsHandlers(): void {
  ipcMain.handle(
    IPC_CHANNELS.TOKEN_STATS_GET,
    async (_event, _projectId?: string): Promise<IPCResult<TokenStats>> => {
      try {
        const manager = getTokenStatsManager();
        const stats = manager.getStats();
        return { success: true, data: stats };
      } catch (error) {
        console.error('[TokenStats] Failed to get stats:', error);
        return { success: false, error: String(error) };
      }
    }
  );

  ipcMain.handle(
    IPC_CHANNELS.TOKEN_STATS_RESET,
    async (): Promise<IPCResult<void>> => {
      try {
        const manager = getTokenStatsManager();
        manager.resetStats();
        return { success: true };
      } catch (error) {
        console.error('[TokenStats] Failed to reset stats:', error);
        return { success: false, error: String(error) };
      }
    }
  );

  ipcMain.handle(
    IPC_CHANNELS.TOKEN_STATS_RECORD,
    async (
      _event,
      inputTokens: number,
      outputTokens: number,
      model: string,
      operation: string,
      cachedTokens?: number,
      durationMs?: number,
      taskId?: string
    ): Promise<IPCResult<TokenRequest>> => {
      try {
        const manager = getTokenStatsManager();
        const request = manager.recordRequest(
          inputTokens,
          outputTokens,
          model,
          operation,
          cachedTokens || 0,
          durationMs,
          taskId
        );
        return { success: true, data: request };
      } catch (error) {
        console.error('[TokenStats] Failed to record request:', error);
        return { success: false, error: String(error) };
      }
    }
  );

  console.log('[IPC] Token stats handlers registered');
}

export { getTokenStatsManager, TokenStatsManager };
