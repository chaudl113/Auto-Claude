import { ipcMain } from 'electron';
import http from 'http';
import https from 'https';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult, CLIProxyStatus, CLIProxyConfig } from '../../shared/types';
import { isCliProxyEnabled, getCliProxyUrl, getCliProxyApiKey } from '../env-utils';
import {
  loadCliProxyConfig,
  saveCliProxyConfig as saveConfigToDisk,
} from '../config/cliproxy-config';

/**
 * HTTP request helper for CLIProxy (supports both http and https)
 */
function httpRequest(
  url: string,
  options: { headers?: Record<string, string>; timeout?: number }
): Promise<{ status: number; statusText: string; data: string }> {
  return new Promise((resolve, reject) => {
    try {
      const parsedUrl = new URL(url);
      const isHttps = parsedUrl.protocol === 'https:';
      const httpModule = isHttps ? https : http;

      const requestOptions = {
        hostname: parsedUrl.hostname,
        port: parsedUrl.port || (isHttps ? 443 : 80),
        path: parsedUrl.pathname + parsedUrl.search,
        method: 'GET',
        headers: options.headers || {},
        timeout: options.timeout || 5000,
      };

      const req = httpModule.request(requestOptions, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          resolve({
            status: res.statusCode || 0,
            statusText: res.statusMessage || '',
            data,
          });
        });
        res.on('error', (err) => reject(err));
      });

      req.on('error', (err) => {
        console.error('[CLIProxy] Request error:', err.message);
        reject(err);
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Request timeout'));
      });

      req.end();
    } catch (err) {
      reject(err);
    }
  });
}

/**
 * Register CLIProxyAPI-related IPC handlers
 */
export function registerCliProxyHandlers(): void {
  // Get current status (from config or env)
  ipcMain.handle(
    IPC_CHANNELS.CLIPROXY_GET_STATUS,
    async (): Promise<IPCResult<CLIProxyStatus>> => {
      try {
        // First try to load from config file
        const config = loadCliProxyConfig();
        const enabled = config.enabled || isCliProxyEnabled();
        const url = config.url || getCliProxyUrl();

        const status: CLIProxyStatus = {
          enabled,
          url,
          connected: false,
        };

        if (enabled) {
          try {
            // Try root endpoint for health check
            const response = await httpRequest(`${url}/`, { timeout: 3000 });
            status.connected = response.status >= 200 && response.status < 300;
          } catch (err) {
            status.connected = false;
            const errMsg = err instanceof Error ? err.message : 'Connection failed';
            if (errMsg.includes('ECONNREFUSED')) {
              status.error = 'Proxy không chạy';
            } else {
              status.error = errMsg;
            }
          }
        }

        return { success: true, data: status };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to get CLIProxyAPI status',
        };
      }
    }
  );

  // Test connection with API key
  ipcMain.handle(
    IPC_CHANNELS.CLIPROXY_TEST_CONNECTION,
    async (_, url?: string, apiKey?: string): Promise<IPCResult<{ connected: boolean; models?: string[] }>> => {
      try {
        const config = loadCliProxyConfig();
        const testUrl = url || config.url || getCliProxyUrl();
        const testApiKey = apiKey || config.apiKey || getCliProxyApiKey();

        console.log('[CLIProxy] Testing connection:', {
          url: testUrl,
          hasApiKey: !!testApiKey,
          apiKeyPrefix: testApiKey?.substring(0, 10),
        });

        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };

        if (testApiKey) {
          headers['Authorization'] = `Bearer ${testApiKey}`;
        }

        const fullUrl = `${testUrl}/v1/models`;
        console.log('[CLIProxy] Fetching:', fullUrl);

        const response = await httpRequest(fullUrl, { headers, timeout: 5000 });

        console.log('[CLIProxy] Response status:', response.status, response.statusText);

        if (response.status >= 200 && response.status < 300) {
          const data = JSON.parse(response.data);
          console.log('[CLIProxy] Response data:', JSON.stringify(data).substring(0, 200));
          const models = data.data?.map((m: { id: string }) => m.id) || [];
          return { success: true, data: { connected: true, models } };
        } else {
          console.log('[CLIProxy] Error response:', response.data);
          const errorData = (() => {
            try { return JSON.parse(response.data); } catch { return {}; }
          })();
          return {
            success: false,
            error: errorData.error || `HTTP ${response.status}: ${response.statusText}`,
          };
        }
      } catch (error) {
        const errMsg = error instanceof Error ? error.message : 'Connection test failed';
        // Make error messages more user-friendly
        let friendlyError = errMsg;
        if (errMsg.includes('ECONNREFUSED')) {
          friendlyError = 'Proxy không chạy / Proxy not running';
        } else if (errMsg.includes('timeout') || errMsg.includes('Timeout')) {
          friendlyError = 'Timeout - Proxy không phản hồi';
        }
        console.error('[CLIProxy] Connection error:', errMsg);
        return {
          success: false,
          error: friendlyError,
        };
      }
    }
  );

  // Load full config
  ipcMain.handle(
    IPC_CHANNELS.CLIPROXY_GET_CONFIG,
    async (): Promise<IPCResult<CLIProxyConfig>> => {
      try {
        const config = loadCliProxyConfig();
        return { success: true, data: config };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to load config',
        };
      }
    }
  );

  // Save full config
  ipcMain.handle(
    IPC_CHANNELS.CLIPROXY_SAVE_CONFIG,
    async (_, config: CLIProxyConfig): Promise<IPCResult<void>> => {
      try {
        saveConfigToDisk(config);
        return { success: true };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to save config',
        };
      }
    }
  );
}
