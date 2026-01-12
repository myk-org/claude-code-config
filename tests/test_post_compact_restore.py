#!/usr/bin/env python3
"""Unit tests for post-compact-restore.py."""

import importlib.util
import json
import sys
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest


def _load_post_compact_restore_module() -> ModuleType:
    """Load the post-compact-restore module with hyphenated filename."""
    script_path = Path(__file__).parent.parent / "scripts" / "post-compact-restore.py"
    spec = importlib.util.spec_from_file_location("post_compact_restore", script_path)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load post-compact-restore module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["post_compact_restore"] = module
    spec.loader.exec_module(module)
    return module


post_compact_restore = _load_post_compact_restore_module()

# Import the functions we need to test
STATE_DIR: Path = post_compact_restore.STATE_DIR
format_context: Callable[[dict[str, Any]], str] = post_compact_restore.format_context
get_snapshot_file: Callable[[str], Path] = post_compact_restore.get_snapshot_file
load_snapshot: Callable[[str], Any] = post_compact_restore.load_snapshot
main: Callable[[], None] = post_compact_restore.main


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def full_snapshot() -> dict[str, Any]:
    """Complete snapshot with all fields populated."""
    return {
        "project": "my-test-project",
        "working_dir": "/home/user/projects/my-test-project",
        "timestamp": "2024-01-15T10:30:00Z",
        "current_focus": "Implementing user authentication feature",
        "tasks": [
            {"task": "Create user model", "status": "completed"},
            {"task": "Add authentication middleware", "status": "in_progress"},
            {"task": "Write unit tests", "status": "pending"},
        ],
        "decisions": [
            "Use JWT for token-based auth",
            "Store refresh tokens in Redis",
            "Implement rate limiting on login endpoint",
        ],
    }


@pytest.fixture
def minimal_snapshot() -> dict[str, Any]:
    """Snapshot with only required fields."""
    return {
        "project": "minimal-project",
        "timestamp": "2024-01-15T10:30:00Z",
    }


@pytest.fixture
def partial_snapshot() -> dict[str, Any]:
    """Snapshot with some optional fields missing."""
    return {
        "project": "partial-project",
        "working_dir": "/home/user/partial",
        "timestamp": "2024-01-15T10:30:00Z",
        "tasks": [
            {"task": "Single task", "status": "in_progress"},
        ],
    }


@pytest.fixture
def snapshot_with_empty_lists() -> dict[str, Any]:
    """Snapshot with empty lists for tasks and decisions."""
    return {
        "project": "empty-lists-project",
        "working_dir": "/home/user/empty",
        "timestamp": "2024-01-15T10:30:00Z",
        "tasks": [],
        "decisions": [],
    }


@pytest.fixture
def snapshot_with_many_decisions() -> dict[str, Any]:
    """Snapshot with more than 5 decisions (tests truncation)."""
    return {
        "project": "many-decisions-project",
        "timestamp": "2024-01-15T10:30:00Z",
        "decisions": [
            "Decision 1",
            "Decision 2",
            "Decision 3",
            "Decision 4",
            "Decision 5",
            "Decision 6 - should be truncated",
            "Decision 7 - should be truncated",
        ],
    }


@pytest.fixture
def snapshot_file_path(tmp_path: Path) -> Path:
    """Create a temporary state directory and return a helper for file paths."""
    state_dir = tmp_path / ".claude" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


# =============================================================================
# Tests for get_snapshot_file()
# =============================================================================


class TestGetSnapshotFile:
    """Tests for get_snapshot_file function."""

    def test_returns_path_object(self) -> None:
        """Should return a Path object."""
        result = get_snapshot_file("test-session-123")
        assert isinstance(result, Path)

    def test_path_contains_session_id(self) -> None:
        """Path should include the session ID."""
        session_id = "unique-session-abc123"
        result = get_snapshot_file(session_id)
        assert session_id in str(result)

    def test_path_ends_with_snapshot_json(self) -> None:
        """Path should end with -snapshot.json suffix."""
        result = get_snapshot_file("my-session")
        assert str(result).endswith("-snapshot.json")

    def test_path_is_in_state_dir(self) -> None:
        """Path should be within the STATE_DIR."""
        result = get_snapshot_file("session-id")
        assert result.parent == STATE_DIR

    def test_different_sessions_get_different_files(self) -> None:
        """Different session IDs should produce different file paths."""
        path1 = get_snapshot_file("session-1")
        path2 = get_snapshot_file("session-2")
        assert path1 != path2


