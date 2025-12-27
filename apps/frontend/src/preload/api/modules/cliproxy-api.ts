import { ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../../../shared/constants';
import type { IPCResult, CLIProxyStatus, CLIProxyConfig } from '../../../shared/types';

export interface CLIProxyAPI {
  getCliProxyStatus: () => Promise<IPCResult<CLIProxyStatus>>;
  testCliProxyConnection: (url?: string, apiKey?: string) => Promise<IPCResult<{ connected: boolean; models?: string[] }>>;
  getCliProxyConfig: () => Promise<IPCResult<CLIProxyConfig>>;
  saveCliProxyConfig: (config: CLIProxyConfig) => Promise<IPCResult<void>>;
}

export const createCLIProxyAPI = (): CLIProxyAPI => ({
  getCliProxyStatus: (): Promise<IPCResult<CLIProxyStatus>> =>
    ipcRenderer.invoke(IPC_CHANNELS.CLIPROXY_GET_STATUS),

  testCliProxyConnection: (url?: string, apiKey?: string): Promise<IPCResult<{ connected: boolean; models?: string[] }>> =>
    ipcRenderer.invoke(IPC_CHANNELS.CLIPROXY_TEST_CONNECTION, url, apiKey),

  getCliProxyConfig: (): Promise<IPCResult<CLIProxyConfig>> =>
    ipcRenderer.invoke(IPC_CHANNELS.CLIPROXY_GET_CONFIG),

  saveCliProxyConfig: (config: CLIProxyConfig): Promise<IPCResult<void>> =>
    ipcRenderer.invoke(IPC_CHANNELS.CLIPROXY_SAVE_CONFIG, config),
});
