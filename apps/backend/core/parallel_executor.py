#!/usr/bin/env python3
"""
Smart Parallel Execution
=======================

Automatically detects dependencies between subtasks and orchestrates
parallel agent execution for faster completion.

Benefits:
- Faster completion by running independent tasks in parallel
- Better resource utilization
- Dependency-aware scheduling

Algorithm:
1. Parse subtasks to extract file dependencies
2. Build dependency graph
3. Find topological groups (independent sets)
4. Schedule parallel execution for independent groups
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Optional

import sys
from pathlib import Path

# Import debug module directly from file to avoid circular import
sys.path.insert(0, str(Path(__file__).parent))
import debug

logger = logging.getLogger(__name__)


@dataclass
class SubtaskDependency:
    """Represents a dependency between subtasks."""

    subtask_id: str
    depends_on: List[str]  # Subtask IDs this one depends on
    files_touched: List[str]  # Files this subtask modifies/reads


@dataclass
class ParallelGroup:
    """Group of subtasks that can run in parallel."""

    group_id: int
    subtask_ids: List[str]
    can_run_in_parallel: bool


class DependencyAnalyzer:
    """
    Analyzes subtask dependencies to enable parallel execution.
    """

    def __init__(self, spec_dir: Path):
        """
        Initialize dependency analyzer.

        Args:
            spec_dir: Spec directory containing implementation_plan.json
        """
        self.spec_dir = Path(spec_dir)
        self.plan_file = spec_dir / "implementation_plan.json"

    def analyze_dependencies(
        self, subtasks: List[dict]
    ) -> Dict[str, SubtaskDependency]:
        """
        Analyze dependencies between subtasks.

        Args:
            subtasks: List of subtask dictionaries from implementation plan

        Returns:
            Dictionary mapping subtask_id -> SubtaskDependency
        """
        debug_detailed(
            "parallel_execution",
            "Analyzing subtask dependencies",
            subtask_count=len(subtasks),
        )

        # Build file -> subtasks mapping
        file_to_subtasks: Dict[str, List[str]] = defaultdict(list)
        subtask_to_files: Dict[str, List[str]] = {}

        for subtask in subtasks:
            subtask_id = subtask.get("id")
            files = []
            
            # Files to modify
            if "files_to_modify" in subtask:
                files.extend(subtask["files_to_modify"])
                for f in subtask["files_to_modify"]:
                    file_to_subtasks[f].append(subtask_id)
            
            # Files to create
            if "files_to_create" in subtask:
                files.extend(subtask["files_to_create"])
                for f in subtask["files_to_create"]:
                    file_to_subtasks[f].append(subtask_id)
            
            subtask_to_files[subtask_id] = files

        # Build dependencies
        dependencies: Dict[str, SubtaskDependency] = {}
        
        for subtask_id, files_touched in subtask_to_files.items():
            depends_on: List[str] = []
            
            # Find subtasks that touch files this subtask needs
            for file in files_touched:
                if file in file_to_subtasks:
                    # This subtask depends on other subtasks that touch same files
                    for other_id in file_to_subtasks[file]:
                        if other_id != subtask_id:
                            depends_on.append(other_id)
            
            dependencies[subtask_id] = SubtaskDependency(
                subtask_id=subtask_id,
                depends_on=depends_on,
                files_touched=files_touched,
            )
        
        # Log dependency graph
        for subtask_id, dep in dependencies.items():
            if dep.depends_on:
                debug_detailed(
                    "parallel_execution",
                    f"Subtask {subtask_id} depends on: {dep.depends_on}",
                    dependency_count=len(dep.depends_on),
                )
        
        return dependencies

    def find_parallel_groups(
        self, dependencies: Dict[str, SubtaskDependency]
    ) -> List[ParallelGroup]:
        """
        Find groups of subtasks that can run in parallel.

        Args:
            dependencies: Dependency mapping from analyze_dependencies()

        Returns:
            List of ParallelGroups ordered by execution order
        """
        if not dependencies:
            debug_detailed("parallel_execution", "No dependencies to analyze")
            return []
        
        debug(
            "parallel_execution",
            "Finding parallel execution groups",
            total_subtasks=len(dependencies),
        )
        
        # Build topological order
        groups: List[ParallelGroup] = []
        remaining: Set[str] = set(dependencies.keys())
        processed: Set[str] = set()
        group_id = 0
        
        while remaining:
            # Find subtasks with no unmet dependencies
            ready_to_run: List[str] = []
            
            for subtask_id in remaining:
                if subtask_id in processed:
                    continue
                
                dep = dependencies[subtask_id]
                
                # Check if all dependencies are satisfied
                unmet_deps = [
                    d for d in dep.depends_on
                    if d not in processed
                ]
                
                if not unmet_deps:
                    ready_to_run.append(subtask_id)
            
            if not ready_to_run:
                # Circular dependency detected
                debug_error(
                    "parallel_execution",
                    "Circular dependency detected, breaking cycle",
                )
                # Pick any remaining subtask to break cycle
                ready_to_run = [next(iter(remaining))]
            
            if ready_to_run:
                group = ParallelGroup(
                    group_id=group_id,
                    subtask_ids=ready_to_run,
                    can_run_in_parallel=len(ready_to_run) > 1,
                )
                groups.append(group)
                
                # Mark as processed
                processed.update(ready_to_run)
                remaining -= set(ready_to_run)
                
                debug_success(
                    "parallel_execution",
                    f"Group {group_id}: {len(ready_to_run)} subtasks ready",
                    can_run_parallel=group.can_run_in_parallel,
                )
                
                group_id += 1
        
        debug_success(
            "parallel_execution",
            f"Found {len(groups)} parallel groups",
            parallel_groups=sum(1 for g in groups if g.can_run_in_parallel),
            sequential_groups=sum(1 for g in groups if not g.can_run_in_parallel),
        )
        
        return groups

    def get_execution_plan(
        self, dependencies: Dict[str, SubtaskDependency]
    ) -> dict:
        """
        Generate execution plan with parallel and sequential recommendations.

        Returns:
            Dictionary with parallel strategy recommendations
        """
        groups = self.find_parallel_groups(dependencies)
        
        parallel_count = sum(1 for g in groups if g.can_run_in_parallel)
        sequential_count = sum(1 for g in groups if not g.can_run_in_parallel)
        
        return {
            "groups": groups,
            "parallel_subtasks": parallel_count,
            "sequential_subtasks": sequential_count,
            "total_groups": len(groups),
            "speedup_potential": min(parallel_count, 1),  # At minimum, 2x speedup for 2 parallel tasks
        }


class ParallelExecutor:
    """
    Orchestrates parallel execution of subtasks.
    """

    def __init__(self, spec_dir: Path, max_parallel: int = 3):
        """
        Initialize parallel executor.

        Args:
            spec_dir: Spec directory
            max_parallel: Maximum concurrent agent sessions
        """
        self.spec_dir = Path(spec_dir)
        self.analyzer = DependencyAnalyzer(spec_dir)
        self.max_parallel = max_parallel
        self._active_tasks: Dict[str, asyncio.Task] = {}

    async def execute_parallel_groups(
        self, groups: List[ParallelGroup], execute_subtask_func
    ) -> Dict[str, str]:
        """
        Execute subtasks in parallel according to groups.

        Args:
            groups: Parallel groups to execute
            execute_subtask_func: Async function to execute a subtask

        Returns:
            Dictionary of subtask_id -> status/result
        """
        results: Dict[str, str] = {}
        
        debug(
            "parallel_executor",
            "Starting parallel execution",
            groups_count=len(groups),
            max_concurrent=self.max_parallel,
        )
        
        for group in groups:
            if group.can_run_in_parallel:
                # Execute group in parallel
                debug_success(
                    "parallel_executor",
                    f"Executing group {group.group_id} in parallel {len(group.subtask_ids)} subtasks",
                )
                
                tasks = []
                for subtask_id in group.subtask_ids:
                    task = asyncio.create_task(
                        execute_subtask_func(subtask_id),
                        name=f"subtask-{subtask_id}"
                    )
                    tasks.append(task)
                    self._active_tasks[subtask_id] = task
                
                # Wait for group completion (with limit on concurrent tasks)
                batch = tasks[:self.max_parallel]
                if batch:
                    await asyncio.gather(*batch, return_exceptions=True)
                
                # Process remaining tasks if batch size exceeded max_parallel
                remaining_tasks = tasks[self.max_parallel:]
                for task in remaining_tasks:
                    await task
                
            else:
                # Execute sequentially
                debug_detailed(
                    "parallel_executor",
                    f"Executing group {group.group_id} sequentially",
                )
                
                for subtask_id in group.subtask_ids:
                    try:
                        result = await execute_subtask_func(subtask_id)
                        results[subtask_id] = result
                    except Exception as e:
                        logger.error(f"Subtask {subtask_id} failed: {e}")
                        results[subtask_id] = f"error: {e}"
        
        # Clean up completed tasks
        self._active_tasks.clear()
        
        debug_success(
            "parallel_executor",
            f"Parallel execution completed",
            total_completed=len(results),
        )
        
        return results


def get_dependency_analyzer(spec_dir: Path) -> DependencyAnalyzer:
    """Factory function to get DependencyAnalyzer instance."""
    return DependencyAnalyzer(spec_dir)