# =============================================================================
# Tests for load_snapshot()
# =============================================================================


class TestLoadSnapshot:
    """Tests for load_snapshot function."""

    def test_load_valid_json(self, tmp_path: Path, full_snapshot: Any) -> None:
        """Should successfully load valid JSON snapshot."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            snapshot_file = tmp_path / "test-session-snapshot.json"
            snapshot_file.write_text(json.dumps(full_snapshot))
            mock_get_file.return_value = snapshot_file

            result = load_snapshot("test-session")

            assert result == full_snapshot
            assert result["project"] == "my-test-project"
            assert len(result["tasks"]) == 3

    def test_missing_file_returns_empty_dict(self, tmp_path: Path, capsys: Any) -> None:
        """Should return empty dict when snapshot file doesn't exist."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            non_existent = tmp_path / "non-existent-snapshot.json"
            mock_get_file.return_value = non_existent

            result = load_snapshot("missing-session")

            assert result == {}
            captured = capsys.readouterr()
            assert "Snapshot file not found" in captured.err

    def test_invalid_json_returns_empty_dict(self, tmp_path: Path, capsys: Any) -> None:
        """Should return empty dict when JSON is malformed."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            invalid_file = tmp_path / "invalid-snapshot.json"
            invalid_file.write_text("{not valid json: ]}")
            mock_get_file.return_value = invalid_file

            result = load_snapshot("invalid-session")

            assert result == {}
            captured = capsys.readouterr()
            assert "Failed to parse snapshot JSON" in captured.err

    def test_empty_json_file(self, tmp_path: Path) -> None:
        """Should handle empty JSON object."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            empty_file = tmp_path / "empty-snapshot.json"
            empty_file.write_text("{}")
            mock_get_file.return_value = empty_file

            result = load_snapshot("empty-session")

            assert result == {}

    def test_json_array_instead_of_object(self, tmp_path: Path) -> None:
        """Should handle JSON array (returns as-is, format_context handles it)."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            array_file = tmp_path / "array-snapshot.json"
            array_file.write_text('["item1", "item2"]')
            mock_get_file.return_value = array_file

            result = load_snapshot("array-session")

            # json.loads returns the array, which is truthy but not a dict
            assert result == ["item1", "item2"]

    def test_unicode_content(self, tmp_path: Path) -> None:
        """Should handle unicode characters in snapshot."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            unicode_file = tmp_path / "unicode-snapshot.json"
            unicode_snapshot = {
                "project": "projet-francais",
                "current_focus": "Implementing cafe feature",
                "decisions": ["Use emoji support"],
            }
            unicode_file.write_text(json.dumps(unicode_snapshot, ensure_ascii=False), encoding="utf-8")
            mock_get_file.return_value = unicode_file

            result = load_snapshot("unicode-session")

            assert result["project"] == "projet-francais"
            assert result["current_focus"] == "Implementing cafe feature"


# =============================================================================
# Tests for format_context()
# =============================================================================


