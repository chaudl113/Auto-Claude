#!/usr/bin/env python3
"""
Tests for Agent State Caching
=============================
"""

import json
import tempfile
from pathlib import Path

import pytest

from core.agent_cache import AgentStateCache


class TestAgentStateCache:
    """Test agent state caching functionality."""

    def test_cache_initialization(self, tmp_path):
        """Test cache creates directory structure."""
        cache_dir = tmp_path / "test_spec" / ".cache"
        cache = AgentStateCache(tmp_path / "test_spec")

        assert cache.cache_dir.exists()
        assert cache.cache_file.parent == cache_dir

    def test_save_and_load_state(self, tmp_path):
        """Test saving and loading state."""
        cache = AgentStateCache(tmp_path / "test_spec")

        session_id = "test-session-001"
        messages = [
            {"role": "user", "content": "Implement feature X"},
            {"role": "assistant", "content": "I'll start..."},
        ]
        context = {"current_file": "src/app.py", "task": "Add login"}
        file_state = {"src/app.py": "abc123"}

        # Save
        saved = cache.save_state(session_id, messages, context, file_state)
        assert saved is True
        assert cache.cache_file.exists()

        # Load
        loaded = cache.load_state()
        assert loaded is not None
        assert loaded["session_id"] == session_id
        assert len(loaded["messages"]) == 2
        assert loaded["context"] == context
        assert loaded["file_state"] == file_state

    def test_messages_truncation(self, tmp_path):
        """Test cache only keeps last N messages."""
        cache = AgentStateCache(tmp_path / "test_spec")

        messages = [{"role": "user", "content": f"Message {i}"} for i in range(100)]
        cache.save_state("session-1", messages, {}, {})

        loaded = cache.load_state()
        # Should only keep last MAX_CACHED_MESSAGES (50)
        assert len(loaded["messages"]) == cache.MAX_CACHED_MESSAGES
        assert loaded["messages"][0]["role"] == "user"
        assert loaded["messages"][0]["content"] == "Message 50"

    def test_cache_invalidation(self, tmp_path):
        """Test cache can be invalidated."""
        cache = AgentStateCache(tmp_path / "test_spec")

        # Save state
        cache.save_state("session-1", [], {}, {})
        assert cache.cache_file.exists()

        # Invalidate
        cache.invalidate()
        assert not cache.cache_file.exists()

    def test_resume_prompt_generation(self, tmp_path):
        """Test resume prompt is generated correctly."""
        cache = AgentStateCache(tmp_path / "test_spec")

        messages = [
            {"role": "user", "content": "Add user login"},
            {"role": "assistant", "content": "I'll implement login form..."},
        ]
        context = {"task": "Add login form", "branch": "feature/login"}
        file_state = {"src/Login.tsx": "hash123"}

        cache.save_state("session-1", messages, context, file_state)

        resume = cache.get_resume_prompt()
        assert resume is not None
        assert "You are resuming" in resume
        assert "Add login form" in resume
        assert "src/Login.tsx" in resume
        assert "Recent Conversation" in resume

    def test_no_cache_returns_none(self, tmp_path):
        """Test loading without cache returns None."""
        cache = AgentStateCache(tmp_path / "nonexistent_spec")

        loaded = cache.load_state()
        assert loaded is None

        resume = cache.get_resume_prompt()
        assert resume is None

    def test_version_mismatch_invalidates(self, tmp_path):
        """Test old cache versions are rejected."""
        cache = AgentStateCache(tmp_path / "test_spec")

        # Manually write old version
        old_state = {
            "version": 0,  # Wrong version
            "timestamp": "2024-01-01T00:00:00",
            "session_id": "old-session",
            "messages": [],
            "context": {},
            "file_state": {},
        }
        with open(cache.cache_file, "w") as f:
            json.dump(old_state, f)

        loaded = cache.load_state()
        assert loaded is None  # Should reject old cache

    @pytest.fixture
    def tmp_path(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
