/**
 * Browser mock for window.electronAPI
 * This allows the app to run in a regular browser for UI development/testing
 *
 * This module aggregates all mock implementations from separate modules
 * for better code organization and maintainability.
 */

import type { ElectronAPI } from '../../shared/types';
import {
  projectMock,
  taskMock,
  workspaceMock,
  terminalMock,
  claudeProfileMock,
  contextMock,
  integrationMock,
  changelogMock,
  insightsMock,
  infrastructureMock,
  settingsMock
} from './mocks';

// Check if we're in a browser (not Electron)
const isElectron = typeof window !== 'undefined' && window.electronAPI !== undefined;

/**
 * Create mock electronAPI for browser
 * Aggregates all mock implementations from separate modules
 */
const browserMockAPI: ElectronAPI = {
  // Project Operations
  ...projectMock,

  // Task Operations
  ...taskMock,

  // Workspace Management
  ...workspaceMock,

  // Terminal Operations
  ...terminalMock,

  // Claude Profile Management
  ...claudeProfileMock,

  // Settings
  ...settingsMock,

  // Roadmap Operations
  getRoadmap: async () => ({
    success: true,
    data: null
  }),

  getRoadmapStatus: async () => ({
    success: true,
    data: { isRunning: false }
  }),

  saveRoadmap: async () => ({
    success: true
  }),

  generateRoadmap: (_projectId: string, _enableCompetitorAnalysis?: boolean, _refreshCompetitorAnalysis?: boolean) => {
    console.warn('[Browser Mock] generateRoadmap called');
  },

  refreshRoadmap: (_projectId: string, _enableCompetitorAnalysis?: boolean, _refreshCompetitorAnalysis?: boolean) => {
    console.warn('[Browser Mock] refreshRoadmap called');
  },

  updateFeatureStatus: async () => ({ success: true }),

  convertFeatureToSpec: async (projectId: string, _featureId: string) => ({
    success: true,
    data: {
      id: `task-${Date.now()}`,
      specId: '',
      projectId,
      title: 'Converted Feature',
      description: 'Feature converted from roadmap',
      status: 'backlog' as const,
      subtasks: [],
      logs: [],
      createdAt: new Date(),
      updatedAt: new Date()
    }
  }),

  stopRoadmap: async () => ({ success: true }),

  // Roadmap Event Listeners
  onRoadmapProgress: () => () => {},
  onRoadmapComplete: () => () => {},
  onRoadmapError: () => () => {},
  onRoadmapStopped: () => () => {},
  // Context Operations
  ...contextMock,

  // Environment Configuration & Integration Operations
  ...integrationMock,

  // Changelog & Release Operations
  ...changelogMock,

  // Insights Operations
  ...insightsMock,

  // Infrastructure & Docker Operations
  ...infrastructureMock,

  // GitHub API
  github: {
    getGitHubRepositories: async () => ({ success: true, data: [] }),
    getGitHubIssues: async () => ({ success: true, data: [] }),
    getGitHubIssue: async () => ({ success: true, data: null as any }),
    getIssueComments: async () => ({ success: true, data: [] }),
    checkGitHubConnection: async () => ({ success: true, data: { connected: false, repoFullName: undefined, error: undefined } }),
    investigateGitHubIssue: () => {},
    importGitHubIssues: async () => ({ success: true, data: { success: true, imported: 0, failed: 0, issues: [] } }),
    createGitHubRelease: async () => ({ success: true, data: { url: '' } }),
    suggestReleaseVersion: async () => ({ success: true, data: { suggestedVersion: '1.0.0', currentVersion: '0.0.0', bumpType: 'minor' as const, commitCount: 0, reason: 'Initial' } }),
    checkGitHubCli: async () => ({ success: true, data: { installed: false } }),
    checkGitHubAuth: async () => ({ success: true, data: { authenticated: false } }),
    startGitHubAuth: async () => ({ success: true, data: { success: false } }),
    getGitHubToken: async () => ({ success: true, data: { token: '' } }),
    getGitHubUser: async () => ({ success: true, data: { username: '' } }),
    listGitHubUserRepos: async () => ({ success: true, data: { repos: [] } }),
    detectGitHubRepo: async () => ({ success: true, data: '' }),
    getGitHubBranches: async () => ({ success: true, data: [] }),
    createGitHubRepo: async () => ({ success: true, data: { fullName: '', url: '' } }),
    addGitRemote: async () => ({ success: true, data: { remoteUrl: '' } }),
    listGitHubOrgs: async () => ({ success: true, data: { orgs: [] } }),
    onGitHubAuthDeviceCode: () => () => {},
    onGitHubInvestigationProgress: () => () => {},
    onGitHubInvestigationComplete: () => () => {},
    onGitHubInvestigationError: () => () => {},
    getAutoFixConfig: async () => null,
    saveAutoFixConfig: async () => true,
    getAutoFixQueue: async () => [],
    checkAutoFixLabels: async () => [],
    checkNewIssues: async () => [],
    startAutoFix: () => {},
    onAutoFixProgress: () => () => {},
    onAutoFixComplete: () => () => {},
    onAutoFixError: () => () => {},
    listPRs: async () => [],
    runPRReview: () => {},
    cancelPRReview: async () => true,
    postPRReview: async () => true,
    postPRComment: async () => true,
    mergePR: async () => true,
    assignPR: async () => true,
    getPRReview: async () => null,
    deletePRReview: async () => true,
    checkNewCommits: async () => ({ hasNewCommits: false, newCommitCount: 0 }),
    runFollowupReview: () => {},
    onPRReviewProgress: () => () => {},
    onPRReviewComplete: () => () => {},
    onPRReviewError: () => () => {},
    batchAutoFix: () => {},
    getBatches: async () => [],
    onBatchProgress: () => () => {},
    onBatchComplete: () => () => {},
    onBatchError: () => () => {},
    // Analyze & Group Issues (proactive workflow)
    analyzeIssuesPreview: () => {},
    approveBatches: async () => ({ success: true, batches: [] }),
    onAnalyzePreviewProgress: () => () => {},
    onAnalyzePreviewComplete: () => () => {},
    onAnalyzePreviewError: () => () => {}
  },

  // CLIProxyAPI (browser mock always returns disabled)
  getCliProxyStatus: async () => ({
    success: true,
    data: { enabled: false, url: 'http://localhost:8317', connected: false }
  }),
  testCliProxyConnection: async () => ({
    success: true,
    data: { connected: false, models: [] }
  }),
  getCliProxyConfig: async () => ({
    success: true,
    data: {
      enabled: false,
      url: 'http://localhost:8317',
      apiKey: '',
      modelMappings: [
        { source: 'opus' as const, target: '', enabled: true },
        { source: 'sonnet' as const, target: '', enabled: true },
        { source: 'haiku' as const, target: '', enabled: true }
      ]
    }
  }),
  saveCliProxyConfig: async () => ({ success: true }),

  // Spec Template
  specTemplate: {
    list: async () => ({
      success: true,
      data: [
        { id: 'auth-crud', name: 'Authentication + CRUD', description: 'User authentication with full CRUD operations', phases: [], finalAcceptance: [] },
        { id: 'api-endpoint', name: 'REST API Endpoint', description: 'Single REST API endpoint with validation', phases: [], finalAcceptance: [] }
      ]
    }),
    get: async () => ({
      success: true,
      data: { id: 'auth-crud', name: 'Authentication + CRUD', description: 'User authentication with full CRUD operations', phases: [], finalAcceptance: [] }
    }),
    createFrom: async () => ({
      success: true,
      data: { phases: [], finalAcceptance: [] }
    })
  },

  // Token Statistics
  tokenStats: {
    get: async () => ({
      success: true,
      data: {
        total_requests: 42,
        total_input_tokens: 125000,
        total_output_tokens: 45000,
        total_cached_tokens: 30000,
        total_cost: 0.85,
        cache_hits: 15,
        cache_misses: 27,
        cache_hit_rate: 35.7,
        tokens_saved_by_cache: 30000,
        cost_saved_by_cache: 0.08,
        avg_response_time_ms: 1250,
        by_operation: {
          'spec_generation': { requests: 10, input_tokens: 50000, output_tokens: 20000, cached_tokens: 10000, cost: 0.30 },
          'code_implementation': { requests: 20, input_tokens: 60000, output_tokens: 20000, cached_tokens: 15000, cost: 0.40 }
        },
        by_model: {
          'claude-sonnet-4-20250514': { requests: 35, input_tokens: 100000, output_tokens: 40000, cost: 0.75 },
          'claude-haiku-3-5-20241022': { requests: 7, input_tokens: 25000, output_tokens: 5000, cost: 0.10 }
        },
        by_hour: {},
        recent_requests: []
      }
    }),
    reset: async () => ({ success: true }),
    record: async () => ({
      success: true,
      data: {
        timestamp: new Date().toISOString(),
        operation: 'test',
        model: 'claude-sonnet-4-20250514',
        input_tokens: 1000,
        output_tokens: 500,
        cached_tokens: 0,
        cache_hit: false,
        cost: 0.01
      }
    })
  }
};

/**
 * Initialize browser mock if not running in Electron
 */
export function initBrowserMock(): void {
  if (!isElectron) {
    console.warn('%c[Browser Mock] Initializing mock electronAPI for browser preview', 'color: #f0ad4e; font-weight: bold;');
    (window as Window & { electronAPI: ElectronAPI }).electronAPI = browserMockAPI;
  }
}

// Auto-initialize
initBrowserMock();