class TestFormatContext:
    """Tests for format_context function."""

    def test_full_snapshot_formatting(self, full_snapshot: dict[str, Any]) -> None:
        """Should format complete snapshot with all sections."""
        result = format_context(full_snapshot)

        assert "**Project**: my-test-project" in result
        assert "**Working Directory**: /home/user/projects/my-test-project" in result
        assert "## Current Focus" in result
        assert "Implementing user authentication feature" in result
        assert "## Tasks" in result
        assert "[done] Create user model" in result
        assert "[doing] Add authentication middleware" in result
        assert "[todo] Write unit tests" in result
        assert "## Key Decisions" in result
        assert "Use JWT for token-based auth" in result

    def test_minimal_snapshot_formatting(self, minimal_snapshot: dict[str, Any]) -> None:
        """Should format minimal snapshot with only project info."""
        result = format_context(minimal_snapshot)

        assert "**Project**: minimal-project" in result
        assert "## Current Focus" not in result
        assert "## Tasks" not in result
        assert "## Key Decisions" not in result

    def test_partial_snapshot_formatting(self, partial_snapshot: dict[str, Any]) -> None:
        """Should format partial snapshot with available fields only."""
        result = format_context(partial_snapshot)

        assert "**Project**: partial-project" in result
        assert "**Working Directory**: /home/user/partial" in result
        assert "[doing] Single task" in result
        assert "## Key Decisions" not in result

    def test_empty_lists_not_rendered(self, snapshot_with_empty_lists: dict[str, Any]) -> None:
        """Should not render section headers for empty lists."""
        result = format_context(snapshot_with_empty_lists)

        assert "**Project**: empty-lists-project" in result
        assert "## Tasks" not in result
        assert "## Key Decisions" not in result

    def test_decisions_truncated_at_five(self, snapshot_with_many_decisions: dict[str, Any]) -> None:
        """Should only show first 5 decisions."""
        result = format_context(snapshot_with_many_decisions)

        assert "Decision 1" in result
        assert "Decision 5" in result
        assert "Decision 6" not in result
        assert "Decision 7" not in result

    def test_empty_snapshot(self) -> None:
        """Should handle empty snapshot dict."""
        result = format_context({})

        assert "**Project**: unknown" in result

    def test_missing_project_defaults_to_unknown(self) -> None:
        """Should default project to 'unknown' if not provided."""
        result = format_context({"current_focus": "Something"})

        assert "**Project**: unknown" in result

    def test_task_with_missing_status(self) -> None:
        """Should handle task with missing status field."""
        snapshot = {
            "project": "test",
            "tasks": [{"task": "No status task"}],
        }
        result = format_context(snapshot)

        assert "[unknown] No status task" in result

    def test_task_with_missing_task_text(self) -> None:
        """Should handle task with missing task field."""
        snapshot = {
            "project": "test",
            "tasks": [{"status": "completed"}],
        }
        result = format_context(snapshot)

        assert "[done]" in result

    def test_unknown_task_status(self) -> None:
        """Should pass through unknown status as-is."""
        snapshot = {
            "project": "test",
            "tasks": [{"task": "Custom status", "status": "blocked"}],
        }
        result = format_context(snapshot)

        assert "[blocked] Custom status" in result

    def test_working_dir_not_rendered_when_empty_string(self) -> None:
        """Should not render working directory line when it's empty string."""
        snapshot = {
            "project": "test",
            "working_dir": "",
        }
        result = format_context(snapshot)

        assert "**Working Directory**" not in result

    def test_current_focus_not_rendered_when_empty_string(self) -> None:
        """Should not render current focus when it's empty string."""
        snapshot = {
            "project": "test",
            "current_focus": "",
        }
        result = format_context(snapshot)

        assert "## Current Focus" not in result


# =============================================================================
# Tests for main()
# =============================================================================


