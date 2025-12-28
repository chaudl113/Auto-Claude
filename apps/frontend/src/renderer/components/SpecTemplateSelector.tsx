/**
 * SpecTemplateSelector - Component for selecting spec templates when creating tasks
 *
 * Provides a dropdown to select from available templates (auth-crud, api-endpoint, etc.)
 * Shows template description and allows applying template structure to the new task.
 */
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { FileCode2, Layers, ChevronDown, ChevronUp, Database, Globe, Component } from 'lucide-react';
import { Label } from './ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from './ui/select';
import { Badge } from './ui/badge';
import { cn } from '../lib/utils';

export interface SpecTemplate {
  id: string;
  name: string;
  description: string;
  phases: unknown[];
  finalAcceptance: string[];
}

interface SpecTemplateSelectorProps {
  /** Currently selected template ID (empty string means no template) */
  selectedTemplateId: string;
  /** Called when template selection changes */
  onTemplateChange: (templateId: string, template: SpecTemplate | null) => void;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Available templates (fetched from backend) */
  templates: SpecTemplate[];
  /** Whether templates are loading */
  isLoading?: boolean;
}

const TEMPLATE_ICONS: Record<string, React.ElementType> = {
  'auth-crud': Layers,
  'api-endpoint': Globe,
  'database-migration': Database,
  'ui-component': Component
};

const NO_TEMPLATE_VALUE = '__none__';

export function SpecTemplateSelector({
  selectedTemplateId,
  onTemplateChange,
  disabled = false,
  templates,
  isLoading = false
}: SpecTemplateSelectorProps) {
  const { t } = useTranslation();
  const [showDetails, setShowDetails] = useState(false);

  const selectedTemplate = templates.find(t => t.id === selectedTemplateId);

  const handleTemplateChange = (value: string) => {
    if (value === NO_TEMPLATE_VALUE) {
      onTemplateChange('', null);
    } else {
      const template = templates.find(t => t.id === value);
      onTemplateChange(value, template || null);
    }
  };

  const IconComponent = selectedTemplate
    ? TEMPLATE_ICONS[selectedTemplate.id] || FileCode2
    : FileCode2;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-medium flex items-center gap-2">
          <FileCode2 className="h-4 w-4 text-muted-foreground" />
          {t('specTemplate.title', 'Spec Template')}
        </Label>
        {selectedTemplate && (
          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            disabled={disabled}
          >
            {showDetails ? (
              <>
                {t('specTemplate.hideDetails', 'Hide details')}
                <ChevronUp className="h-3 w-3" />
              </>
            ) : (
              <>
                {t('specTemplate.showDetails', 'Show details')}
                <ChevronDown className="h-3 w-3" />
              </>
            )}
          </button>
        )}
      </div>

      <Select
        value={selectedTemplateId || NO_TEMPLATE_VALUE}
        onValueChange={handleTemplateChange}
        disabled={disabled || isLoading}
      >
        <SelectTrigger className="h-10">
          <SelectValue placeholder={isLoading
            ? t('specTemplate.loading', 'Loading templates...')
            : t('specTemplate.noTemplate', 'No template (start from scratch)')
          } />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NO_TEMPLATE_VALUE}>
            <div className="flex items-center gap-2">
              <FileCode2 className="h-4 w-4 text-muted-foreground" />
              <span>{t('specTemplate.noTemplate', 'No template (start from scratch)')}</span>
            </div>
          </SelectItem>
          {templates.map(template => {
            const TemplateIcon = TEMPLATE_ICONS[template.id] || FileCode2;
            return (
              <SelectItem key={template.id} value={template.id}>
                <div className="flex items-center gap-2">
                  <TemplateIcon className="h-4 w-4 text-primary" />
                  <span>{template.name}</span>
                  <Badge variant="outline" className="ml-2 text-xs">
                    {template.phases.length} {t('specTemplate.phases', 'phases')}
                  </Badge>
                </div>
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>

      {selectedTemplate && (
        <p className="text-xs text-muted-foreground">
          {selectedTemplate.description}
        </p>
      )}

      {/* Template Details */}
      {showDetails && selectedTemplate && (
        <div className="mt-3 p-3 rounded-lg border border-border bg-muted/30 space-y-3">
          {/* Phases */}
          <div>
            <h4 className="text-xs font-medium text-muted-foreground mb-2">
              {t('specTemplate.phasesTitle', 'Phases')}
            </h4>
            <div className="space-y-1">
              {(selectedTemplate.phases as Array<{ phase: number; name: string }>).map((phase, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm">
                  <Badge variant="secondary" className="text-xs min-w-[20px] justify-center">
                    {phase.phase}
                  </Badge>
                  <span>{phase.name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Final Acceptance Criteria */}
          {selectedTemplate.finalAcceptance.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">
                {t('specTemplate.acceptanceCriteria', 'Acceptance Criteria')}
              </h4>
              <ul className="text-xs text-muted-foreground space-y-1">
                {selectedTemplate.finalAcceptance.map((criteria, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-primary mt-0.5">•</span>
                    <span>{criteria}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SpecTemplateSelector;
