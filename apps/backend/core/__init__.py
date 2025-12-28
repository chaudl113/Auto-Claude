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
from .diff_preview import (
    DiffPreview,
    DiffPreviewGenerator,
    FileChange,
    get_diff_preview_generator,
)
from .feature_config import FeatureConfig
from .parallel_executor import (
    DependencyAnalyzer,
    ParallelExecutor,
    SubtaskDependency,
    ParallelGroup,
    get_dependency_analyzer,
)
from .progress import count_subtasks, is_build_complete
from .rollback import (
    RollbackManager,
    RollbackPoint,
    RollbackResult,
    get_rollback_manager,
)
from .spec_template import (
    SpecTemplate,
    SpecTemplateManager,
    get_template_manager,
)
from .worktree import WorktreeManager
from .worktree_pool import WorktreePool, get_worktree_pool, PooledWorktree
from .workspace.models import WorkspaceMode

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
    "DependencyAnalyzer",
    "ParallelExecutor",
    "SubtaskDependency",
    "ParallelGroup",
    "get_dependency_analyzer",
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
    "WorkspaceMode",
    "get_status_manager",
    # Priority 2 features
    "DiffPreview",
    "DiffPreviewGenerator",
    "FileChange",
    "get_diff_preview_generator",
    "RollbackManager",
    "RollbackPoint",
    "RollbackResult",
    "get_rollback_manager",
    "SpecTemplate",
    "SpecTemplateManager",
    "get_template_manager",
    # Feature configuration
    "FeatureConfig",
]