class TestMain:
    """Tests for main function (JSON input/output protocol)."""

    def test_valid_session_with_snapshot(self, tmp_path: Path, full_snapshot: dict[str, Any], capsys: Any) -> None:
        """Should output additionalContext when snapshot exists."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            snapshot_file = tmp_path / "test-session-snapshot.json"
            snapshot_file.write_text(json.dumps(full_snapshot))
            mock_get_file.return_value = snapshot_file

            hook_input = json.dumps({"session_id": "test-session"})
            with patch("sys.stdin", StringIO(hook_input)):
                main()

            captured = capsys.readouterr()
            output = json.loads(captured.out.strip())

            assert "additionalContext" in output
            assert "[SESSION CONTEXT RESTORED AFTER COMPACTION]" in output["additionalContext"]
            assert "my-test-project" in output["additionalContext"]

    def test_missing_snapshot_returns_no_snapshot_found(self, tmp_path: Path, capsys: Any) -> None:
        """Should return no_snapshot_found status when file doesn't exist."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            mock_get_file.return_value = tmp_path / "non-existent.json"

            hook_input = json.dumps({"session_id": "missing-session"})
            with patch("sys.stdin", StringIO(hook_input)):
                main()

            captured = capsys.readouterr()
            output = json.loads(captured.out.strip())

            assert output == {"status": "no_snapshot_found"}
            assert "No snapshot found" in captured.err

    def test_invalid_json_input_uses_unknown_session(self, tmp_path: Path, capsys: Any) -> None:
        """Should handle malformed JSON input gracefully and use 'unknown' session."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            mock_get_file.return_value = tmp_path / "unknown-snapshot.json"

            with patch("sys.stdin", StringIO("not valid json")):
                main()

            captured = capsys.readouterr()
            assert "Failed to parse hook input JSON" in captured.err
            mock_get_file.assert_called_with("unknown")

    def test_missing_session_id_uses_unknown(self, tmp_path: Path) -> None:
        """Should use 'unknown' as session_id when not provided."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            mock_get_file.return_value = tmp_path / "unknown-snapshot.json"

            hook_input = json.dumps({})  # No session_id
            with patch("sys.stdin", StringIO(hook_input)):
                main()

            mock_get_file.assert_called_with("unknown")

    def test_empty_json_object_returns_no_snapshot_found(self, tmp_path: Path, capsys: Any) -> None:
        """Should return no_snapshot_found when snapshot file contains empty JSON object.

        An empty dict {} is falsy in Python, so load_snapshot returns {} which
        triggers the no_snapshot_found branch in main().
        """
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            snapshot_file = tmp_path / "empty-snapshot.json"
            snapshot_file.write_text("{}")
            mock_get_file.return_value = snapshot_file

            hook_input = json.dumps({"session_id": "empty-session"})
            with patch("sys.stdin", StringIO(hook_input)):
                main()

            captured = capsys.readouterr()
            output = json.loads(captured.out.strip())
            assert output == {"status": "no_snapshot_found"}

    def test_timestamp_included_in_output(self, tmp_path: Path, full_snapshot: dict[str, Any], capsys: Any) -> None:
        """Should include timestamp from snapshot in output."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            snapshot_file = tmp_path / "test-snapshot.json"
            snapshot_file.write_text(json.dumps(full_snapshot))
            mock_get_file.return_value = snapshot_file

            hook_input = json.dumps({"session_id": "test"})
            with patch("sys.stdin", StringIO(hook_input)):
                main()

            captured = capsys.readouterr()
            output = json.loads(captured.out.strip())

            assert "2024-01-15T10:30:00Z" in output["additionalContext"]

    def test_output_is_valid_json(self, tmp_path: Path, full_snapshot: dict[str, Any], capsys: Any) -> None:
        """Should always output valid JSON."""
        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            snapshot_file = tmp_path / "test-snapshot.json"
            snapshot_file.write_text(json.dumps(full_snapshot))
            mock_get_file.return_value = snapshot_file

            hook_input = json.dumps({"session_id": "test"})
            with patch("sys.stdin", StringIO(hook_input)):
                main()

            captured = capsys.readouterr()
            # This should not raise
            parsed = json.loads(captured.out.strip())
            assert isinstance(parsed, dict)


# =============================================================================
# Integration-style tests
# =============================================================================


class TestIntegration:
    """Integration-style tests that test multiple components together."""

    def test_full_workflow(self, tmp_path: Path, capsys: Any) -> None:
        """Test the complete workflow from input to output."""
        # Create a realistic snapshot
        snapshot = {
            "project": "integration-test",
            "working_dir": "/home/user/integration-test",
            "timestamp": "2024-01-15T12:00:00Z",
            "current_focus": "Testing the restore functionality",
            "tasks": [
                {"task": "Write tests", "status": "in_progress"},
                {"task": "Run tests", "status": "pending"},
            ],
            "decisions": ["Use pytest", "Mock external dependencies"],
        }

        with patch("post_compact_restore.get_snapshot_file") as mock_get_file:
            snapshot_file = tmp_path / "integration-snapshot.json"
            snapshot_file.write_text(json.dumps(snapshot))
            mock_get_file.return_value = snapshot_file

            hook_input = json.dumps({"session_id": "integration-test"})
            with patch("sys.stdin", StringIO(hook_input)):
                main()

            captured = capsys.readouterr()
            output = json.loads(captured.out.strip())

            # Verify structure
            assert "additionalContext" in output
            context = output["additionalContext"]

            # Verify content
            assert "[SESSION CONTEXT RESTORED AFTER COMPACTION]" in context
            assert "integration-test" in context
            assert "Testing the restore functionality" in context
            assert "[doing] Write tests" in context
            assert "[todo] Run tests" in context
            assert "Use pytest" in context
