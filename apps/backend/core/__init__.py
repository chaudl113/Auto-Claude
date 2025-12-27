"""
Core Module
============

Central infrastructure for Auto Claude framework.
"""

from .agent_cache import AgentStateCache, get_agent_cache
from .client import create_client
from .debug import (
    debug,
    debug_detailed,
    debug_error,
    debug_info,
    debug_section,
    debug_success,
    debug_timer,
    debug_async_timer,
    is_debug_enabled,
    get_debug_level,
)
from .progress import count_subtasks, is_build_complete
from .worktree import WorktreeManager
from .worktree_pool import WorktreePool, get_worktree_pool, PooledWorktree

# StatusManager is imported from ui module
# This is a re-export for backwards compatibility
def get_status_manager(project_dir):
    """Get StatusManager instance (imported from ui module)."""
    from ui.status import StatusManager
    return StatusManager(project_dir)

__all__ = [
    "create_client",
    "AgentStateCache",
    "get_agent_cache",
    "WorktreePool",
    "get_worktree_pool",
    "PooledWorktree",
    "debug",
    "debug_detailed",
    "debug_error",
    "debug_info",
    "debug_section",
    "debug_success",
    "debug_timer",
    "debug_async_timer",
    "is_debug_enabled",
    "get_debug_level",
    "count_subtasks",
    "is_build_complete",
    "WorktreeManager",
    "get_status_manager",
]
