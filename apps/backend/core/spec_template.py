#!/usr/bin/env python3
"""
Spec Template System
===================

Provides reusable templates for common spec types.
Templates for: auth, CRUD, API endpoints, and more.

Benefits:
- Faster spec creation with pre-built templates
- Consistent structure across similar features
- Best practices built-in
- Easy customization

Usage:
    manager = SpecTemplateManager(templates_dir)
    spec = manager.create_from_template("auth-crud", "User Management")
    spec.save(output_path)
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from core.debug import debug, debug_detailed, debug_error, debug_success

logger = logging.getLogger(__name__)


# Built-in templates (embedded in code for portability)
BUILTIN_TEMPLATES = {
    "auth-crud": {
        "name": "Authentication + CRUD",
        "description": "User authentication with full CRUD operations",
        "phases": [
            {
                "phase": 1,
                "name": "Database Setup",
                "type": "implementation",
                "subtasks": [
                    {
                        "id": "db-setup",
                        "description": "Create user model with authentication fields",
                        "files_to_create": [
                            "models/user.py",
                            "migrations/create_users_table.sql",
                        ],
                        "verification": {
                            "type": "manual",
                            "steps": [
                                "Verify database table structure",
                                "Check field types and constraints",
                                "Validate indexes",
                            ],
                        },
                    },
                ],
            },
            {
                "phase": 2,
                "name": "Authentication Service",
                "type": "implementation",
                "subtasks": [
                    {
                        "id": "auth-service",
                        "description": "Implement authentication service with JWT tokens",
                        "files_to_create": ["services/auth.py"],
                        "files_to_modify": ["models/user.py"],
                        "verification": {
                            "type": "test",
                            "test_files": ["tests/test_auth.py"],
                            "expected_behavior": "Users can login and receive JWT tokens",
                        },
                    },
                    {
                        "id": "auth-middleware",
                        "description": "Add authentication middleware to protect routes",
                        "files_to_create": ["middleware/auth.py"],
                        "files_to_modify": ["app.py"],
                    },
                ],
            },
            {
                "phase": 3,
                "name": "CRUD Operations",
                "type": "implementation",
                "parallel_safe": True,
                "subtasks": [
                    {
                        "id": "user-create",
                        "description": "Create user endpoint (POST /users)",
                        "files_to_create": ["controllers/user_controller.py"],
                        "files_to_modify": ["app.py"],
                    },
                    {
                        "id": "user-read",
                        "description": "Read user endpoint (GET /users/:id)",
                        "files_to_create": [],
                        "files_to_modify": ["controllers/user_controller.py"],
                    },
                    {
                        "id": "user-update",
                        "description": "Update user endpoint (PUT /users/:id)",
                        "files_to_create": [],
                        "files_to_modify": ["controllers/user_controller.py"],
                    },
                    {
                        "id": "user-delete",
                        "description": "Delete user endpoint (DELETE /users/:id)",
                        "files_to_create": [],
                        "files_to_modify": ["controllers/user_controller.py"],
                    },
                ],
            },
        ],
        "final_acceptance": [
            "User can register with email/password",
            "User can login and receive JWT token",
            "Protected routes require authentication",
            "Full CRUD operations work for users",
            "Password is hashed before storage",
            "JWT tokens expire correctly",
        ],
    },
    "api-endpoint": {
        "name": "REST API Endpoint",
        "description": "Single REST API endpoint with validation",
        "phases": [
            {
                "phase": 1,
                "name": "Endpoint Implementation",
                "type": "implementation",
                "subtasks": [
                    {
                        "id": "endpoint-handler",
                        "description": "Implement API endpoint handler",
                        "files_to_create": ["routes/{{endpoint_name}}.py"],
                        "files_to_modify": ["app.py"],
                    },
                    {
                        "id": "request-validation",
                        "description": "Add request validation and error handling",
                        "files_to_create": ["schemas/{{endpoint_name}}_schema.py"],
                        "files_to_modify": ["routes/{{endpoint_name}}.py"],
                    },
                    {
                        "id": "response-formatter",
                        "description": "Implement response formatting",
                        "files_to_create": [],
                        "files_to_modify": ["routes/{{endpoint_name}}.py"],
                    },
                ],
            },
            {
                "phase": 2,
                "name": "Testing",
                "type": "verification",
                "subtasks": [
                    {
                        "id": "unit-tests",
                        "description": "Write unit tests for endpoint",
                        "files_to_create": ["tests/test_{{endpoint_name}}.py"],
                    },
                    {
                        "id": "integration-tests",
                        "description": "Write integration tests",
                        "files_to_create": ["tests/integration/test_{{endpoint_name}}.py"],
                    },
                ],
            },
        ],
        "final_acceptance": [
            "Endpoint responds with correct status codes",
            "Request validation works correctly",
            "Error handling covers all cases",
            "Tests pass successfully",
        ],
    },
    "database-migration": {
        "name": "Database Migration",
        "description": "Database schema migration with rollback",
        "phases": [
            {
                "phase": 1,
                "name": "Migration Script",
                "type": "implementation",
                "subtasks": [
                    {
                        "id": "migration-up",
                        "description": "Write forward migration script",
                        "files_to_create": ["migrations/{{timestamp}}_{{name}}_up.sql"],
                        "verification": {
                            "type": "manual",
                            "steps": [
                                "Run migration in development database",
                                "Verify schema changes",
                                "Check constraints and indexes",
                            ],
                        },
                    },
                    {
                        "id": "migration-down",
                        "description": "Write rollback migration script",
                        "files_to_create": ["migrations/{{timestamp}}_{{name}}_down.sql"],
                    },
                ],
            },
            {
                "phase": 2,
                "name": "Testing",
                "type": "verification",
                "subtasks": [
                    {
                        "id": "migration-test",
                        "description": "Test migration and rollback",
                        "files_to_create": ["tests/test_migration_{{name}}.py"],
                    },
                ],
            },
        ],
        "final_acceptance": [
            "Migration runs successfully",
            "Rollback works correctly",
            "Database constraints are preserved",
            "Tests pass",
        ],
    },
    "ui-component": {
        "name": "UI Component",
        "description": "Reusable React/Vue/Svelte component",
        "phases": [
            {
                "phase": 1,
                "name": "Component Structure",
                "type": "implementation",
                "subtasks": [
                    {
                        "id": "component-base",
                        "description": "Create base component structure",
                        "files_to_create": ["components/{{component_name}}.tsx"],
                        "verification": {
                            "type": "manual",
                            "steps": [
                                "Component renders without errors",
                                "Props are documented",
                                "Styles are scoped correctly",
                            ],
                        },
                    },
                    {
                        "id": "types-interfaces",
                        "description": "Define TypeScript types/interfaces",
                        "files_to_create": ["types/{{component_name}}.ts"],
                    },
                ],
            },
            {
                "phase": 2,
                "name": "Styling",
                "type": "implementation",
                "subtasks": [
                    {
                        "id": "component-styles",
                        "description": "Add component styles",
                        "files_to_create": ["components/{{component_name}}.module.css"],
                    },
                ],
            },
            {
                "phase": 3,
                "name": "Testing",
                "type": "verification",
                "subtasks": [
                    {
                        "id": "component-tests",
                        "description": "Write component tests",
                        "files_to_create": [
                            "components/{{component_name}}.test.tsx"
                        ],
                    },
                ],
            },
        ],
        "final_acceptance": [
            "Component renders correctly",
            "Props are properly typed",
            "Styles are applied correctly",
            "Tests pass",
        ],
    },
}


@dataclass
class SpecTemplate:
    """Represents a spec template."""

    id: str
    name: str
    description: str
    phases: List[dict]
    final_acceptance: List[str]

    # Template variables (to be filled)
    variables: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Converts to dictionary representation."""
        return {
            "feature": self.name,
            "workflow_type": "feature",
            "phases": self.phases,
            "final_acceptance": self.final_acceptance,
        }


