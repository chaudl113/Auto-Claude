import { useTranslation } from 'react-i18next';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Switch } from '../ui/switch';
import { SettingsSection } from './SettingsSection';
import type { AppSettings, PerformanceFeatureFlags } from '../../../shared/types';
import { DEFAULT_PERFORMANCE_FLAGS } from '../../../shared/constants';

interface PerformanceSettingsProps {
  settings: AppSettings;
  onSettingsChange: (settings: AppSettings) => void;
}

/**
 * Performance settings for feature flags controlling caching, pooling, and parallel execution
 */
export function PerformanceSettings({ settings, onSettingsChange }: PerformanceSettingsProps) {
  const { t } = useTranslation('settings');

  // Get current flags with defaults
  const flags: PerformanceFeatureFlags = {
    ...DEFAULT_PERFORMANCE_FLAGS,
    ...settings.performanceFlags
  };

  const updateFlag = <K extends keyof PerformanceFeatureFlags>(
    key: K,
    value: PerformanceFeatureFlags[K]
  ) => {
    onSettingsChange({
      ...settings,
      performanceFlags: {
        ...flags,
        [key]: value
      }
    });
  };

  return (
    <div className="space-y-8">
      {/* Caching & Pooling Section */}
      <SettingsSection
        title={t('performance.cachingPooling.title')}
        description={t('performance.cachingPooling.description')}
      >
        <div className="space-y-4">
          {/* Agent Cache */}
          <div className="flex items-center justify-between p-4 rounded-lg border border-border">
            <div className="space-y-1">
              <Label className="font-medium text-foreground">
                {t('performance.agentCache.title')}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t('performance.agentCache.description')}
              </p>
            </div>
            <Switch
              checked={flags.agentCacheEnabled}
              onCheckedChange={(checked) => updateFlag('agentCacheEnabled', checked)}
            />
          </div>

          {/* Worktree Pool */}
          <div className="flex items-center justify-between p-4 rounded-lg border border-border">
            <div className="space-y-1">
              <Label className="font-medium text-foreground">
                {t('performance.worktreePool.title')}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t('performance.worktreePool.description')}
              </p>
            </div>
            <Switch
              checked={flags.worktreePoolEnabled}
              onCheckedChange={(checked) => updateFlag('worktreePoolEnabled', checked)}
            />
          </div>

          {/* Worktree Pool Size */}
          {flags.worktreePoolEnabled && (
            <div className="flex items-center justify-between p-4 rounded-lg border border-border bg-muted/30">
              <div className="space-y-1">
                <Label className="font-medium text-foreground">
                  {t('performance.worktreePoolSize.title')}
                </Label>
                <p className="text-sm text-muted-foreground">
                  {t('performance.worktreePoolSize.description')}
                </p>
              </div>
              <Input
                type="number"
                min={1}
                max={8}
                value={flags.worktreePoolSize}
                onChange={(e) => {
                  const value = Math.min(8, Math.max(1, parseInt(e.target.value) || 3));
                  updateFlag('worktreePoolSize', value);
                }}
                className="w-20 text-center"
              />
            </div>
          )}
        </div>
      </SettingsSection>

      {/* Merge Safety Section */}
      <SettingsSection
        title={t('performance.mergeSafety.title')}
        description={t('performance.mergeSafety.description')}
      >
        <div className="space-y-4">
          {/* Diff Preview */}
          <div className="flex items-center justify-between p-4 rounded-lg border border-border">
            <div className="space-y-1">
              <Label className="font-medium text-foreground">
                {t('performance.diffPreview.title')}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t('performance.diffPreview.description')}
              </p>
            </div>
            <Switch
              checked={flags.diffPreviewEnabled}
              onCheckedChange={(checked) => updateFlag('diffPreviewEnabled', checked)}
            />
          </div>

          {/* Rollback */}
          <div className="flex items-center justify-between p-4 rounded-lg border border-border">
            <div className="space-y-1">
              <Label className="font-medium text-foreground">
                {t('performance.rollback.title')}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t('performance.rollback.description')}
              </p>
            </div>
            <Switch
              checked={flags.rollbackEnabled}
              onCheckedChange={(checked) => updateFlag('rollbackEnabled', checked)}
            />
          </div>
        </div>
      </SettingsSection>

      {/* Parallel Execution Section */}
      <SettingsSection
        title={t('performance.parallelExecution.title')}
        description={t('performance.parallelExecution.description')}
      >
        <div className="space-y-4">
          {/* Enable Parallel */}
          <div className="flex items-center justify-between p-4 rounded-lg border border-border">
            <div className="space-y-1">
              <Label className="font-medium text-foreground">
                {t('performance.enableParallel.title')}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t('performance.enableParallel.description')}
              </p>
            </div>
            <Switch
              checked={flags.parallelExecutionEnabled}
              onCheckedChange={(checked) => updateFlag('parallelExecutionEnabled', checked)}
            />
          </div>

          {/* Max Parallel Tasks */}
          {flags.parallelExecutionEnabled && (
            <div className="flex items-center justify-between p-4 rounded-lg border border-border bg-muted/30">
              <div className="space-y-1">
                <Label className="font-medium text-foreground">
                  {t('performance.maxParallelTasks.title')}
                </Label>
                <p className="text-sm text-muted-foreground">
                  {t('performance.maxParallelTasks.description')}
                </p>
              </div>
              <Input
                type="number"
                min={1}
                max={8}
                value={flags.maxParallelTasks}
                onChange={(e) => {
                  const value = Math.min(8, Math.max(1, parseInt(e.target.value) || 3));
                  updateFlag('maxParallelTasks', value);
                }}
                className="w-20 text-center"
              />
            </div>
          )}
        </div>
      </SettingsSection>

      {/* Spec Templates Section */}
      <SettingsSection
        title={t('performance.specTemplates.title')}
        description={t('performance.specTemplates.description')}
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 rounded-lg border border-border">
            <div className="space-y-1">
              <Label className="font-medium text-foreground">
                {t('performance.enableTemplates.title')}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t('performance.enableTemplates.description')}
              </p>
            </div>
            <Switch
              checked={flags.specTemplatesEnabled}
              onCheckedChange={(checked) => updateFlag('specTemplatesEnabled', checked)}
            />
          </div>
        </div>
      </SettingsSection>
    </div>
  );
}
