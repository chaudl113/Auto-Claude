#!/usr/bin/env python3
"""
Tests for Rollback Mechanism
==========================
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.rollback import (
    RollbackManager,
    RollbackPoint,
    RollbackResult,
    get_rollback_manager,
)


class TestRollbackManager:
    """Test rollback manager functionality."""

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess.run for testing."""
        with patch("core.rollback.subprocess.run") as mock_run:
            yield mock_run

    @pytest.fixture
    def tmp_path(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_manager_initialization(self, tmp_path):
        """Test manager initializes correctly."""
        manager = RollbackManager(tmp_path / "test_project")

        assert manager.project_dir == tmp_path / "test_project"

    def test_record_safe_point_success(self, tmp_path, mock_subprocess):
        """Test successful safe point recording."""
        # Mock git commands
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""

            cmd = args[0]

            if "commit" in cmd:
                result.stdout = "[main abc123] commit message"
            elif "rev-parse HEAD" in cmd:
                result.stdout = "abc123def456"

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        commit_hash = manager.record_safe_point("Before merge")

        assert commit_hash == "abc123def456"

    def test_record_safe_point_nothing_to_commit(self, tmp_path, mock_subprocess):
        """Test safe point recording when nothing to commit."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 1
            result.stdout = ""
            result.stderr = "nothing to commit"

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        commit_hash = manager.record_safe_point()

        # Should return None gracefully
        assert commit_hash is None

    def test_get_rollback_points(self, tmp_path, mock_subprocess):
        """Test getting rollback points from reflog."""
        # Mock reflog output
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""

            cmd = " ".join(args[0])

            if "reflog" in cmd:
                result.stdout = """abc123 HEAD@{0}: commit (2024-01-15 10:00:00)
def456 HEAD@{1}: [rollback-safe] Before merge (2024-01-15 09:30:00)
789abc HEAD@{2}: commit (2024-01-15 09:00:00)"""

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        points = manager.get_rollback_points()

        assert len(points) == 3
        assert points[0].is_stable  # Most recent should be safe point
        assert not points[1].is_stable
        assert points[0].commit_hash == "abc123"

    def test_find_latest_safe_point(self, tmp_path, mock_subprocess):
        """Test finding latest safe rollback point."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = """abc123 HEAD@{0}: commit
def456 HEAD@{1}: [rollback-safe] Safe point 1
789abc HEAD@{2}: commit
123456 HEAD@{3}: [rollback-safe] Safe point 2"""

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        safe_commit = manager._find_latest_safe_point()

        assert safe_commit == "def456"  # First safe point (most recent)

    def test_can_rollback(self, tmp_path, mock_subprocess):
        """Test checking if rollback is possible."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = "[rollback-safe] Safe point"

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")

        assert manager.can_rollback() is True

    def test_can_rollback_no_safe_points(self, tmp_path, mock_subprocess):
        """Test can_rollback when no safe points exist."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = "commit\ncommit\ncommit"  # No safe points

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")

        assert manager.can_rollback() is False

    def test_rollback_success(self, tmp_path, mock_subprocess):
        """Test successful rollback."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""

            cmd = " ".join(args[0])

            if "rev-parse HEAD" in cmd:
                result.stdout = "current_commit"
            elif "reflog" in cmd:
                result.stdout = "def456 HEAD@{0}: [rollback-safe] Safe point"
            elif "diff --name-only" in cmd:
                result.stdout = "src/app.py\ntests/test.py"
            elif "reset --hard" in cmd:
                pass

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        result = manager.rollback(create_backup=False)

        assert result.success is True
        assert result.previous_commit == "current_commit"
        assert len(result.files_changed) == 2
        assert result.error is None

    def test_rollback_no_safe_point(self, tmp_path, mock_subprocess):
        """Test rollback when no safe point exists."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = "commit\ncommit"  # No safe points
            result.stderr = ""

            cmd = " ".join(args[0])

            if "rev-parse HEAD" in cmd:
                result.stdout = "abc123"

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        result = manager.rollback()

        assert result.success is False
        assert result.error is not None
        assert "No safe rollback point" in result.error

    def test_rollback_with_backup(self, tmp_path, mock_subprocess):
        """Test rollback with backup creation."""
        commit_sequence = []

        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""

            cmd = " ".join(args[0])

            if "commit" in cmd and "[rollback-safe]" in " ".join(cmd):
                result.stdout = "backup_commit"
                commit_sequence.append("backup")
            elif "rev-parse HEAD" in cmd:
                if len(commit_sequence) == 0:
                    result.stdout = "current_commit"
                else:
                    result.stdout = "rolled_back_commit"
            elif "reflog" in cmd:
                result.stdout = "target123 HEAD@{0}: [rollback-safe] Target"
            elif "diff --name-only" in cmd:
                result.stdout = "file1.py"
            elif "reset --hard" in cmd:
                commit_sequence.append("reset")

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        result = manager.rollback(create_backup=True)

        assert result.success is True
        assert "backup" in commit_sequence  # Backup should be created first

    def test_get_affected_files(self, tmp_path, mock_subprocess):
        """Test getting files affected by rollback."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = ""

            cmd = " ".join(args[0])

            if "rev-parse HEAD" in cmd:
                result.stdout = "abc123"
            elif "diff --name-only" in cmd:
                result.stdout = "src/app.py\nsrc/utils.py\ntests/test.py"

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        files = manager._get_affected_files("target123")

        assert len(files) == 3
        assert "src/app.py" in files
        assert "src/utils.py" in files
        assert "tests/test.py" in files

    def test_cleanup_old_points_analysis(self, tmp_path, mock_subprocess):
        """Test cleanup analysis for old rollback points."""
        def side_effect(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = "commit\n[rollback-safe] safe\ncommit\ncommit"

            return result

        mock_subprocess.side_effect = side_effect

        manager = RollbackManager(tmp_path / "test_project")
        cleaned = manager.cleanup_old_points(max_age_hours=24)

        # Should count non-safe points
        assert cleaned >= 2


class TestRollbackPoint:
    """Test RollbackPoint dataclass."""

    def test_rollback_point_creation(self):
        """Test RollbackPoint creation."""
        point = RollbackPoint(
            commit_hash="abc123",
            timestamp="2024-01-15 10:00:00",
            message="Safe point before merge",
            reflog_index=5,
            is_stable=True,
        )

        assert point.commit_hash == "abc123"
        assert point.is_stable is True
        assert point.reflog_index == 5

    def test_rollback_point_default_stable(self):
        """Test RollbackPoint with default stable flag."""
        point = RollbackPoint(
            commit_hash="abc123",
            timestamp="2024-01-15",
            message="Regular commit",
            reflog_index=0,
        )

        assert point.is_stable is False


class TestRollbackResult:
    """Test RollbackResult dataclass."""

    def test_rollback_result_success(self):
        """Test successful RollbackResult."""
        result = RollbackResult(
            success=True,
            previous_commit="abc123",
            current_commit="def456",
            files_changed=["src/app.py"],
        )

        assert result.success is True
        assert result.previous_commit == "abc123"
        assert result.current_commit == "def456"
        assert len(result.files_changed) == 1
        assert result.error is None

    def test_rollback_result_failure(self):
        """Test failed RollbackResult."""
        result = RollbackResult(
            success=False,
            previous_commit="abc123",
            current_commit="abc123",
            files_changed=[],
            error="No safe rollback point found",
        )

        assert result.success is False
        assert result.error is not None
        assert result.current_commit == result.previous_commit


class TestFactoryFunction:
    """Test factory function."""

    def test_get_rollback_manager(self, tmp_path):
        """Test factory function creates manager."""
        manager = get_rollback_manager(tmp_path / "test_project")

        assert isinstance(manager, RollbackManager)
        assert manager.project_dir == tmp_path / "test_project"
