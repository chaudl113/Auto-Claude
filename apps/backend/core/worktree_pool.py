#!/usr/bin/env python3
"""
Worktree Pool Management
=======================

Maintains a pool of pre-created, clean worktrees for fast startup.
Reduces overhead of git worktree creation.

Benefits:
- Faster worktree allocation (no git clone overhead)
- Reduced I/O operations
- Better resource management

Pool Strategy:
1. Maintain N clean worktrees in pool
2. Allocate from pool when needed
3. Recycle worktrees after use (clean and return to pool)
4. Auto-clean stale/unused worktrees
"""

import asyncio
import logging
import random
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from core.debug import debug, debug_detailed, debug_error, debug_success

logger = logging.getLogger(__name__)


@dataclass
class PooledWorktree:
    """Represents a worktree in the pool."""

    path: Path
    branch: str
    created_at: datetime
    last_used: datetime
    is_available: bool = True
    spec_assigned: Optional[str] = None


class WorktreePool:
    """
    Manages a pool of reusable Git worktrees.

    Usage:
        pool = WorktreePool(project_dir, pool_size=3)
        worktree = await pool.allocate("spec-001")
        # ... use worktree ...
        await pool.release(worktree, clean=True)
    """

    DEFAULT_POOL_SIZE = 3
    MAX_POOL_SIZE = 8
    MAX_IDLE_HOURS = 24
    CLEANUP_CHECK_INTERVAL_HOURS = 6

    def __init__(
        self,
        project_dir: Path,
        pool_size: int = DEFAULT_POOL_SIZE,
        base_branch: str = "main",
    ):
        """
        Initialize worktree pool.

        Args:
            project_dir: Project root directory
            pool_size: Number of worktrees to maintain in pool
            base_branch: Base branch for worktrees
        """
        self.project_dir = Path(project_dir)
        self.base_branch = base_branch
        self.pool_dir = self.project_dir / ".worktree-pool"
        self.pool_dir.mkdir(parents=True, exist_ok=True)

        self.pool: dict[str, PooledWorktree] = {}
        self.pool_size = min(pool_size, self.MAX_POOL_SIZE)
        self._lock = asyncio.Lock()

        # Track metrics
        self.stats = {
            "allocations": 0,
            "releases": 0,
            "pool_hits": 0,
            "pool_misses": 0,
        }

    async def initialize_pool(self) -> int:
        """
        Pre-create worktrees for the pool.

        Returns:
            Number of worktrees created
        """
        current_count = len([w for w in self.pool.values() if w.is_available])

        if current_count >= self.pool_size:
            debug_detailed(
                "worktree_pool",
                "Pool already at capacity",
                count=current_count,
                target=self.pool_size,
            )
            return 0

        needed = self.pool_size - current_count
        created = 0

        debug(
            "worktree_pool",
            "Initializing worktree pool",
            needed=needed,
            target_size=self.pool_size,
        )

        for i in range(needed):
            pool_name = f"pool-{random.randint(10000, 99999)}"
            branch_name = f"auto-claude/{pool_name}"

            try:
                worktree_path = self._create_worktree(pool_name, branch_name)
                if worktree_path:
                    self.pool[pool_name] = PooledWorktree(
                        path=worktree_path,
                        branch=branch_name,
                        created_at=datetime.now(),
                        last_used=datetime.now(),
                        is_available=True,
                    )
                    created += 1
                    debug_success(
                        "worktree_pool",
                        f"Created pool worktree: {pool_name}",
                    )
            except Exception as e:
                logger.error(f"Failed to create pool worktree {pool_name}: {e}")
                debug_error("worktree_pool", "Pool creation failed", error=str(e))

        if created > 0:
            debug_success(
                "worktree_pool",
                f"Pool initialized: {created}/{self.pool_size} worktrees ready",
            )

        return created

    async def allocate(self, spec_name: str) -> Optional[PooledWorktree]:
        """
        Allocate a worktree from pool for a spec.

        Args:
            spec_name: Name of spec needing worktree

        Returns:
            PooledWorktree or None if pool empty
        """
        async with self._lock:
            # Try to get available worktree from pool
            for pool_name, worktree in list(self.pool.items()):
                if worktree.is_available and not worktree.spec_assigned:
                    # Allocate from pool
                    worktree.is_available = False
                    worktree.spec_assigned = spec_name
                    worktree.last_used = datetime.now()

                    self.stats["allocations"] += 1
                    self.stats["pool_hits"] += 1

                    debug_success(
                        "worktree_pool",
                        f"Allocated from pool: {pool_name}",
                        spec=spec_name,
                        pool_hit=True,
                    )
                    return worktree

            # No available worktree in pool - pool miss
            self.stats["allocations"] += 1
            self.stats["pool_misses"] += 1

            debug_detailed(
                "worktree_pool",
                "Pool miss - no available worktrees",
                spec=spec_name,
                pool_hit=False,
            )

            # Optionally create on-demand worktree
            return self._create_on_demand(spec_name)

    async def release(self, worktree: PooledWorktree, clean: bool = True) -> bool:
        """
        Return a worktree to the pool.

        Args:
            worktree: Worktree to release
            clean: Whether to reset worktree (remove changes)

        Returns:
            True if released successfully
        """
        async with self._lock:
            if worktree.spec_assigned not in self.pool:
                debug_detailed(
                    "worktree_pool",
                    "Worktree not in pool",
                    spec=worktree.spec_assigned,
                )
                return False

            # Clean worktree if requested
            if clean and worktree.path.exists():
                try:
                    self._clean_worktree(worktree.path)
                    debug_success(
                        "worktree_pool",
                        f"Cleaned worktree: {worktree.spec_assigned}",
                    )
                except Exception as e:
                    logger.error(f"Failed to clean worktree: {e}")
                    debug_error(
                        "worktree_pool",
                        "Worktree cleanup failed",
                        error=str(e),
                    )

            # Return to pool
            worktree.is_available = True
            worktree.spec_assigned = None
            worktree.last_used = datetime.now()

            self.stats["releases"] += 1

            debug_success(
                "worktree_pool",
                f"Released worktree to pool: {worktree.branch}",
            )
            return True

    def _create_worktree(self, pool_name: str, branch_name: str) -> Optional[Path]:
        """Create a new worktree for the pool."""
        try:
            worktree_path = self.pool_dir / pool_name

            # Remove if exists
            if worktree_path.exists():
                shutil.rmtree(worktree_path)

            # Create worktree
            result = subprocess.run(
                [
                    "git",
                    "worktree",
                    "add",
                    "--force",
                    "--detach",
                    "--checkout",
                    branch_name,
                    str(worktree_path),
                ],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                raise Exception(f"git worktree add failed: {result.stderr}")

            return worktree_path

        except Exception as e:
            logger.error(f"Failed to create worktree: {e}")
            return None

    def _create_on_demand(self, spec_name: str) -> Optional[PooledWorktree]:
        """Create a temporary worktree when pool is empty."""
        try:
            pool_name = f"temp-{spec_name}"
            branch_name = f"auto-claude/temp-{spec_name}"

            worktree_path = self._create_worktree(pool_name, branch_name)
            if not worktree_path:
                return None

            worktree = PooledWorktree(
                path=worktree_path,
                branch=branch_name,
                created_at=datetime.now(),
                last_used=datetime.now(),
                is_available=False,
                spec_assigned=spec_name,
            )

            # Add to pool tracking (not reusable)
            self.pool[pool_name] = worktree

            debug_success(
                "worktree_pool",
                f"Created on-demand worktree for spec: {spec_name}",
            )

            return worktree

        except Exception as e:
            logger.error(f"Failed to create on-demand worktree: {e}")
            return None

    def _clean_worktree(self, worktree_path: Path) -> None:
        """Reset worktree to clean state."""
        # Reset all changes
        subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
        )

        # Remove untracked files
        subprocess.run(
            ["git", "clean", "-fdx"],
            cwd=worktree_path,
            capture_output=True,
        )

    async def cleanup_stale(self, max_age_hours: int = MAX_IDLE_HOURS) -> int:
        """
        Remove stale/unused worktrees from the pool.

        Args:
            max_age_hours: Maximum idle hours before cleanup

        Returns:
            Number of worktrees cleaned up
        """
        now = datetime.now()
        removed = 0

        async with self._lock:
            for pool_name, worktree in list(self.pool.items()):
                age = (now - worktree.last_used).total_seconds() / 3600

                # Skip if recently used or assigned
                if age < max_age_hours or worktree.spec_assigned:
                    continue

                # Remove worktree
                try:
                    self._remove_worktree(worktree.path)
                    del self.pool[pool_name]
                    removed += 1

                    debug_success(
                        "worktree_pool",
                        f"Cleaned up stale worktree: {pool_name}",
                        age_hours=age,
                    )
                except Exception as e:
                    logger.error(f"Failed to remove stale worktree {pool_name}: {e}")

            return removed

    def _remove_worktree(self, worktree_path: Path) -> None:
        """Remove a worktree from git."""
        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path)],
            cwd=self.project_dir,
            capture_output=True,
        )

        if worktree_path.exists():
            shutil.rmtree(worktree_path)

    def get_pool_stats(self) -> dict:
        """Get pool usage statistics."""
        return {
            **self.stats,
            "total_worktrees": len(self.pool),
            "available": len([w for w in self.pool.values() if w.is_available]),
            "assigned": len([w for w in self.pool.values() if w.spec_assigned]),
            "hit_rate": (
                self.stats["pool_hits"] / self.stats["allocations"]
                if self.stats["allocations"] > 0
                else 0
            ),
        }

    async def shutdown(self) -> None:
        """Clean up all worktrees in the pool."""
        debug("worktree_pool", "Shutting down worktree pool")

        for worktree in list(self.pool.values()):
            try:
                self._remove_worktree(worktree.path)
            except Exception as e:
                logger.error(f"Failed to remove worktree: {e}")

        self.pool.clear()


def get_worktree_pool(project_dir: Path, pool_size: int = 3) -> WorktreePool:
    """
    Factory function to get or create worktree pool.

    Args:
        project_dir: Project root directory
        pool_size: Number of worktrees to maintain

    Returns:
        WorktreePool instance
    """
    return WorktreePool(project_dir, pool_size)
