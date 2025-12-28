/**
 * Spec Template Preload API
 *
 * Provides API for spec template operations from renderer process.
 */

import { ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../../../shared/constants';
import type { IPCResult } from '../../../shared/types';

export interface SpecTemplate {
  id: string;
  name: string;
  description: string;
  phases: unknown[];
  finalAcceptance: string[];
}

export interface SpecTemplateAPI {
  specTemplate: {
    list: () => Promise<IPCResult<SpecTemplate[]>>;
    get: (templateId: string) => Promise<IPCResult<SpecTemplate>>;
    createFrom: (
      templateId: string,
      variables?: Record<string, string>
    ) => Promise<IPCResult<{ phases: unknown[]; finalAcceptance: string[] }>>;
  };
}

export const createSpecTemplateAPI = (): SpecTemplateAPI => ({
  specTemplate: {
    list: () => ipcRenderer.invoke(IPC_CHANNELS.SPEC_TEMPLATE_LIST),
    get: (templateId: string) =>
      ipcRenderer.invoke(IPC_CHANNELS.SPEC_TEMPLATE_GET, templateId),
    createFrom: (templateId: string, variables?: Record<string, string>) =>
      ipcRenderer.invoke(IPC_CHANNELS.SPEC_TEMPLATE_CREATE_FROM, templateId, variables)
  }
});
