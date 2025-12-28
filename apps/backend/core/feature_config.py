"""Feature configuration for core modules.

This module provides feature flags for enabling/disabling core performance
and safety features. Configuration is read from environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path


class FeatureConfig:
    """Feature flags for core modules.

    All features default to enabled (True) for optimal performance.
    Set environment variables to disable specific features if needed.
    """

    @staticmethod
    def agent_cache_enabled() -> bool:
        """Enable agent state caching for faster session recovery."""
        return os.getenv("AGENT_CACHE_ENABLED", "true").lower() == "true"

    @staticmethod
    def worktree_pool_enabled() -> bool:
        """Enable worktree pooling for faster worktree allocation."""
        return os.getenv("WORKTREE_POOL_ENABLED", "true").lower() == "true"

    @staticmethod
    def worktree_pool_size() -> int:
        """Number of worktrees to keep in the pool."""
        return int(os.getenv("WORKTREE_POOL_SIZE", "3"))

    @staticmethod
    def diff_preview_enabled() -> bool:
        """Enable AI diff preview before merge operations."""
        return os.getenv("DIFF_PREVIEW_ENABLED", "true").lower() == "true"

    @staticmethod
    def rollback_enabled() -> bool:
        """Enable automatic rollback on merge failure."""
        return os.getenv("ROLLBACK_ENABLED", "true").lower() == "true"

    @staticmethod
    def parallel_execution_enabled() -> bool:
        """Enable parallel execution of independent subtasks."""
        return os.getenv("PARALLEL_EXECUTION_ENABLED", "true").lower() == "true"

    @staticmethod
    def max_parallel_tasks() -> int:
        """Maximum number of tasks to run in parallel."""
        return int(os.getenv("MAX_PARALLEL_TASKS", "3"))

    @staticmethod
    def spec_templates_enabled() -> bool:
        """Enable spec template system."""
        return os.getenv("SPEC_TEMPLATES_ENABLED", "true").lower() == "true"

    @staticmethod
    def custom_templates_dir() -> Path:
        """Directory for custom spec templates."""
        default = Path.home() / ".auto-claude" / "templates"
        return Path(os.getenv("CUSTOM_TEMPLATES_DIR", str(default)))

    @classmethod
    def get_all_flags(cls) -> dict[str, bool | int | str]:
        """Get all feature flag values for debugging."""
        return {
            "agent_cache_enabled": cls.agent_cache_enabled(),
            "worktree_pool_enabled": cls.worktree_pool_enabled(),
            "worktree_pool_size": cls.worktree_pool_size(),
            "diff_preview_enabled": cls.diff_preview_enabled(),
            "rollback_enabled": cls.rollback_enabled(),
            "parallel_execution_enabled": cls.parallel_execution_enabled(),
            "max_parallel_tasks": cls.max_parallel_tasks(),
            "spec_templates_enabled": cls.spec_templates_enabled(),
            "custom_templates_dir": str(cls.custom_templates_dir()),
        }

    @classmethod
    def print_status(cls) -> None:
        """Print current feature flag status."""
        flags = cls.get_all_flags()
        print("\n=== Feature Flags ===")
        for name, value in flags.items():
            status = "✅" if value is True else ("❌" if value is False else "")
            print(f"  {status} {name}: {value}")
        print()
