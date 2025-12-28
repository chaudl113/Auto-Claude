# Core Module Integration Plan

## Overview

This plan integrates 6 implemented but unused core modules into the active workflow.

**Modules to integrate:**
1. Agent State Caching (`core/agent_cache.py`)
2. Worktree Pooling (`core/worktree_pool.py`)
3. AI Diff Preview (`core/diff_preview.py`)
4. Rollback Mechanism (`core/rollback.py`)
5. Parallel Executor (`core/parallel_executor.py`)
6. Spec Template System (`core/spec_template.py`)

---

## Phase 1: Configuration & Feature Flags

### 1.1 Add .env options

**File:** `apps/backend/.env.example`

```env
# === Performance Features ===
AGENT_CACHE_ENABLED=true
WORKTREE_POOL_ENABLED=true
WORKTREE_POOL_SIZE=3

# === Merge Safety Features ===
DIFF_PREVIEW_ENABLED=true
ROLLBACK_ENABLED=true

# === Parallel Execution ===
PARALLEL_EXECUTION_ENABLED=true
MAX_PARALLEL_TASKS=3

# === Spec Templates ===
SPEC_TEMPLATES_ENABLED=true
CUSTOM_TEMPLATES_DIR=~/.auto-claude/templates
```

### 1.2 Create Feature Config Module

**File:** `apps/backend/core/feature_config.py`

```python
import os
from pathlib import Path

class FeatureConfig:
    """Feature flags for core modules."""
    
    @staticmethod
    def agent_cache_enabled() -> bool:
        return os.getenv("AGENT_CACHE_ENABLED", "true").lower() == "true"
    
    @staticmethod
    def worktree_pool_enabled() -> bool:
        return os.getenv("WORKTREE_POOL_ENABLED", "true").lower() == "true"
    
    @staticmethod
    def worktree_pool_size() -> int:
        return int(os.getenv("WORKTREE_POOL_SIZE", "3"))
    
    @staticmethod
    def diff_preview_enabled() -> bool:
        return os.getenv("DIFF_PREVIEW_ENABLED", "true").lower() == "true"
    
    @staticmethod
    def rollback_enabled() -> bool:
        return os.getenv("ROLLBACK_ENABLED", "true").lower() == "true"
    
    @staticmethod
    def parallel_execution_enabled() -> bool:
        return os.getenv("PARALLEL_EXECUTION_ENABLED", "true").lower() == "true"
    
    @staticmethod
    def max_parallel_tasks() -> int:
        return int(os.getenv("MAX_PARALLEL_TASKS", "3"))
    
    @staticmethod
    def spec_templates_enabled() -> bool:
        return os.getenv("SPEC_TEMPLATES_ENABLED", "true").lower() == "true"
    
    @staticmethod
    def custom_templates_dir() -> Path:
        default = Path.home() / ".auto-claude" / "templates"
        return Path(os.getenv("CUSTOM_TEMPLATES_DIR", str(default)))
```

---

## Phase 2: Agent State Caching Integration

### Target File: `apps/backend/spec/pipeline/agent_runner.py`

### Changes:

```python
from core.agent_cache import get_agent_cache
from core.feature_config import FeatureConfig

class AgentRunner:
    def __init__(self, spec_dir: Path, ...):
        self.spec_dir = spec_dir
        self.cache = get_agent_cache(spec_dir) if FeatureConfig.agent_cache_enabled() else None
    
    async def run_agent(self, message: str, ...):
        # Check for cached state
        if self.cache:
            cached_state = self.cache.load_state()
            if cached_state:
                resume_prompt = self.cache.get_resume_prompt()
                message = f"{resume_prompt}\n\n{message}"
        
        # Run agent session
        result = await self._execute_agent(message, ...)
        
        # Save state periodically
        if self.cache and result.messages:
            self.cache.save_state(
                session_id=self.session_id,
                messages=result.messages,
                context={"task": message, "phase": self.current_phase},
                file_state=self._get_file_state()
            )
        
        # Invalidate on completion
        if self.cache and result.status == "complete":
            self.cache.invalidate()
        
        return result
```

