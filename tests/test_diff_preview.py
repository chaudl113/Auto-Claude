#!/usr/bin/env python3
"""
Tests for AI Diff Preview
=======================
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.diff_preview import (
    DiffPreview,
    DiffPreviewGenerator,
    FileChange,
    get_diff_preview_generator,
)


class TestDiffPreviewGenerator:
    """Test diff preview generation."""

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess.run for testing."""
        with patch("core.diff_preview.subprocess.run") as mock_run:
            yield mock_run

    @pytest.fixture
    def tmp_path(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_generator_initialization(self, tmp_path):
        """Test generator initializes correctly."""
        generator = DiffPreviewGenerator(tmp_path / "test_project")

        assert generator.project_dir == tmp_path / "test_project"
        assert generator.client is None

    def test_generator_with_client(self, tmp_path):
        """Test generator with Claude SDK client."""
        mock_client = Mock()
        generator = DiffPreviewGenerator(tmp_path / "test_project", client=mock_client)

        assert generator.client == mock_client

    def test_generate_preview_basic(self, tmp_path, mock_subprocess):
        """Test basic preview generation."""
        # Mock git commands
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""

            cmd = args[0]

            if "rev-parse" in cmd:
                result.stdout = "main"
            elif "diff --name-status" in cmd:
                result.stdout = "M\tsrc/app.py\nA\ttests/test.py"
            elif "diff --" in cmd:
                result.stdout = "+new line\n-old line"

            return result

        mock_subprocess.side_effect = side_effect

        generator = DiffPreviewGenerator(tmp_path / "test_project")
        preview = generator.generate_preview("spec-001", base_branch="main")

        assert preview.spec_name == "spec-001"
        assert preview.base_branch == "main"
        assert preview.spec_branch == "auto-claude/spec-001"
        assert len(preview.files_changed) == 2
        assert preview.total_additions > 0
        assert preview.total_deletions > 0

    def test_file_change_parsing(self, tmp_path, mock_subprocess):
        """Test file change status parsing."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""

            cmd = args[0]
            if "rev-parse" in cmd:
                result.stdout = "main"
            elif "diff --name-status" in cmd:
                result.stdout = "A\tsrc/new.py\nM\tsrc/mod.py\nD\tsrc/old.py"
            elif "diff --" in cmd:
                result.stdout = "+added\n-modified\n-deleted"

            return result

        mock_subprocess.side_effect = side_effect

        generator = DiffPreviewGenerator(tmp_path / "test_project")
        preview = generator.generate_preview("spec-001")

        # Check file statuses
        new_file = next((f for f in preview.files_changed if f.path == "src/new.py"), None)
        mod_file = next((f for f in preview.files_changed if f.path == "src/mod.py"), None)
        del_file = next((f for f in preview.files_changed if f.path == "src/old.py"), None)

        assert new_file is not None
        assert new_file.status == "A"
        assert mod_file is not None
        assert mod_file.status == "M"
        assert del_file is not None
        assert del_file.status == "D"

    def test_auto_detect_base_branch(self, tmp_path, mock_subprocess):
        """Test auto-detection of base branch."""
        # Mock main branch exists
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""

            cmd = args[0]

            if "rev-parse main" in " ".join(cmd):
                result.stdout = "abc123"
            elif "diff --name-status" in " ".join(cmd):
                result.stdout = ""

            return result

        mock_subprocess.side_effect = side_effect

        generator = DiffPreviewGenerator(tmp_path / "test_project")
        preview = generator.generate_preview("spec-001")

        assert preview.base_branch == "main"

    def test_git_error_handling(self, tmp_path, mock_subprocess):
        """Test graceful error handling for git failures."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 1
            result.stderr = "Git error"
            result.stdout = ""
            return result

        mock_subprocess.side_effect = side_effect

        generator = DiffPreviewGenerator(tmp_path / "test_project")
        preview = generator.generate_preview("spec-001")

        # Should not crash, return empty preview
        assert len(preview.files_changed) == 0

    @pytest.mark.asyncio
    async def test_ai_summary_generation(self, tmp_path, mock_subprocess):
        """Test AI summary generation."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""

            if "rev-parse" in args[0]:
                result.stdout = "main"
            elif "diff --name-status" in args[0]:
                result.stdout = "M\tsrc/app.py"

            return result

        mock_subprocess.side_effect = side_effect

        # Mock client
        mock_client = Mock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = AsyncMock()

        # Mock AI response
        async def mock_receive():
            from claude_agent_sdk import AssistantMessage, TextBlock

            yield AssistantMessage(
                content=[
                    TextBlock(text="This change adds user authentication features to the app.")
                ]
            )

        mock_client.receive_response.return_value = mock_receive()

        generator = DiffPreviewGenerator(tmp_path / "test_project", client=mock_client)
        preview = generator.generate_preview("spec-001", include_ai_summary=True)

        assert preview.summary is not None
        assert "authentication" in preview.summary.lower()


class TestFileChange:
    """Test FileChange dataclass."""

    def test_file_change_creation(self):
        """Test FileChange creation."""
        change = FileChange(
            path="src/app.py",
            status="M",
            diff="+new line\n-old line",
        )

        assert change.path == "src/app.py"
        assert change.status == "M"
        assert change.diff == "+new line\n-old line"
        assert change.summary is None

    def test_file_change_without_diff(self):
        """Test FileChange without diff."""
        change = FileChange(path="src/new.py", status="A")

        assert change.diff is None


class TestDiffPreview:
    """Test DiffPreview dataclass."""

    def test_diff_preview_creation(self):
        """Test DiffPreview creation."""
        files = [
            FileChange(path="src/app.py", status="M"),
            FileChange(path="tests/test.py", status="A"),
        ]

        preview = DiffPreview(
            spec_name="spec-001",
            base_branch="main",
            spec_branch="auto-claude/spec-001",
            files_changed=files,
        )

        assert preview.spec_name == "spec-001"
        assert len(preview.files_changed) == 2
        assert preview.total_additions == 0
        assert preview.total_deletions == 0
        assert preview.summary is None

    def test_diff_preview_with_summary(self):
        """Test DiffPreview with AI summary."""
        preview = DiffPreview(
            spec_name="spec-001",
            base_branch="main",
            spec_branch="auto-claude/spec-001",
            files_changed=[],
            summary="Adds user authentication",
        )

        assert preview.summary == "Adds user authentication"


class TestFactoryFunction:
    """Test factory function."""

    def test_get_diff_preview_generator(self, tmp_path):
        """Test factory function creates generator."""
        generator = get_diff_preview_generator(tmp_path / "test_project")

        assert isinstance(generator, DiffPreviewGenerator)
        assert generator.project_dir == tmp_path / "test_project"
