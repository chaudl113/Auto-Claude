/**
 * Application settings types
 */

import type { NotificationSettings } from './project';
import type { ChangelogFormat, ChangelogAudience, ChangelogEmojiLevel } from './changelog';
import type { SupportedLanguage } from '../constants/i18n';

// Color theme types for multi-theme support
export type ColorTheme = 'default' | 'dusk' | 'lime' | 'ocean' | 'retro' | 'neo' | 'forest';

export interface ThemePreviewColors {
  bg: string;
  accent: string;
  darkBg: string;
  darkAccent?: string;
}

export interface ColorThemeDefinition {
  id: ColorTheme;
  name: string;
  description: string;
  previewColors: ThemePreviewColors;
}

// Thinking level for Claude model (budget token allocation)
export type ThinkingLevel = 'none' | 'low' | 'medium' | 'high' | 'ultrathink';

// Model type shorthand
export type ModelTypeShort = 'haiku' | 'sonnet' | 'opus';

// Phase-based model configuration for Auto profile
// Each phase can use a different model optimized for that task type
export interface PhaseModelConfig {
  spec: ModelTypeShort;       // Spec creation (discovery, requirements, context)
  planning: ModelTypeShort;   // Implementation planning
  coding: ModelTypeShort;     // Actual coding implementation
  qa: ModelTypeShort;         // QA review and fixing
}

// Thinking level configuration per phase
export interface PhaseThinkingConfig {
  spec: ThinkingLevel;
  planning: ThinkingLevel;
  coding: ThinkingLevel;
  qa: ThinkingLevel;
}

// Feature-specific model configuration (for non-pipeline features)
export interface FeatureModelConfig {
  insights: ModelTypeShort;    // Insights chat feature
  ideation: ModelTypeShort;    // Ideation generation
  roadmap: ModelTypeShort;     // Roadmap generation
  githubIssues: ModelTypeShort; // GitHub Issues automation
  githubPrs: ModelTypeShort;    // GitHub PR review automation
}

// Feature-specific thinking level configuration
export interface FeatureThinkingConfig {
  insights: ThinkingLevel;
  ideation: ThinkingLevel;
  roadmap: ThinkingLevel;
  githubIssues: ThinkingLevel;
  githubPrs: ThinkingLevel;
}

// Agent profile for preset model/thinking configurations
export interface AgentProfile {
  id: string;
  name: string;
  description: string;
  model: ModelTypeShort;
  thinkingLevel: ThinkingLevel;
  icon?: string;  // Lucide icon name
  // Auto profile specific - per-phase configuration
  isAutoProfile?: boolean;
  phaseModels?: PhaseModelConfig;
  phaseThinking?: PhaseThinkingConfig;
}

// Performance feature flags configuration
export interface PerformanceFeatureFlags {
  // Agent state caching for faster session recovery
  agentCacheEnabled: boolean;
  // Worktree pooling for faster worktree allocation
  worktreePoolEnabled: boolean;
  // Number of worktrees to keep in pool (1-8)
  worktreePoolSize: number;
  // AI diff preview before merge operations
  diffPreviewEnabled: boolean;
  // Automatic rollback on merge failure
  rollbackEnabled: boolean;
  // Parallel execution of independent subtasks
  parallelExecutionEnabled: boolean;
  // Maximum parallel tasks (1-8)
  maxParallelTasks: number;
  // Spec template system
  specTemplatesEnabled: boolean;
}

export interface AppSettings {
  theme: 'light' | 'dark' | 'system';
  colorTheme?: ColorTheme;
  defaultModel: string;
  agentFramework: string;
  pythonPath?: string;
  autoBuildPath?: string;
  autoUpdateAutoBuild: boolean;
  autoNameTerminals: boolean;
  notifications: NotificationSettings;
  // Global API keys (used as defaults for all projects)
  globalClaudeOAuthToken?: string;
  globalOpenAIApiKey?: string;
  globalAnthropicApiKey?: string;
  globalGoogleApiKey?: string;
  globalGroqApiKey?: string;
  globalOpenRouterApiKey?: string;
  // Graphiti LLM provider settings
  graphitiLlmProvider?: 'openai' | 'anthropic' | 'google' | 'groq' | 'ollama';
  ollamaBaseUrl?: string;
  // Onboarding wizard completion state
  onboardingCompleted?: boolean;
  // Selected agent profile for preset model/thinking configurations
  selectedAgentProfile?: string;
  // Custom phase configuration for Auto profile (overrides defaults)
  customPhaseModels?: PhaseModelConfig;
  customPhaseThinking?: PhaseThinkingConfig;
  // Feature-specific configuration (insights, ideation, roadmap)
  featureModels?: FeatureModelConfig;
  featureThinking?: FeatureThinkingConfig;
  // Changelog preferences
  changelogFormat?: ChangelogFormat;
  changelogAudience?: ChangelogAudience;
  changelogEmojiLevel?: ChangelogEmojiLevel;
  // UI Scale setting (75-200%, default 100)
  uiScale?: number;
  // Beta updates opt-in (receive pre-release updates)
  betaUpdates?: boolean;
  // Migration flags (internal use)
  _migratedAgentProfileToAuto?: boolean;
  // Language preference for UI (i18n)
  language?: SupportedLanguage;
  // Performance feature flags
  performanceFlags?: PerformanceFeatureFlags;
}

// Auto-Claude Source Environment Configuration (for auto-claude repo .env)
export interface SourceEnvConfig {
  // Claude Authentication (required for ideation, roadmap generation, etc.)
  hasClaudeToken: boolean;
  claudeOAuthToken?: string;

  // Source path info
  sourcePath?: string;
  envExists: boolean;
}

export interface SourceEnvCheckResult {
  hasToken: boolean;
  sourcePath?: string;
  error?: string;
  source?: 'profile' | 'env' | undefined;
  profileId?: string;
  profileName?: string;
}

// Auto Claude Source Update Types
export interface AutoBuildSourceUpdateCheck {
  updateAvailable: boolean;
  currentVersion: string;
  latestVersion?: string;
  releaseNotes?: string;
  releaseUrl?: string;
  error?: string;
}

export interface AutoBuildSourceUpdateResult {
  success: boolean;
  version?: string;
  error?: string;
}

export interface AutoBuildSourceUpdateProgress {
  stage: 'checking' | 'downloading' | 'extracting' | 'complete' | 'error';
  percent?: number;
  message: string;
  /** New version after successful update - used to refresh UI */
  newVersion?: string;
}

// CLIProxyAPI configuration status
export interface CLIProxyStatus {
  enabled: boolean;
  url: string;
  connected: boolean;
  error?: string;
}

// Model mapping for CLIProxyAPI
export interface ModelMapping {
  /** Source model type (opus, sonnet, haiku) */
  source: 'opus' | 'sonnet' | 'haiku';
  /** Target model name in CLIProxyAPI (e.g., "gpt-5.1", "claude-sonnet-4.5") */
  target: string;
  /** Whether this mapping is enabled */
  enabled: boolean;
}

// Full CLIProxyAPI configuration (persisted to ~/.auto-claude/cliproxy-config.json)
export interface CLIProxyConfig {
  /** Whether CLIProxyAPI mode is enabled */
  enabled: boolean;
  /** CLIProxyAPI server URL */
  url: string;
  /** API key for authentication */
  apiKey: string;
  /** Model mappings from Auto-Claude models to CLIProxyAPI models */
  modelMappings: ModelMapping[];
  /** Last successful connection test timestamp */
  lastConnected?: string;
  /** Available models from the proxy (cached) */
  availableModels?: string[];
}