class SpecTemplateManager:
    """
    Manages spec templates and creates specs from them.

    Usage:
        manager = SpecTemplateManager(templates_dir)
        templates = manager.list_templates()

        # Create spec from template with variables
        spec_dict = manager.create_from_template(
            "auth-crud",
            variables={
                "endpoint_name": "users",
                "component_name": "UserForm",
            }
        )
    """

    def __init__(self, templates_dir: Path | None = None):
        """
        Initialize template manager.

        Args:
            templates_dir: Optional directory for custom templates
        """
        self.templates_dir = Path(templates_dir) if templates_dir else None
        self._custom_templates: Dict[str, dict] = {}

        # Load custom templates if directory provided
        if self.templates_dir and self.templates_dir.exists():
            self._load_custom_templates()

    def _load_custom_templates(self) -> None:
        """Loads custom templates from templates directory."""
        debug_detailed("template_manager", "Loading custom templates")

        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file) as f:
                    template = json.load(f)
                    template_id = template_file.stem
                    self._custom_templates[template_id] = template

                    debug_success(
                        "template_manager",
                        f"Loaded custom template: {template_id}"
                    )
            except Exception as e:
                logger.error(f"Failed to load template {template_file}: {e}")
                debug_error(
                    "template_manager", "Load failed", template=template_file, error=str(e)
                )

    def list_templates(self) -> List[SpecTemplate]:
        """
        Lists all available templates.

        Returns:
            List of SpecTemplate objects (both built-in and custom)
        """
        templates = []

        # Add built-in templates
        for template_id, template_data in BUILTIN_TEMPLATES.items():
            templates.append(
                SpecTemplate(
                    id=template_id,
                    name=template_data["name"],
                    description=template_data["description"],
                    phases=template_data["phases"],
                    final_acceptance=template_data["final_acceptance"],
                )
            )

        # Add custom templates
        for template_id, template_data in self._custom_templates.items():
            templates.append(
                SpecTemplate(
                    id=template_id,
                    name=template_data.get("name", template_id),
                    description=template_data.get("description", ""),
                    phases=template_data.get("phases", []),
                    final_acceptance=template_data.get("final_acceptance", []),
                )
            )

        return templates

    def get_template(self, template_id: str) -> SpecTemplate | None:
        """
        Gets a specific template by ID.

        Args:
            template_id: Template identifier (e.g., "auth-crud")

        Returns:
            SpecTemplate or None if not found
        """
        # Check built-in templates
        if template_id in BUILTIN_TEMPLATES:
            template_data = BUILTIN_TEMPLATES[template_id]
            return SpecTemplate(
                id=template_id,
                name=template_data["name"],
                description=template_data["description"],
                phases=template_data["phases"],
                final_acceptance=template_data["final_acceptance"],
            )

        # Check custom templates
        if template_id in self._custom_templates:
            template_data = self._custom_templates[template_id]
            return SpecTemplate(
                id=template_id,
                name=template_data.get("name", template_id),
                description=template_data.get("description", ""),
                phases=template_data.get("phases", []),
                final_acceptance=template_data.get("final_acceptance", []),
            )

        return None

    def create_from_template(
        self,
        template_id: str,
        variables: Dict[str, str] | None = None,
    ) -> dict:
        """
        Creates a spec from template with variable substitution.

        Args:
            template_id: Template to use
            variables: Key-value pairs to substitute in template

        Returns:
            Dictionary representation of spec ready to save
        """
        debug(
            "template_manager",
            "Creating spec from template",
            template_id=template_id,
            variables=variables,
        )

        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        # Apply variable substitution
        variables = variables or {}
        phases_json = json.dumps(template.phases)

        # Replace {{variable}} patterns
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            phases_json = phases_json.replace(placeholder, value)

        phases = json.loads(phases_json)

        # Build spec dictionary
        spec_dict = {
            "feature": f"{template.name}: {variables.get('name', 'New Feature')}",
            "workflow_type": "feature",
            "phases": phases,
            "final_acceptance": template.final_acceptance,
        }

        debug_success("template_manager", "Spec created from template")
        return spec_dict

    def save_custom_template(
        self, template_id: str, template_data: dict
    ) -> bool:
        """
        Saves a custom template to templates directory.

        Args:
            template_id: Template identifier
            template_data: Template dictionary (phases, final_acceptance, etc.)

        Returns:
            True if saved successfully
        """
        if not self.templates_dir:
            logger.error("No templates directory configured")
            return False

        try:
            template_file = self.templates_dir / f"{template_id}.json"
            template_file.parent.mkdir(parents=True, exist_ok=True)

            with open(template_file, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2)

            self._custom_templates[template_id] = template_data

            debug_success(
                "template_manager",
                f"Saved custom template: {template_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save template: {e}")
            debug_error(
                "template_manager", "Save failed", template_id=template_id, error=str(e)
            )
            return False

    def delete_custom_template(self, template_id: str) -> bool:
        """
        Deletes a custom template.

        Args:
            template_id: Template identifier to delete

        Returns:
            True if deleted successfully
        """
        if template_id not in self._custom_templates:
            return False

        if not self.templates_dir:
            return False

        try:
            template_file = self.templates_dir / f"{template_id}.json"
            if template_file.exists():
                template_file.unlink()

            del self._custom_templates[template_id]

            debug_success(
                "template_manager",
                f"Deleted custom template: {template_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to delete template: {e}")
            return False


def get_template_manager(templates_dir: Path | None = None) -> SpecTemplateManager:
    """Factory function to get SpecTemplateManager instance."""
    return SpecTemplateManager(templates_dir)
