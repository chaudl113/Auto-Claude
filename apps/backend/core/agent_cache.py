#!/usr/bin/env python3
"""
Agent State Caching System
=========================

Enables fast resume of agent sessions by caching:
- Conversation context
- Current working state
- File modifications
- Tool usage patterns

Benefits:
- Faster resume after interruptions (network issues, crashes)
- Reduced token usage (don't repeat context)
- Better recovery from partial sessions
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from core.debug import debug, debug_detailed, debug_error

logger = logging.getLogger(__name__)


class AgentStateCache:
    """Manages cached agent state for fast resume."""

    CACHE_VERSION = 1
    CACHE_TTL_HOURS = 24
    MAX_CACHED_MESSAGES = 50

    def __init__(self, spec_dir: Path):
        """
        Initialize cache for a spec.

        Args:
            spec_dir: Spec directory for cache storage
        """
        self.spec_dir = Path(spec_dir)
        self.cache_dir = self.spec_dir / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "agent_state.json"
        self._current_state: dict = {}

    def save_state(
        self,
        session_id: str,
        messages: list[dict],
        context: dict[str, Any],
        file_state: dict[str, str],
    ) -> bool:
        """
        Save current agent state to cache.

        Args:
            session_id: Current session identifier
            messages: Conversation messages (last N messages)
            context: Working context (files, environment, etc.)
            file_state: File modifications (path -> hash)

        Returns:
            True if saved successfully
        """
        try:
            # Only keep last N messages to manage cache size
            cached_messages = messages[-self.MAX_CACHED_MESSAGES:] if messages else []

            state = {
                "version": self.CACHE_VERSION,
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "messages": cached_messages,
                "context": context,
                "file_state": file_state,
            }

            # Write atomically
            temp_file = self.cache_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
            temp_file.replace(self.cache_file)

            debug(
                "agent_cache",
                "State saved to cache",
                session_id=session_id,
                messages_count=len(cached_messages),
                files_count=len(file_state),
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save agent state cache: {e}")
            debug_error("agent_cache", "Save failed", error=str(e))
            return False

    def load_state(self) -> Optional[dict]:
        """
        Load cached agent state if valid.

        Returns:
            Cached state dict or None if cache invalid/expired
        """
        if not self.cache_file.exists():
            debug_detailed("agent_cache", "No cache file found")
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            # Validate cache version
            if state.get("version") != self.CACHE_VERSION:
                debug_detailed("agent_cache", "Cache version mismatch, ignoring")
                return None

            # Check if cache is expired
            timestamp = state.get("timestamp")
            if timestamp:
                cache_age = datetime.now() - datetime.fromisoformat(timestamp)
                if cache_age > timedelta(hours=self.CACHE_TTL_HOURS):
                    debug_detailed(
                        "agent_cache",
                        "Cache expired",
                        age_hours=cache_age.total_seconds() / 3600,
                    )
                    return None

            debug(
                "agent_cache",
                "Cache loaded successfully",
                session_id=state.get("session_id"),
                messages_count=len(state.get("messages", [])),
                age_hours=cache_age.total_seconds() / 3600,
            )
            return state

        except Exception as e:
            logger.error(f"Failed to load agent state cache: {e}")
            debug_error("agent_cache", "Load failed", error=str(e))
            return None

    def invalidate(self) -> None:
        """Invalidate cached state (e.g., after successful completion)."""
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                debug("agent_cache", "Cache invalidated")
            except Exception as e:
                logger.error(f"Failed to invalidate cache: {e}")
                debug_error("agent_cache", "Invalidation failed", error=str(e))

    def get_resume_prompt(self) -> Optional[str]:
        """
        Generate resume prompt from cached state.

        Returns:
            Prompt to resume session or None if no cache
        """
        state = self.load_state()
        if not state:
            return None

        messages = state.get("messages", [])
        if not messages:
            return None

        # Get context summary
        context = state.get("context", {})
        file_state = state.get("file_state", {})

        # Build resume context
        resume_parts = [
            "You are resuming a previous session that was interrupted.",
            "",
            "## Context Summary",
        ]

        if context:
            for key, value in context.items():
                if value:
                    resume_parts.append(f"- {key}: {value}")

        if file_state:
            resume_parts.append("")
            resume_parts.append("## File Modifications")
            for path, file_hash in file_state.items():
                resume_parts.append(f"- {path} (hash: {file_hash[:8]})")

        resume_parts.append("")
        resume_parts.append("## Recent Conversation (Last Messages)")
        resume_parts.append("Here are the last messages from the interrupted session:")
        resume_parts.append("")

        # Add last few messages for context
        last_messages = messages[-5:] if len(messages) > 5 else messages
        for msg in last_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            preview = content[:200] + "..." if len(content) > 200 else content
            resume_parts.append(f"**{role.upper()}**: {preview}")

        resume_parts.append("")
        resume_parts.append(
            "Please continue from where you left off. "
            "The task and context should be clear from the conversation above."
        )

        return "\n".join(resume_parts)


def get_agent_cache(spec_dir: Path) -> AgentStateCache:
    """
    Factory function to get or create agent cache.

    Args:
        spec_dir: Spec directory

    Returns:
        AgentStateCache instance
    """
    return AgentStateCache(spec_dir)