---

## Phase 3: Worktree Pooling Integration

### Target File: `apps/backend/core/worktree.py`

### Changes:

```python
from core.worktree_pool import get_worktree_pool, PooledWorktree
from core.feature_config import FeatureConfig

class WorktreeManager:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self._pool = None
        if FeatureConfig.worktree_pool_enabled():
            self._pool = get_worktree_pool(
                project_dir, 
                pool_size=FeatureConfig.worktree_pool_size()
            )
    
    async def initialize_pool(self):
        """Pre-populate worktree pool."""
        if self._pool:
            await self._pool.initialize_pool()
    
    async def create_worktree(self, spec_name: str, base_branch: str = "main") -> Path:
        """Create or allocate worktree."""
        # Try pool first
        if self._pool:
            worktree = await self._pool.allocate(spec_name)
            if worktree:
                return worktree.path
        
        # Fallback to traditional creation
        return self._create_worktree_sync(spec_name, base_branch)
    
    async def release_worktree(self, worktree_path: Path, clean: bool = True):
        """Release worktree back to pool or delete."""
        if self._pool:
            # Find pooled worktree and release
            await self._pool.release_by_path(worktree_path, clean=clean)
        else:
            self._delete_worktree_sync(worktree_path)
```

---

## Phase 4: Diff Preview + Rollback Integration

### Target File: `apps/backend/core/workspace.py`

### Changes to `merge_existing_build()`:

```python
from core.diff_preview import get_diff_preview_generator
from core.rollback import get_rollback_manager
from core.feature_config import FeatureConfig

async def merge_existing_build(
    project_dir: Path,
    spec_name: str,
    base_branch: str = "main",
    preview: bool = None,
    auto_rollback: bool = None
) -> dict:
    """Merge with optional diff preview and rollback support."""
    
    # Use config defaults if not specified
    preview = preview if preview is not None else FeatureConfig.diff_preview_enabled()
    auto_rollback = auto_rollback if auto_rollback is not None else FeatureConfig.rollback_enabled()
    
    # Step 1: Show diff preview if enabled
    if preview:
        generator = get_diff_preview_generator(project_dir)
        diff_preview = generator.generate_preview(spec_name, base_branch)
        generator.display_preview(diff_preview)
        
        # Get approval (for CLI - UI handles this differently)
        if not await generator.prompt_approval(diff_preview):
            return {"success": False, "reason": "User cancelled merge"}
    
    # Step 2: Record safe point before merge if rollback enabled
    rollback_manager = None
    if auto_rollback:
        rollback_manager = get_rollback_manager(project_dir)
        safe_point = rollback_manager.record_safe_point(f"Before merge: {spec_name}")
    
    # Step 3: Perform merge
    try:
        result = await _perform_merge(project_dir, spec_name, base_branch)
        return result
    except Exception as e:
        # Step 4: Offer rollback on failure
        if rollback_manager and rollback_manager.can_rollback():
            print(f"\n⚠️ Merge failed: {e}")
            print("Rolling back to safe point...")
            rollback_result = rollback_manager.rollback(create_backup=True)
            if rollback_result.success:
                print(f"✅ Rolled back to {rollback_result.current_commit[:8]}")
            return {"success": False, "rolled_back": True, "error": str(e)}
        raise
```

---

## Phase 5: CLI Flag Integration

### Target File: `apps/backend/run.py`

### Add CLI arguments:

```python
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Auto Claude Build Runner")
    
    # Existing args...
    parser.add_argument("--spec", type=str, help="Spec ID to run")
    parser.add_argument("--merge", action="store_true", help="Merge completed build")
    parser.add_argument("--review", action="store_true", help="Review changes")
    
    # New feature flags
    parser.add_argument("--enable-cache", action="store_true", 
                        help="Enable agent state caching")
    parser.add_argument("--disable-cache", action="store_true",
                        help="Disable agent state caching")
    parser.add_argument("--enable-pool", action="store_true",
                        help="Enable worktree pooling")
    parser.add_argument("--preview-diff", action="store_true",
                        help="Show diff preview before merge")
    parser.add_argument("--no-rollback", action="store_true",
                        help="Disable auto-rollback on merge failure")
    parser.add_argument("--parallel", type=int, default=None,
                        help="Max parallel tasks (0 to disable)")
    parser.add_argument("--template", type=str,
                        help="Create spec from template ID")
    
    return parser.parse_args()
```

---

## Phase 6: Parallel Executor Integration

### Target File: `apps/backend/spec/pipeline/orchestrator.py`

### Changes:

```python
from core.parallel_executor import DependencyAnalyzer, ParallelExecutor
from core.feature_config import FeatureConfig

class SpecOrchestrator:
    async def run_build(self, spec_dir: Path):
        plan = self._load_implementation_plan(spec_dir)
        
        if FeatureConfig.parallel_execution_enabled():
            return await self._run_parallel(plan, spec_dir)
        else:
            return await self._run_sequential(plan, spec_dir)
    
    async def _run_parallel(self, plan, spec_dir: Path):
        """Run subtasks in parallel where possible."""
        subtasks = [s for p in plan.phases for s in p.subtasks]
        
        # Analyze dependencies
        analyzer = DependencyAnalyzer(spec_dir)
        dependencies = analyzer.analyze_dependencies(subtasks)
        groups = analyzer.find_parallel_groups(dependencies)
        
        # Execute parallel groups
        executor = ParallelExecutor(
            spec_dir, 
            max_parallel=FeatureConfig.max_parallel_tasks()
        )
        return await executor.execute_parallel_groups(groups, self._execute_subtask)
```

---

## Phase 7: Spec Template UI Integration

### Target File: `apps/frontend/src/renderer/components/TaskCreationWizard.tsx`

### Add template selection step:

```tsx
// Add template selector component
import { SpecTemplateSelector } from './SpecTemplateSelector';

// In wizard steps
const steps = [
  { id: 'template', title: 'Choose Template (Optional)' },
  { id: 'description', title: 'Task Description' },
  // ... existing steps
];

// Template step component
{currentStep === 'template' && (
  <SpecTemplateSelector
    onSelect={(template) => setSelectedTemplate(template)}
    onSkip={() => nextStep()}
  />
)}
```

---

## Implementation Order

| Priority | Task | Estimated Time | Dependencies |
|----------|------|----------------|--------------|
| 1 | Create feature_config.py | 15 min | None |
| 2 | Update .env.example | 5 min | None |
| 3 | Integrate Agent Cache | 30 min | feature_config |
| 4 | Integrate Worktree Pool | 45 min | feature_config |
| 5 | Integrate Diff Preview + Rollback | 1 hour | feature_config |
| 6 | Add CLI flags | 30 min | All integrations |
| 7 | Integrate Parallel Executor | 45 min | feature_config |
| 8 | Add Spec Template UI | 1 hour | Backend templates |

**Total Estimated Time:** ~5 hours

---

## Testing Plan

```bash
# Run all core module tests
python -m pytest tests/test_agent_cache.py -v
python -m pytest tests/test_worktree_pool.py -v
python -m pytest tests/test_diff_preview.py -v
python -m pytest tests/test_rollback.py -v
python -m pytest tests/test_parallel_executor.py -v
python -m pytest tests/test_spec_template.py -v

# Integration test
python run.py --spec test --enable-cache --enable-pool --preview-diff
```

---

## Rollout Strategy

1. **Phase 1:** Feature flags default to `false` (opt-in)
2. **Phase 2:** After testing, change defaults to `true`
3. **Phase 3:** Add UI controls in Settings
4. **Phase 4:** Remove feature flags (always on)
