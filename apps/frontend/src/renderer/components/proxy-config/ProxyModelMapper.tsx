/**
 * ProxyModelMapper Component
 *
 * Shared component for configuring CLIProxyAPI connection and model mappings.
 * Used in both Onboarding (OAuthStep) and Settings (IntegrationSettings).
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Wifi,
  WifiOff,
  Loader2,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
  RefreshCw,
  Settings2,
  Zap,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Switch } from '../ui/switch';
import { Card, CardContent } from '../ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { cn } from '../../lib/utils';
import type { CLIProxyConfig, ModelMapping } from '../../../shared/types';

interface ProxyModelMapperProps {
  /** Callback when config changes (for parent to track dirty state) */
  onConfigChange?: (config: CLIProxyConfig) => void;
  /** Callback when config is saved successfully */
  onSaveSuccess?: () => void;
  /** Whether to show the enable/disable toggle */
  showEnableToggle?: boolean;
  /** Compact mode for settings panel */
  compact?: boolean;
  /** Class name for container */
  className?: string;
}

// Source model display names
const SOURCE_MODEL_LABELS: Record<ModelMapping['source'], string> = {
  opus: 'Claude Opus (Heavy Tasks)',
  sonnet: 'Claude Sonnet (Default)',
  haiku: 'Claude Haiku (Fast)',
};

