#!/usr/bin/env python3
"""
Tests for Worktree Pooling
==========================
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.worktree_pool import WorktreePool, PooledWorktree


class TestWorktreePool:
    """Test worktree pool management."""

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess.run for testing."""
        with patch("core.worktree_pool.subprocess.run") as mock_run:
            yield mock_run

    @pytest.fixture
    def tmp_pool(self, tmp_path):
        """Create a test worktree pool."""
        pool = WorktreePool(tmp_path / "test_project", pool_size=2)
        yield pool
        # Cleanup
        # (real pool would call shutdown, but tests manage their own lifecycle)

    @pytest.fixture
    def tmp_path(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_pool_initialization(self, tmp_path):
        """Test pool creates required directories."""
        pool = WorktreePool(tmp_path / "test_project")

        assert pool.pool_dir.exists()
        assert pool.pool_dir == tmp_path / "test_project" / ".worktree-pool"
        assert pool.pool_size == 3

    def test_default_pool_size(self, tmp_path):
        """Test default pool size."""
        pool = WorktreePool(tmp_path / "test_project")
        assert pool.pool_size == WorktreePool.DEFAULT_POOL_SIZE

    def test_max_pool_size_cap(self, tmp_path):
        """Test pool size is capped at MAX_POOL_SIZE."""
        pool = WorktreePool(tmp_path / "test_project", pool_size=20)
        assert pool.pool_size == WorktreePool.MAX_POOL_SIZE

    def test_pool_initialization_creates_worktrees(self, tmp_pool, mock_subprocess):
        """Test pool creates worktrees on initialization."""
        # Mock successful git worktree creation
        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

        import asyncio
        created = asyncio.run(tmp_pool.initialize_pool())

        assert created == 2  # pool_size - 0 existing
        assert len(tmp_pool.pool) == 2

    def test_allocate_from_pool(self, tmp_pool):
        """Test allocating worktree from pool."""
        # Create mock worktrees
        worktree1 = PooledWorktree(
            path=Path("/pool1"),
            branch="branch1",
            created_at=datetime.now(),
            last_used=datetime.now(),
        )
        worktree2 = PooledWorktree(
            path=Path("/pool2"),
            branch="branch2",
            created_at=datetime.now(),
            last_used=datetime.now(),
        )

        tmp_pool.pool["wt1"] = worktree1
        tmp_pool.pool["wt2"] = worktree2

        # Allocate
        allocated = tmp_pool.allocate("spec-001")

        assert allocated is not None
        assert not allocated.is_available
        assert allocated.spec_assigned == "spec-001"
        assert tmp_pool.stats["pool_hits"] == 1

    def test_pool_miss(self, tmp_pool):
        """Test pool miss when no available worktrees."""
        # All worktrees assigned
        worktree = PooledWorktree(
            path=Path("/pool1"),
            branch="branch1",
            created_at=datetime.now(),
            last_used=datetime.now(),
            is_available=False,
            spec_assigned="spec-other",
        )
        tmp_pool.pool["wt1"] = worktree

        # Try to allocate
        allocated = tmp_pool.allocate("spec-001")

        # Should create on-demand (or return None if mocked)
        assert tmp_pool.stats["pool_misses"] == 1

    def test_release_worktree(self, tmp_pool):
        """Test releasing worktree back to pool."""
        worktree = PooledWorktree(
            path=Path("/pool1"),
            branch="branch1",
            created_at=datetime.now(),
            last_used=datetime.now(),
            is_available=False,
            spec_assigned="spec-001",
        )
        tmp_pool.pool["wt1"] = worktree

        # Release
        import asyncio
        released = asyncio.run(tmp_pool.release(worktree, clean=False))

        assert released is True
        assert worktree.is_available
        assert worktree.spec_assigned is None
        assert tmp_pool.stats["releases"] == 1

    def test_release_clean_worktree(self, tmp_pool, mock_subprocess):
        """Test releasing worktree cleans it."""
        worktree = PooledWorktree(
            path=Path("/pool1"),
            branch="branch1",
            created_at=datetime.now(),
            last_used=datetime.now(),
            is_available=False,
            spec_assigned="spec-001",
        )
        tmp_pool.pool["wt1"] = worktree

        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

        # Release with cleaning
        import asyncio
        released = asyncio.run(tmp_pool.release(worktree, clean=True))

        assert released is True
        # Should have called git reset and clean
        assert mock_subprocess.call_count >= 2

    def test_cleanup_stale_worktrees(self, tmp_pool):
        """Test cleanup of old worktrees."""
        import datetime
        now = datetime.datetime.now()

        # Create old worktree
        old_worktree = PooledWorktree(
            path=Path("/old"),
            branch="old-branch",
            created_at=now,
            last_used=now - datetime.timedelta(hours=48),  # 2 days ago
            is_available=True,
        )
        tmp_pool.pool["old"] = old_worktree

        # Create recent worktree
        recent_worktree = PooledWorktree(
            path=Path("/recent"),
            branch="recent-branch",
            created_at=now,
            last_used=now - datetime.timedelta(hours=1),
            is_available=True,
        )
        tmp_pool.pool["recent"] = recent_worktree

        # Cleanup
        import asyncio
        removed = asyncio.run(tmp_pool.cleanup_stale(max_age_hours=24))

        assert removed == 1
        assert "old" not in tmp_pool.pool
        assert "recent" in tmp_pool.pool

    def test_get_pool_stats(self, tmp_pool):
        """Test pool statistics."""
        # Add mock worktrees
        tmp_pool.stats = {
            "allocations": 10,
            "releases": 8,
            "pool_hits": 7,
            "pool_misses": 3,
        }
        tmp_pool.pool["wt1"] = PooledWorktree(
            path=Path("/1"),
            branch="b1",
            created_at=datetime.now(),
            last_used=datetime.now(),
            is_available=True,
        )
        tmp_pool.pool["wt2"] = PooledWorktree(
            path=Path("/2"),
            branch="b2",
            created_at=datetime.now(),
            last_used=datetime.now(),
            is_available=False,
            spec_assigned="spec-1",
        )

        stats = tmp_pool.get_pool_stats()

        assert stats["allocations"] == 10
        assert stats["releases"] == 8
        assert stats["total_worktrees"] == 2
        assert stats["available"] == 1
        assert stats["assigned"] == 1
        assert stats["hit_rate"] == 0.7

    def test_shutdown(self, tmp_pool, mock_subprocess):
        """Test pool shutdown removes all worktrees."""
        tmp_pool.pool["wt1"] = PooledWorktree(
            path=Path("/1"),
            branch="b1",
            created_at=datetime.now(),
            last_used=datetime.now(),
        )
        tmp_pool.pool["wt2"] = PooledWorktree(
            path=Path("/2"),
            branch="b2",
            created_at=datetime.now(),
            last_used=datetime.now(),
        )

        mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")

        # Shutdown
        import asyncio
        asyncio.run(tmp_pool.shutdown())

        assert len(tmp_pool.pool) == 0
        # Should call git worktree remove twice
        assert mock_subprocess.call_count >= 2
