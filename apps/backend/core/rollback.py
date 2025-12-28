#!/usr/bin/env python3
"""
Rollback Mechanism
=================

Quick rollback using git reflog for safe merge operations.
Tracks commits and provides easy rollback functionality.

Benefits:
- Safe merge operations with one-click rollback
- Automatic commit tracking for recovery
- Quick rollback to previous stable state
- Integration with existing RecoveryManager
"""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.debug import debug, debug_detailed, debug_error, debug_success

logger = logging.getLogger(__name__)


@dataclass
class RollbackPoint:
    """Represents a rollback point in git history."""

    commit_hash: str
    timestamp: str
    message: str
    reflog_index: int
    is_stable: bool = False


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    previous_commit: str
    current_commit: str
    files_changed: List[str]
    error: Optional[str] = None


class RollbackManager:
    """
    Manages quick rollback operations using git reflog.

    Usage:
        manager = RollbackManager(project_dir)
        manager.record_safe_point("Before merge")  # Record stable state
        # ... perform merge ...
        result = manager.rollback()  # Quick rollback to safe point
    """

    MAX_REFLOG_ENTRIES = 50

    def __init__(self, project_dir: Path):
        """
        Initialize rollback manager.

        Args:
            project_dir: Project root directory
        """
        self.project_dir = Path(project_dir)

    def record_safe_point(self, message: str = "Safe rollback point") -> str:
        """
        Record a stable state as a rollback point.

        Creates a commit with a special marker for easy identification.

        Args:
            message: Optional description for rollback point

        Returns:
            Commit hash of safe point
        """
        debug("rollback", "Recording safe rollback point", message=message)

        # Create a commit with special marker
        marker = f"[rollback-safe] {message}"

        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.project_dir,
            capture_output=True,
        )

        # Create commit with marker
        result = subprocess.run(
            ["git", "commit", "-m", marker],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 and "nothing to commit" not in result.stderr:
            debug_error("rollback", "Failed to create safe point", error=result.stderr)
            return None

        # Get commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        if commit_result.returncode == 0:
            commit_hash = commit_result.stdout.strip()
            debug_success(
                "rollback", "Safe point recorded", commit=commit_hash[:8]
            )
            return commit_hash

        return None

    def get_rollback_points(self, limit: int = 20) -> List[RollbackPoint]:
        """
        Gets list of available rollback points from reflog.

        Args:
            limit: Maximum number of points to return

        Returns:
            List of RollbackPoint objects, most recent first
        """
        debug_detailed("rollback", "Getting rollback points from reflog")

        # Get reflog entries
        result = subprocess.run(
            ["git", "reflog", "-n", str(limit)],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            debug_error("rollback", "Failed to get reflog", error=result.stderr)
            return []

        points = []

        for i, line in enumerate(result.stdout.strip().split("\n")):
            # Parse reflog line: abc123 HEAD@{0}: commit message
            if ":" not in line:
                continue

            parts = line.split(":", 1)
            if len(parts) != 2:
                continue

            hash_part, rest = parts

            # Extract commit hash (first 7 chars are enough)
            commit_hash = hash_part.strip().split()[0]

            # Parse timestamp and message
            # Format: HEAD@{0}: commit message (timestamp)
            # Extract timestamp in parentheses
            timestamp = "unknown"
            message = rest.strip()

            if "(" in message and ")" in message:
                start = message.rfind("(")
                end = message.rfind(")")
                timestamp = message[start + 1 : end]
                message = message[:start].strip()

            # Check if this is a safe point marker
            is_safe = "[rollback-safe]" in message

            # Clean up message
            if is_safe:
                message = message.replace("[rollback-safe]", "").strip()

            points.append(
                RollbackPoint(
                    commit_hash=commit_hash,
                    timestamp=timestamp,
                    message=message,
                    reflog_index=i,
                    is_stable=is_safe,
                )
            )

        debug_detailed("rollback", "Found rollback points", count=len(points))
        return points

    def rollback(
        self, target_commit: Optional[str] = None, create_backup: bool = True
    ) -> RollbackResult:
        """
        Rollbacks to a previous commit.

        If target_commit is None, rolls back to most recent safe point.

        Args:
            target_commit: Specific commit hash to rollback to
            create_backup: Whether to create a backup commit before rolling back

        Returns:
            RollbackResult with operation details
        """
        debug(
            "rollback",
            "Initiating rollback",
            target_commit=target_commit,
            create_backup=create_backup,
        )

        # Get current commit for comparison
        current_commit = self._get_current_commit()

        if not target_commit:
            # Find most recent safe point
            target_commit = self._find_latest_safe_point()

            if not target_commit:
                debug_error(
                    "rollback", "No safe rollback point found"
                )
                return RollbackResult(
                    success=False,
                    previous_commit=current_commit,
                    current_commit=current_commit,
                    files_changed=[],
                    error="No safe rollback point found. Use 'record_safe_point' first.",
                )

        debug_detailed(
            "rollback", "Rolling back", from_commit=current_commit[:8], to_commit=target_commit[:8]
        )

        # Create backup if requested
        backup_commit = None
        if create_backup:
            backup_commit = self.record_safe_point(
                f"Backup before rollback to {target_commit[:8]}"
            )

        # Get list of files that will change
        files_changed = self._get_affected_files(target_commit)

        # Reset to target commit (hard reset)
        result = subprocess.run(
            ["git", "reset", "--hard", target_commit],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            debug_error("rollback", "Reset failed", error=result.stderr)
            return RollbackResult(
                success=False,
                previous_commit=current_commit,
                current_commit=current_commit,
                files_changed=files_changed,
                error=f"Reset failed: {result.stderr}",
            )

        new_commit = self._get_current_commit()

        debug_success(
            "rollback",
            "Rollback successful",
            previous=current_commit[:8],
            current=new_commit[:8],
            files_changed=len(files_changed),
            backup=backup_commit[:8] if backup_commit else None,
        )

        return RollbackResult(
            success=True,
            previous_commit=current_commit,
            current_commit=new_commit,
            files_changed=files_changed,
        )

    def _find_latest_safe_point(self) -> Optional[str]:
        """Finds most recent commit marked as safe rollback point."""
        points = self.get_rollback_points(limit=50)

        for point in points:
            if point.is_stable:
                return point.commit_hash

        return None

    def _get_current_commit(self) -> str:
        """Gets current HEAD commit hash."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return result.stdout.strip()

        return "unknown"

    def _get_affected_files(self, target_commit: str) -> List[str]:
        """Gets list of files that will change during rollback."""
        current_commit = self._get_current_commit()

        # Get diff between current and target
        result = subprocess.run(
            ["git", "diff", "--name-only", current_commit, target_commit],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            files = [f for f in result.stdout.strip().split("\n") if f]
            return files

        return []

    def can_rollback(self) -> bool:
        """
        Checks if rollback is possible.

        Returns:
            True if at least one safe rollback point exists
        """
        return self._find_latest_safe_point() is not None

    def display_rollback_menu(self) -> None:
        """Displays interactive menu of rollback points."""
        from ui import bold, error, muted, print_status, success, warning

        points = self.get_rollback_points(limit=20)

        if not points:
            print(error("No rollback points available."))
            print()
            print("Tip: Use 'record_safe_point' to create rollback points.")
            return

        print()
        print(bold("=" * 70))
        print(bold("ROLLBACK MENU"))
        print(bold("=" * 70))
        print()

        for i, point in enumerate(points, 1):
            icon = success("✓") if point.is_stable else warning("•")
            status = " (SAFE)" if point.is_stable else ""

            print(
                f"  {bold(str(i))}. {icon} {point.commit_hash[:8]} {point.timestamp}{status}"
            )
            print(f"      {point.message}")
            print()

        print(bold("=" * 70))
        print()

    def cleanup_old_points(self, max_age_hours: int = 24) -> int:
        """
        Cleanups old rollback points (optional).

        Note: This uses git reflog expiration, which is automatic.
        This method is mainly for reference and manual cleanup if needed.

        Args:
            max_age_hours: Maximum age for rollback points (default 24 hours)

        Returns:
            Number of points that would be cleaned up
        """
        points = self.get_rollback_points(limit=self.MAX_REFLOG_ENTRIES)

        cleaned = 0

        for point in points:
            # Check age (simplified - real implementation would parse timestamps)
            if not point.is_stable:
                cleaned +=1

        debug_detailed(
            "rollback", "Cleanup analysis", old_points=cleaned
        )

        return cleaned


def get_rollback_manager(project_dir: Path) -> RollbackManager:
    """Factory function to get RollbackManager instance."""
    return RollbackManager(project_dir)