export function ProxyModelMapper({
  onConfigChange,
  onSaveSuccess,
  showEnableToggle = true,
  compact = false,
  className,
}: ProxyModelMapperProps) {
  // Config state
  const [config, setConfig] = useState<CLIProxyConfig>({
    enabled: false,
    url: 'http://localhost:8317',
    apiKey: '',
    modelMappings: [
      { source: 'opus', target: '', enabled: true },
      { source: 'sonnet', target: '', enabled: true },
      { source: 'haiku', target: '', enabled: true },
    ],
  });

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'unknown' | 'connected' | 'error'>('unknown');
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [hasChanges, setHasChanges] = useState(false);

  // Load config on mount
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const result = await window.electronAPI.getCliProxyConfig();
      if (result.success && result.data) {
        setConfig(result.data);
        if (result.data.availableModels?.length) {
          setAvailableModels(result.data.availableModels);
        }
        // Auto-test if enabled
        if (result.data.enabled && result.data.url && result.data.apiKey) {
          testConnection(result.data.url, result.data.apiKey);
        }
      }
    } catch (error) {
      console.error('Failed to load CLIProxy config:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const testConnection = async (url?: string, apiKey?: string) => {
    setIsTesting(true);
    setConnectionStatus('unknown');
    setConnectionError(null);

    try {
      const result = await window.electronAPI.testCliProxyConnection(
        url || config.url,
        apiKey || config.apiKey
      );

      if (result.success && result.data?.connected) {
        setConnectionStatus('connected');
        if (result.data.models?.length) {
          setAvailableModels(result.data.models);
          // Update config with available models cache
          updateConfig({ availableModels: result.data.models });
        }
      } else {
        setConnectionStatus('error');
        setConnectionError(result.error || 'Connection failed');
      }
    } catch (error) {
      setConnectionStatus('error');
      setConnectionError(error instanceof Error ? error.message : 'Connection failed');
    } finally {
      setIsTesting(false);
    }
  };

  const updateConfig = useCallback((updates: Partial<CLIProxyConfig>) => {
    setConfig(prev => {
      const newConfig = { ...prev, ...updates };
      setHasChanges(true);
      onConfigChange?.(newConfig);
      return newConfig;
    });
  }, [onConfigChange]);

  const updateModelMapping = useCallback((source: ModelMapping['source'], target: string) => {
    setConfig(prev => {
      const newMappings = prev.modelMappings.map(m =>
        m.source === source ? { ...m, target } : m
      );
      const newConfig = { ...prev, modelMappings: newMappings };
      setHasChanges(true);
      onConfigChange?.(newConfig);
      return newConfig;
    });
  }, [onConfigChange]);

  const toggleMappingEnabled = useCallback((source: ModelMapping['source']) => {
    setConfig(prev => {
      const newMappings = prev.modelMappings.map(m =>
        m.source === source ? { ...m, enabled: !m.enabled } : m
      );
      const newConfig = { ...prev, modelMappings: newMappings };
      setHasChanges(true);
      onConfigChange?.(newConfig);
      return newConfig;
    });
  }, [onConfigChange]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Add last connected timestamp if connected
      const configToSave: CLIProxyConfig = {
        ...config,
        lastConnected: connectionStatus === 'connected' ? new Date().toISOString() : config.lastConnected,
      };

      const result = await window.electronAPI.saveCliProxyConfig(configToSave);
      if (result.success) {
        setHasChanges(false);
        onSaveSuccess?.();
      } else {
        console.error('Failed to save config:', result.error);
      }
    } catch (error) {
      console.error('Failed to save CLIProxy config:', error);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className={cn("flex items-center justify-center py-8", className)}>
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header with Enable Toggle */}
      {showEnableToggle && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "h-10 w-10 rounded-lg flex items-center justify-center",
              config.enabled ? "bg-primary/10" : "bg-muted"
            )}>
              <Zap className={cn(
                "h-5 w-5",
                config.enabled ? "text-primary" : "text-muted-foreground"
              )} />
            </div>
            <div>
              <h3 className="text-sm font-medium">CLIProxyAPI Mode</h3>
              <p className="text-xs text-muted-foreground">
                Route API calls through ProxyPal
              </p>
            </div>
          </div>
          <Switch
            checked={config.enabled}
            onCheckedChange={(enabled) => updateConfig({ enabled })}
          />
        </div>
      )}

      {/* Connection Settings */}
      <Card className={cn(
        "border transition-colors",
        config.enabled ? "border-border" : "border-border/50 opacity-60"
      )}>
        <CardContent className={cn(compact ? "p-3" : "p-4", "space-y-4")}>
          {/* URL & API Key */}
          <div className="grid gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Proxy URL</Label>
              <Input
                value={config.url}
                onChange={(e) => updateConfig({ url: e.target.value })}
                placeholder="http://localhost:8317"
                disabled={!config.enabled}
                className="h-8 text-sm"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">API Key</Label>
              <div className="relative">
                <Input
                  type={showApiKey ? 'text' : 'password'}
                  value={config.apiKey}
                  onChange={(e) => updateConfig({ apiKey: e.target.value })}
                  placeholder="proxypal-local"
                  disabled={!config.enabled}
                  className="h-8 text-sm pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  disabled={!config.enabled}
                >
                  {showApiKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>
          </div>

          {/* Test Connection Button & Status */}
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => testConnection()}
              disabled={!config.enabled || isTesting || !config.url}
              className="gap-2"
            >
              {isTesting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Test Connection
            </Button>

            {connectionStatus !== 'unknown' && (
              <div className={cn(
                "flex items-center gap-1.5 text-xs",
                connectionStatus === 'connected' ? "text-success" : "text-destructive"
              )}>
                {connectionStatus === 'connected' ? (
                  <>
                    <Wifi className="h-3.5 w-3.5" />
                    Connected ({availableModels.length} models)
                  </>
                ) : (
                  <>
                    <WifiOff className="h-3.5 w-3.5" />
                    {connectionError || 'Connection failed'}
                  </>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Model Mappings */}
      {config.enabled && connectionStatus === 'connected' && availableModels.length > 0 && (
        <Card className="border border-border">
          <CardContent className={cn(compact ? "p-3" : "p-4", "space-y-3")}>
            <div className="flex items-center gap-2 text-sm font-medium">
              <Settings2 className="h-4 w-4 text-muted-foreground" />
              Model Mappings
            </div>

            <div className="space-y-2">
              {config.modelMappings.map((mapping) => (
                <div
                  key={mapping.source}
                  className={cn(
                    "flex items-center gap-3 p-2 rounded-lg border",
                    mapping.enabled ? "border-border bg-background" : "border-border/50 bg-muted/30"
                  )}
                >
                  <Switch
                    checked={mapping.enabled}
                    onCheckedChange={() => toggleMappingEnabled(mapping.source)}
                    className="scale-75"
                  />

                  <div className="flex-1 min-w-0">
                    <span className={cn(
                      "text-xs font-medium",
                      mapping.enabled ? "text-foreground" : "text-muted-foreground"
                    )}>
                      {SOURCE_MODEL_LABELS[mapping.source]}
                    </span>
                  </div>

                  <div className="text-xs text-muted-foreground">→</div>

                  <Select
                    value={mapping.target}
                    onValueChange={(value) => updateModelMapping(mapping.source, value)}
                    disabled={!mapping.enabled}
                  >
                    <SelectTrigger className="w-48 h-7 text-xs">
                      <SelectValue placeholder="Select target model" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableModels.map((model) => (
                        <SelectItem key={model} value={model} className="text-xs">
                          {model}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Save Button */}
      {hasChanges && (
        <div className="flex justify-end">
          <Button
            onClick={handleSave}
            disabled={isSaving}
            size="sm"
            className="gap-2"
          >
            {isSaving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
            Save Configuration
          </Button>
        </div>
      )}
    </div>
  );
}
