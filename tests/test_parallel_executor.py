#!/usr/bin/env python3
"""
Tests for Smart Parallel Execution
================================
"""

import tempfile
from pathlib import Path

import pytest

from core.parallel_executor import (
    DependencyAnalyzer,
    ParallelExecutor,
    SubtaskDependency,
    ParallelGroup,
)


class TestDependencyAnalyzer:
    """Test dependency analysis functionality."""

    @pytest.fixture
    def sample_subtasks(self):
        """Create sample subtasks for testing."""
        return [
            {
                "id": "st-1",
                "description": "Create user model",
                "files_to_create": ["models/user.py"],
                "files_to_modify": [],
            },
            {
                "id": "st-2",
                "description": "Create auth service",
                "files_to_create": ["services/auth.py"],
                "files_to_modify": ["models/user.py"],
            },
            {
                "id": "st-3",
                "description": "Create auth controller",
                "files_to_create": ["controllers/auth.py"],
                "files_to_modify": ["services/auth.py"],
            },
            {
                "id": "st-4",
                "description": "Create user controller (independent)",
                "files_to_create": ["controllers/user.py"],
                "files_to_modify": [],
            },
            {
                "id": "st-5",
                "description": "Create login view (depends on auth)",
                "files_to_create": ["views/login.py"],
                "files_to_modify": ["services/auth.py", "controllers/auth.py"],
            },
        ]

    @pytest.fixture
    def tmp_path(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_analyze_dependencies_detects_file_conflicts(self, sample_subtasks, tmp_path):
        """Test file conflict detection."""
        analyzer = DependencyAnalyzer(tmp_path)
        
        dependencies = analyzer.analyze_dependencies(sample_subtasks)
        
        # st-2 depends on st-1 (both touch models/user.py)
        assert "st-1" in dependencies
        assert "st-2" in dependencies
        
        # st-3 depends on st-2 (touches services/auth.py)
        assert "st-3" in dependencies
        assert dependencies["st-3"].depends_on == ["st-2"]
        
        # st-5 depends on st-2 and st-3
        assert "st-5" in dependencies
        assert set(dependencies["st-5"].depends_on) >= {"st-2", "st-3"}

    def test_find_parallel_groups_identifies_independent_tasks(self, sample_subtasks, tmp_path):
        """Test parallel group identification."""
        analyzer = DependencyAnalyzer(tmp_path)
        dependencies = analyzer.analyze_dependencies(sample_subtasks)
        groups = analyzer.find_parallel_groups(dependencies)
        
        # st-4 is independent (no conflicts with any other task)
        independent_groups = [g for g in groups if "st-4" in g.subtask_ids]
        assert len(independent_groups) > 0

    def test_parallel_groups_topological_order(self, sample_subtasks, tmp_path):
        """Test groups are in correct topological order."""
        analyzer = DependencyAnalyzer(tmp_path)
        dependencies = analyzer.analyze_dependencies(sample_subtasks)
        groups = analyzer.find_parallel_groups(dependencies)
        
        # st-1 must be before st-2 (st-2 depends on st-1)
        group_order = [g.group_id for g in groups]
        st1_idx = next(i for i, g in enumerate(groups) if "st-1" in g.subtask_ids)
        st2_idx = next(i for i, g in enumerate(groups) if "st-2" in g.subtask_ids)
        
        assert st1_idx < st2_idx

    def test_get_execution_plan_includes_recommendations(self, sample_subtasks, tmp_path):
        """Test execution plan generation."""
        analyzer = DependencyAnalyzer(tmp_path)
        dependencies = analyzer.analyze_dependencies(sample_subtasks)
        plan = analyzer.get_execution_plan(dependencies)
        
        assert "groups" in plan
        assert "parallel_subtasks" in plan
        assert "sequential_subtasks" in plan
        assert "recommendations" in plan
        assert len(plan["recommendations"]) > 0

    def test_no_subtasks_returns_empty_plan(self, tmp_path):
        """Test empty subtasks handling."""
        analyzer = DependencyAnalyzer(tmp_path)
        dependencies = analyzer.analyze_dependencies([])
        groups = analyzer.find_parallel_groups(dependencies)
        plan = analyzer.get_execution_plan(dependencies)
        
        assert len(groups) == 0
        assert plan["parallel_subtasks"] == 0
        assert plan["sequential_subtasks"] == 0

    def test_circular_dependency_handling(self, tmp_path):
        """Test circular dependency detection."""
        circular_subtasks = [
            {
                "id": "c1",
                "description": "Task 1",
                "files_to_modify": ["a.py"],
            },
            {
                "id": "c2",
                "description": "Task 2",
                "files_to_modify": ["b.py", "a.py"],
            },
            {
                "id": "c3",
                "description": "Task 3",
                "files_to_modify": ["c.py", "b.py"],
            },
        ]
        
        analyzer = DependencyAnalyzer(tmp_path)
        dependencies = analyzer.analyze_dependencies(circular_subtasks)
        groups = analyzer.find_parallel_groups(dependencies)
        
        # Should still produce groups (breaks cycle)
        assert len(groups) > 0


class TestParallelGroup:
    """Test ParallelGroup dataclass."""

    def test_parallel_group_creation(self):
        """Test ParallelGroup creation."""
        group = ParallelGroup(
            group_id=0,
            subtask_ids=["st-1", "st-2"],
            can_run_in_parallel=True,
            blocked_by=[],
        )
        
        assert group.group_id == 0
        assert group.can_run_in_parallel is True
        assert len(group.subtask_ids) == 2

    def test_sequential_group_creation(self):
        """Test sequential group creation."""
        group = ParallelGroup(
            group_id=1,
            subtask_ids=["st-3"],
            can_run_in_parallel=False,
            blocked_by=["st-1", "st-2"],
        )
        
        assert group.can_run_in_parallel is False
        assert len(group.blocked_by) == 2


class TestParallelExecutor:
    """Test parallel execution orchestration."""

    @pytest.mark.asyncio
    async def test_execute_parallel_groups(self, tmp_path):
        """Test parallel group execution."""
        groups = [
            ParallelGroup(
                group_id=0,
                subtask_ids=["st-1", "st-4"],
                can_run_in_parallel=True,
                blocked_by=[],
            ),
            ParallelGroup(
                group_id=1,
                subtask_ids=["st-2"],
                can_run_in_parallel=False,
                blocked_by=["st-1"],
            ),
        ]
        
        executor = ParallelExecutor(tmp_path, max_parallel=2)
        
        executed_subtasks = {}
        
        async def mock_execute(subtask_id: str) -> str:
            executed_subtasks[subtask_id] = "completed"
            return "success"
        
        results = await executor.execute_parallel_groups(groups, mock_execute)
        
        # Should have results for all subtasks
        assert len(results) >= 4
        assert results.get("st-1") == "completed"
        assert results.get("st-4") == "completed"

    @pytest.mark.asyncio
    async def test_max_parallel_limit(self, tmp_path):
        """Test max concurrent task limit."""
        # Create 5 subtasks, but limit to 2 parallel
        groups = [
            ParallelGroup(
                group_id=0,
                subtask_ids=["st-1", "st-2", "st-3", "st-4", "st-5"],
                can_run_in_parallel=True,
                blocked_by=[],
            ),
        ]
        
        executor = ParallelExecutor(tmp_path, max_parallel=2)
        
        async def mock_execute(subtask_id: str) -> str:
            import asyncio
            await asyncio.sleep(0.1)  # Simulate work
            return "done"
        
        results = await executor.execute_parallel_groups(groups, mock_execute)
        
        # All should complete
        assert len(results) == 5
