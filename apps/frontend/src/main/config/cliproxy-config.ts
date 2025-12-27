/**
 * CLIProxyAPI Configuration Manager
 *
 * Handles reading and writing CLIProxyAPI configuration to:
 *   ~/.auto-claude/cliproxy-config.json
 *
 * This configuration is shared between the frontend and backend.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import type { CLIProxyConfig, ModelMapping } from '../../shared/types';

// Config file location
const CONFIG_DIR = path.join(os.homedir(), '.auto-claude');
const CONFIG_FILE = path.join(CONFIG_DIR, 'cliproxy-config.json');

// Default configuration
const DEFAULT_CONFIG: CLIProxyConfig = {
  enabled: false,
  url: 'http://localhost:8317',
  apiKey: '',
  modelMappings: [
    { source: 'opus', target: 'gpt-5.1', enabled: true },
    { source: 'sonnet', target: 'gpt-5.1', enabled: true },
    { source: 'haiku', target: 'claude-haiku-4.5', enabled: true },
  ],
};

/**
 * Ensure config directory exists
 */
function ensureConfigDir(): void {
  if (!fs.existsSync(CONFIG_DIR)) {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
  }
}

/**
 * Load CLIProxyAPI configuration from disk
 */
export function loadCliProxyConfig(): CLIProxyConfig {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      const content = fs.readFileSync(CONFIG_FILE, 'utf-8');
      const config = JSON.parse(content) as Partial<CLIProxyConfig>;

      // Merge with defaults to ensure all fields exist
      return {
        ...DEFAULT_CONFIG,
        ...config,
        modelMappings: config.modelMappings?.length
          ? config.modelMappings
          : DEFAULT_CONFIG.modelMappings,
      };
    }
  } catch (error) {
    console.error('Failed to load CLIProxy config:', error);
  }

  return { ...DEFAULT_CONFIG };
}

/**
 * Save CLIProxyAPI configuration to disk
 */
export function saveCliProxyConfig(config: CLIProxyConfig): void {
  try {
    ensureConfigDir();
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), 'utf-8');
  } catch (error) {
    console.error('Failed to save CLIProxy config:', error);
    throw error;
  }
}

/**
 * Get the config file path (for debugging)
 */
export function getConfigFilePath(): string {
  return CONFIG_FILE;
}

/**
 * Check if config file exists
 */
export function configExists(): boolean {
  return fs.existsSync(CONFIG_FILE);
}

/**
 * Get default model mappings
 */
export function getDefaultModelMappings(): ModelMapping[] {
  return [...DEFAULT_CONFIG.modelMappings];
}
