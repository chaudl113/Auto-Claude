#!/usr/bin/env python3
"""
AI Diff Preview
==============

Generate AI-powered diff previews before merging worktrees.
Shows file changes, summaries, and allows approval/rejection.

Benefits:
- Preview changes before merging to main
- Catch unintended changes early
- Better review experience with AI summaries
"""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from claude_agent_sdk import ClaudeSDKClient
from core.debug import debug, debug_detailed, debug_error, debug_success

logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """Represents a file change."""

    path: str
    status: str  # 'A' (added), 'M' (modified), 'D' (deleted)
    diff: str | None = None
    summary: str | None = None


@dataclass
class DiffPreview:
    """Complete diff preview with AI-generated summary."""

    spec_name: str
    base_branch: str
    spec_branch: str
    files_changed: List[FileChange]
    summary: str | None = None
    total_additions: int = 0
    total_deletions: int = 0


class DiffPreviewGenerator:
    """
    Generates AI-powered diff previews for worktree merges.

    Usage:
        generator = DiffPreviewGenerator(project_dir)
        preview = generator.generate_preview(spec_name, base_branch)
        preview.display()
        approved = preview.prompt_approval()
    """

    def __init__(self, project_dir: Path, client: ClaudeSDKClient | None = None):
        """
        Initialize diff preview generator.

        Args:
            project_dir: Project root directory
            client: Optional Claude SDK client for AI summaries
        """
        self.project_dir = Path(project_dir)
        self.client = client

    def generate_preview(
        self,
        spec_name: str,
        base_branch: str | None = None,
        include_ai_summary: bool = True,
    ) -> DiffPreview:
        """
        Generate a comprehensive diff preview.

        Args:
            spec_name: Name of spec/worktree
            base_branch: Base branch to compare against (auto-detect if None)
            include_ai_summary: Whether to generate AI summary of changes

        Returns:
            DiffPreview object with all change information
        """
        debug(
            "diff_preview",
            "Generating diff preview",
            spec_name=spec_name,
            base_branch=base_branch,
        )

        # Detect base branch if not specified
        if not base_branch:
            base_branch = self._detect_base_branch()

        spec_branch = f"auto-claude/{spec_name}"

        # Get file changes
        files_changed = self._get_file_changes(spec_branch, base_branch)
        total_additions = sum(f.diff.count("\n+") if f.diff else 0 for f in files_changed)
        total_deletions = sum(f.diff.count("\n-") if f.diff else 0 for f in files_changed)

        preview = DiffPreview(
            spec_name=spec_name,
            base_branch=base_branch,
            spec_branch=spec_branch,
            files_changed=files_changed,
            total_additions=total_additions,
            total_deletions=total_deletions,
        )

        # Generate AI summary if client available
        if include_ai_summary and self.client and files_changed:
            preview.summary = self._generate_ai_summary(preview)

        debug_success(
            "diff_preview",
            "Diff preview generated",
            files_count=len(files_changed),
            total_additions=total_additions,
            total_deletions=total_deletions,
        )

        return preview

    def _detect_base_branch(self) -> str:
        """Auto-detects base branch."""
        for branch in ["main", "master"]:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return branch

        # Fall back to current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _get_file_changes(self, spec_branch: str, base_branch: str) -> List[FileChange]:
        """Gets list of changed files with diffs."""
        files = []

        # Get changed files with status
        result = subprocess.run(
            ["git", "diff", "--name-status", f"{base_branch}...{spec_branch}"],
            cwd=self.project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            debug_error("diff_preview", "Failed to get changed files", error=result.stderr)
            return files

        # Parse file changes
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue

            status, path = parts
            if status not in ("A", "M", "D"):
                continue

            # Get diff for modified/added files
            diff = None
            if status in ("A", "M"):
                diff_result = subprocess.run(
                    [
                        "git",
                        "diff",
                        f"{base_branch}...{spec_branch}",
                        "--",
                        path,
                    ],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                )
                if diff_result.returncode == 0:
                    diff = diff_result.stdout

            files.append(FileChange(path=path, status=status, diff=diff))

        return files

    async def _generate_ai_summary(self, preview: DiffPreview) -> str:
        """
        Generates AI summary of changes.

        Args:
            preview: DiffPreview with all file changes

        Returns:
            AI-generated summary string
        """
        if not self.client:
            return None

        # Build summary prompt
        changed_files = "\n".join(
            [f"- {f.status} {f.path}" for f in preview.files_changed]
        )

        prompt = f"""Please summarize these code changes for a code review:

Spec: {preview.spec_name}
Branches: {preview.base_branch} → {preview.spec_branch}

Files Changed:
{changed_files}

Total Changes:
+{preview.total_additions} lines
-{preview.total_deletions} lines

Provide a concise summary (3-5 bullet points) of what this change does:
1. Main purpose of the change
2. Key files or components affected
3. Any potential risks or concerns
4. Testing recommendations
5. Breaking changes or migration notes (if any)

Keep it technical and brief."""

        try:
            debug_detailed("diff_preview", "Requesting AI summary...")
            await self.client.query(prompt)

            # Collect response
            summary = ""
            async for msg in self.client.receive_response():
                msg_type = type(msg).__name__
                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        if type(block).__name__ == "TextBlock":
                            summary += block.text

            return summary.strip() if summary else None

        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            debug_error("diff_preview", "AI summary generation failed", error=str(e))
            return None

    def display_preview(self, preview: DiffPreview, verbose: bool = False) -> None:
        """
        Displays diff preview to user.

        Args:
            preview: DiffPreview to display
            verbose: Show full diffs (vs just file list)
        """
        from ui import bold, error, muted, success, warning

        print()
        print(bold("=" * 70))
        print(bold("DIFF PREVIEW"))
        print(bold("=" * 70))
        print()
        print(f"Spec: {preview.spec_name}")
        print(f"Branch: {preview.base_branch} → {preview.spec_branch}")
        print(f"Files: {len(preview.files_changed)}")
        print(f"Changes: +{preview.total_additions} -{preview.total_deletions}")
        print()

        # Show AI summary if available
        if preview.summary:
            print(bold("AI Summary:"))
            print(preview.summary)
            print()

        # Show file changes
        print(bold("Files Changed:"))
        for file in preview.files_changed:
            status_icon = {
                "A": success("✓ (new)"),
                "M": warning("~ (modified)"),
                "D": error("✗ (deleted)"),
            }.get(file.status, "?")

            print(f"  {status_icon} {file.path}")

            if verbose and file.diff:
                print(muted(f"    Diff: {len(file.diff)} lines"))
                if len(file.diff) < 500:
                    print(muted(file.diff[:200]))
                else:
                    print(muted(f"    {file.diff[:200]}... (truncated)"))
                print()

        print(bold("=" * 70))
        print()

    async def prompt_approval(self, preview: DiffPreview) -> bool:
        """
        Prompts user to approve or reject merge.

        Args:
            preview: DiffPreview to show

        Returns:
            True if user approves, False otherwise
        """
        from ui import (
            bold,
            error,
            info,
            input,
            print_status,
            success,
            warning,
        )

        self.display_preview(preview, verbose=False)

        while True:
            print()
            print("Options:")
            print("  " + success("[y]") + " - Merge these changes")
            print("  " + warning("[v]") + " - Show verbose diffs")
            print("  " + info("[d]") + " - Show diff for specific file")
            print("  " + error("[n]") + " - Cancel merge")
            print()

            choice = input(bold("Approve merge? [y/v/d/n]: ")).strip().lower()

            if choice == "y":
                return True
            elif choice == "n":
                return False
            elif choice == "v":
                self.display_preview(preview, verbose=True)
            elif choice == "d":
                file_path = input("Enter file path to show diff: ").strip()
                file = next((f for f in preview.files_changed if f.path == file_path), None)
                if file and file.diff:
                    print()
                    print(bold(f"Diff for {file.path}:"))
                    print(file.diff)
                elif file:
                    print(warning("No diff available for this file"))
                else:
                    print(error(f"File not found: {file_path}"))
            else:
                print(warning("Invalid choice. Try again."))


def get_diff_preview_generator(project_dir: Path) -> DiffPreviewGenerator:
    """Factory function to get DiffPreviewGenerator instance."""
    return DiffPreviewGenerator(project_dir)
