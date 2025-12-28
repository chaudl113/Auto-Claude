#!/usr/bin/env python3
"""
Tests for Spec Template System
============================
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.spec_template import (
    BUILTIN_TEMPLATES,
    SpecTemplate,
    SpecTemplateManager,
    get_template_manager,
)


class TestSpecTemplateManager:
    """Test spec template manager functionality."""

    @pytest.fixture
    def tmp_path(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_manager_initialization_no_custom_dir(self):
        """Test manager initialization without custom templates dir."""
        manager = SpecTemplateManager()

        assert manager.templates_dir is None
        assert len(manager._custom_templates) == 0

    def test_manager_initialization_with_custom_dir(self, tmp_path):
        """Test manager initialization with custom templates dir."""
        manager = SpecTemplateManager(tmp_path)

        assert manager.templates_dir == tmp_path
        assert len(manager._custom_templates) == 0

    def test_manager_loads_custom_templates(self, tmp_path):
        """Test manager loads custom templates from directory."""
        # Create custom template
        custom_template = {
            "name": "Custom Template",
            "description": "A custom template",
            "phases": [
                {
                    "phase": 1,
                    "name": "Test Phase",
                    "type": "implementation",
                    "subtasks": [
                        {
                            "id": "test-task",
                            "description": "Test task",
                            "files_to_create": ["test.py"],
                        }
                    ],
                }
            ],
            "final_acceptance": ["Works correctly"],
        }

        template_file = tmp_path / "custom.json"
        with open(template_file, "w") as f:
            json.dump(custom_template, f)

        # Create manager (should load templates)
        manager = SpecTemplateManager(tmp_path)

        assert "custom" in manager._custom_templates
        assert (
            manager._custom_templates["custom"]["name"] == "Custom Template"
        )

    def test_list_templates_includes_builtin(self, tmp_path):
        """Test list_templates includes built-in templates."""
        manager = SpecTemplateManager()

        templates = manager.list_templates()

        # Should include built-in templates
        template_ids = [t.id for t in templates]

        assert "auth-crud" in template_ids
        assert "api-endpoint" in template_ids
        assert "database-migration" in template_ids
        assert "ui-component" in template_ids

    def test_list_templates_includes_custom(self, tmp_path):
        """Test list_templates includes custom templates."""
        # Create custom template
        custom_template = {
            "name": "Custom Feature",
            "description": "Custom",
            "phases": [],
            "final_acceptance": [],
        }

        template_file = tmp_path / "custom.json"
        with open(template_file, "w") as f:
            json.dump(custom_template, f)

        manager = SpecTemplateManager(tmp_path)
        templates = manager.list_templates()

        template_ids = [t.id for t in templates]

        assert "custom" in template_ids

        # Check built-in templates are also present
        assert "auth-crud" in template_ids

    def test_get_template_builtin(self):
        """Test getting a built-in template."""
        manager = SpecTemplateManager()
        template = manager.get_template("auth-crud")

        assert template is not None
        assert template.id == "auth-crud"
        assert "Authentication" in template.name
        assert len(template.phases) > 0
        assert len(template.final_acceptance) > 0

    def test_get_template_custom(self, tmp_path):
        """Test getting a custom template."""
        custom_template = {
            "name": "My Custom Template",
            "description": "Test",
            "phases": [
                {
                    "phase": 1,
                    "name": "Phase 1",
                    "type": "implementation",
                    "subtasks": [],
                }
            ],
            "final_acceptance": [],
        }

        template_file = tmp_path / "my-custom.json"
        with open(template_file, "w") as f:
            json.dump(custom_template, f)

        manager = SpecTemplateManager(tmp_path)
        template = manager.get_template("my-custom")

        assert template is not None
        assert template.id == "my-custom"
        assert template.name == "My Custom Template"

    def test_get_template_not_found(self):
        """Test getting non-existent template returns None."""
        manager = SpecTemplateManager()
        template = manager.get_template("non-existent")

        assert template is None

    def test_create_from_template_basic(self):
        """Test creating spec from template without variables."""
        manager = SpecTemplateManager()
        spec_dict = manager.create_from_template("api-endpoint")

        assert spec_dict["feature"] == "REST API Endpoint: New Feature"
        assert spec_dict["workflow_type"] == "feature"
        assert "phases" in spec_dict
        assert "final_acceptance" in spec_dict

    def test_create_from_template_with_variables(self):
        """Test creating spec from template with variables."""
        manager = SpecTemplateManager()
        spec_dict = manager.create_from_template(
            "api-endpoint",
            variables={"name": "Create User", "endpoint_name": "users"},
        )

        # Variables should be substituted in phases
        phases_json = json.dumps(spec_dict["phases"])

        assert "users" in phases_json
        assert "Create User" in spec_dict["feature"]

    def test_create_from_template_not_found(self):
        """Test creating spec from non-existent template raises error."""
        manager = SpecTemplateManager()

        with pytest.raises(ValueError, match="Template not found"):
            manager.create_from_template("non-existent")

    def test_save_custom_template(self, tmp_path):
        """Test saving a custom template."""
        manager = SpecTemplateManager(tmp_path)

        template_data = {
            "name": "New Custom",
            "description": "Test",
            "phases": [],
            "final_acceptance": [],
        }

        result = manager.save_custom_template("new-custom", template_data)

        assert result is True
        assert "new-custom" in manager._custom_templates

        # File should exist
        template_file = tmp_path / "new-custom.json"
        assert template_file.exists()

    def test_delete_custom_template(self, tmp_path):
        """Test deleting a custom template."""
        # First create a template
        manager = SpecTemplateManager(tmp_path)

        template_data = {
            "name": "ToDelete",
            "description": "Test",
            "phases": [],
            "final_acceptance": [],
        }

        manager.save_custom_template("to-delete", template_data)

        # Now delete it
        result = manager.delete_custom_template("to-delete")

        assert result is True
        assert "to-delete" not in manager._custom_templates

        # File should be deleted
        template_file = tmp_path / "to-delete.json"
        assert not template_file.exists()

    def test_delete_non_existent_template(self, tmp_path):
        """Test deleting non-existent template returns False."""
        manager = SpecTemplateManager(tmp_path)
        result = manager.delete_custom_template("does-not-exist")

        assert result is False

    def test_save_custom_template_no_dir(self):
        """Test saving custom template when no directory configured."""
        manager = SpecTemplateManager()

        result = manager.save_custom_template(
            "test", {"name": "Test", "phases": [], "final_acceptance": []}
        )

        assert result is False


class TestSpecTemplate:
    """Test SpecTemplate dataclass."""

    def test_spec_template_creation(self):
        """Test SpecTemplate creation."""
        template = SpecTemplate(
            id="auth-crud",
            name="Authentication CRUD",
            description="Auth with CRUD",
            phases=[{"phase": 1, "name": "Setup", "subtasks": []}],
            final_acceptance=["Works"],
        )

        assert template.id == "auth-crud"
        assert template.name == "Authentication CRUD"
        assert len(template.phases) == 1
        assert len(template.final_acceptance) == 1

    def test_spec_template_to_dict(self):
        """Test SpecTemplate to_dict method."""
        template = SpecTemplate(
            id="test",
            name="Test Template",
            description="Test",
            phases=[
                {"phase": 1, "name": "Phase 1", "subtasks": []}
            ],
            final_acceptance=["Done"],
        )

        spec_dict = template.to_dict()

        assert spec_dict["feature"] == "Test Template"
        assert spec_dict["workflow_type"] == "feature"
        assert "phases" in spec_dict
        assert "final_acceptance" in spec_dict


class TestBuiltinTemplates:
    """Test built-in template structure."""

    def test_builtin_templates_exist(self):
        """Verify built-in templates are defined."""
        assert "auth-crud" in BUILTIN_TEMPLATES
        assert "api-endpoint" in BUILTIN_TEMPLATES
        assert "database-migration" in BUILTIN_TEMPLATES
        assert "ui-component" in BUILTIN_TEMPLATES

    def test_builtin_template_structure(self):
        """Test built-in templates have required fields."""
        for template_id, template_data in BUILTIN_TEMPLATES.items():
            assert "name" in template_data
            assert "description" in template_data
            assert "phases" in template_data
            assert "final_acceptance" in template_data

            # Check phases structure
            for phase in template_data["phases"]:
                assert "phase" in phase
                assert "name" in phase
                assert "subtasks" in phase

    def test_auth_crud_template(self):
        """Test auth-crud template has expected content."""
        template = BUILTIN_TEMPLATES["auth-crud"]

        assert "Authentication" in template["name"]
        assert len(template["phases"]) >= 3  # Should have multiple phases
        assert len(template["final_acceptance"]) > 0

    def test_api_endpoint_template(self):
        """Test api-endpoint template structure."""
        template = BUILTIN_TEMPLATES["api-endpoint"]

        assert "API" in template["name"]
        assert len(template["phases"]) >= 1


class TestFactoryFunction:
    """Test factory function."""

    def test_get_template_manager(self, tmp_path):
        """Test factory function creates manager."""
        manager = get_template_manager(tmp_path)

        assert isinstance(manager, SpecTemplateManager)
        assert manager.templates_dir == tmp_path

    def test_get_template_manager_no_dir(self):
        """Test factory function without directory."""
        manager = get_template_manager()

        assert isinstance(manager, SpecTemplateManager)
        assert manager.templates_dir is None
