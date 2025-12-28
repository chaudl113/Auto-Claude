/**
 * Spec Template IPC Handlers
 *
 * Handles IPC requests for spec template operations:
 * - List available templates
 * - Get template details
 * - Create spec from template
 */

import { ipcMain } from 'electron';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult } from '../../shared/types';

interface SpecTemplatePhase {
  phase: number;
  name: string;
  type: string;
  subtasks: unknown[];
  parallel_safe?: boolean;
}

interface SpecTemplateData {
  name: string;
  description: string;
  phases: SpecTemplatePhase[];
  final_acceptance: string[];
}

export interface SpecTemplate {
  id: string;
  name: string;
  description: string;
  phases: SpecTemplatePhase[];
  finalAcceptance: string[];
}

const BUILTIN_TEMPLATES: Record<string, SpecTemplateData> = {
  'auth-crud': {
    name: 'Authentication + CRUD',
    description: 'User authentication with full CRUD operations',
    phases: [
      {
        phase: 1,
        name: 'Database Setup',
        type: 'implementation',
        subtasks: [
          {
            id: 'db-setup',
            description: 'Create user model with authentication fields',
            files_to_create: ['models/user.py', 'migrations/create_users_table.sql']
          }
        ]
      },
      {
        phase: 2,
        name: 'Authentication Service',
        type: 'implementation',
        subtasks: [
          {
            id: 'auth-service',
            description: 'Implement authentication service with JWT tokens',
            files_to_create: ['services/auth.py']
          },
          {
            id: 'auth-middleware',
            description: 'Add authentication middleware to protect routes',
            files_to_create: ['middleware/auth.py']
          }
        ]
      },
      {
        phase: 3,
        name: 'CRUD Operations',
        type: 'implementation',
        parallel_safe: true,
        subtasks: [
          { id: 'user-create', description: 'Create user endpoint (POST /users)' },
          { id: 'user-read', description: 'Read user endpoint (GET /users/:id)' },
          { id: 'user-update', description: 'Update user endpoint (PUT /users/:id)' },
          { id: 'user-delete', description: 'Delete user endpoint (DELETE /users/:id)' }
        ]
      }
    ],
    final_acceptance: [
      'User can register with email/password',
      'User can login and receive JWT token',
      'Protected routes require authentication',
      'Full CRUD operations work for users',
      'Password is hashed before storage',
      'JWT tokens expire correctly'
    ]
  },
  'api-endpoint': {
    name: 'REST API Endpoint',
    description: 'Single REST API endpoint with validation',
    phases: [
      {
        phase: 1,
        name: 'Endpoint Implementation',
        type: 'implementation',
        subtasks: [
          { id: 'endpoint-handler', description: 'Implement API endpoint handler' },
          { id: 'request-validation', description: 'Add request validation and error handling' },
          { id: 'response-formatter', description: 'Implement response formatting' }
        ]
      },
      {
        phase: 2,
        name: 'Testing',
        type: 'verification',
        subtasks: [
          { id: 'unit-tests', description: 'Write unit tests for endpoint' },
          { id: 'integration-tests', description: 'Write integration tests' }
        ]
      }
    ],
    final_acceptance: [
      'Endpoint responds with correct status codes',
      'Request validation works correctly',
      'Error handling covers all cases',
      'Tests pass successfully'
    ]
  },
  'database-migration': {
    name: 'Database Migration',
    description: 'Database schema migration with rollback',
    phases: [
      {
        phase: 1,
        name: 'Migration Script',
        type: 'implementation',
        subtasks: [
          { id: 'migration-up', description: 'Write forward migration script' },
          { id: 'migration-down', description: 'Write rollback migration script' }
        ]
      },
      {
        phase: 2,
        name: 'Testing',
        type: 'verification',
        subtasks: [
          { id: 'migration-test', description: 'Test migration and rollback' }
        ]
      }
    ],
    final_acceptance: [
      'Migration runs successfully',
      'Rollback works correctly',
      'Database constraints are preserved',
      'Tests pass'
    ]
  },
  'ui-component': {
    name: 'UI Component',
    description: 'Reusable React/Vue/Svelte component',
    phases: [
      {
        phase: 1,
        name: 'Component Structure',
        type: 'implementation',
        subtasks: [
          { id: 'component-base', description: 'Create base component structure' },
          { id: 'types-interfaces', description: 'Define TypeScript types/interfaces' }
        ]
      },
      {
        phase: 2,
        name: 'Styling',
        type: 'implementation',
        subtasks: [
          { id: 'component-styles', description: 'Add component styles' }
        ]
      },
      {
        phase: 3,
        name: 'Testing',
        type: 'verification',
        subtasks: [
          { id: 'component-tests', description: 'Write component tests' }
        ]
      }
    ],
    final_acceptance: [
      'Component renders correctly',
      'Props are properly typed',
      'Styles are applied correctly',
      'Tests pass'
    ]
  }
};

function convertToSpecTemplate(id: string, data: SpecTemplateData): SpecTemplate {
  return {
    id,
    name: data.name,
    description: data.description,
    phases: data.phases,
    finalAcceptance: data.final_acceptance
  };
}

export function registerSpecTemplateHandlers(): void {
  ipcMain.handle(
    IPC_CHANNELS.SPEC_TEMPLATE_LIST,
    async (): Promise<IPCResult<SpecTemplate[]>> => {
      try {
        const templates = Object.entries(BUILTIN_TEMPLATES).map(([id, data]) =>
          convertToSpecTemplate(id, data)
        );
        return { success: true, data: templates };
      } catch (error) {
        return { success: false, error: String(error) };
      }
    }
  );

  ipcMain.handle(
    IPC_CHANNELS.SPEC_TEMPLATE_GET,
    async (_, templateId: string): Promise<IPCResult<SpecTemplate>> => {
      try {
        const templateData = BUILTIN_TEMPLATES[templateId];
        if (!templateData) {
          return { success: false, error: `Template not found: ${templateId}` };
        }
        return { success: true, data: convertToSpecTemplate(templateId, templateData) };
      } catch (error) {
        return { success: false, error: String(error) };
      }
    }
  );

  ipcMain.handle(
    IPC_CHANNELS.SPEC_TEMPLATE_CREATE_FROM,
    async (
      _,
      templateId: string,
      variables?: Record<string, string>
    ): Promise<IPCResult<{ phases: unknown[]; finalAcceptance: string[] }>> => {
      try {
        const templateData = BUILTIN_TEMPLATES[templateId];
        if (!templateData) {
          return { success: false, error: `Template not found: ${templateId}` };
        }

        let phasesJson = JSON.stringify(templateData.phases);

        if (variables) {
          for (const [key, value] of Object.entries(variables)) {
            const placeholder = `{{${key}}}`;
            phasesJson = phasesJson.replace(new RegExp(placeholder, 'g'), value);
          }
        }

        const phases = JSON.parse(phasesJson);

        return {
          success: true,
          data: {
            phases,
            finalAcceptance: templateData.final_acceptance
          }
        };
      } catch (error) {
        return { success: false, error: String(error) };
      }
    }
  );

  console.warn('[IPC] Spec template handlers registered');
}
