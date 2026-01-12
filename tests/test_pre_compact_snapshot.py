"""Comprehensive unit tests for pre-compact-snapshot.py."""

import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest


def _load_pre_compact_snapshot_module() -> ModuleType:
    """Load the pre-compact-snapshot module with hyphenated filename."""
    scripts_dir = Path(__file__).parent.parent / "scripts"
    spec = importlib.util.spec_from_file_location("pre_compact_snapshot", scripts_dir / "pre-compact-snapshot.py")
    if spec is None or spec.loader is None:
        raise ImportError("Could not load pre-compact-snapshot module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["pre_compact_snapshot"] = module
    spec.loader.exec_module(module)
    return module


_module = _load_pre_compact_snapshot_module()

# Import the functions we need to test
get_snapshot_file: Callable[[str], Path] = _module.get_snapshot_file
validate_transcript_path: Callable[[str | None], bool] = _module.validate_transcript_path
normalize_task_description: Callable[[str], str] = _module.normalize_task_description
extract_from_transcript: Callable[[str], dict[str, Any]] = _module.extract_from_transcript
_is_code_block: Callable[[str], bool] = _module._is_code_block
_looks_like_code: Callable[[str], bool] = _module._looks_like_code
STATE_DIR: Path = _module.STATE_DIR


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tmp_claude_dir(tmp_path: Path) -> Path:
    """Create a temporary .claude directory structure."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    return claude_dir


@pytest.fixture
def mock_home(tmp_path: Path, monkeypatch: Any) -> Path:
    """Mock Path.home() to return tmp_path."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


# =============================================================================
# Tests for get_snapshot_file()
# =============================================================================


class TestGetSnapshotFile:
    """Tests for get_snapshot_file function."""

    def test_basic_session_id(self) -> None:
        """Test path construction with basic session ID."""
        result = get_snapshot_file("session123")
        # STATE_DIR is set at import time, so we check the structure
        assert result.name == "session123-snapshot.json"
        assert result.parent.name == "state"
        assert result.parent.parent.name == ".claude"

    def test_uuid_session_id(self) -> None:
        """Test path construction with UUID-style session ID."""
        session_id = "550e8400-e29b-41d4-a716-446655440000"
        result = get_snapshot_file(session_id)
        assert result.name == f"{session_id}-snapshot.json"

    def test_empty_session_id(self) -> None:
        """Test path construction with empty session ID."""
        result = get_snapshot_file("")
        assert result.name == "-snapshot.json"

    def test_special_characters_session_id(self) -> None:
        """Test path construction with special characters in session ID."""
        result = get_snapshot_file("session_with-special.chars")
        assert result.name == "session_with-special.chars-snapshot.json"

    def test_returns_path_object(self) -> None:
        """Test that function returns a Path object."""
        result = get_snapshot_file("test")
        assert isinstance(result, Path)

    def test_consistent_parent_directory(self) -> None:
        """Test that all snapshots go to the same parent directory."""
        result1 = get_snapshot_file("session1")
        result2 = get_snapshot_file("session2")
        assert result1.parent == result2.parent


# =============================================================================
# Tests for validate_transcript_path()
# =============================================================================


class TestValidateTranscriptPath:
    """Tests for validate_transcript_path function."""

    @pytest.mark.usefixtures("mock_home")
    def test_valid_claude_directory(self, tmp_claude_dir: Path) -> None:
        """Test valid path within ~/.claude directory."""
        test_file = tmp_claude_dir / "transcript.jsonl"
        test_file.touch()
        result = validate_transcript_path(str(test_file))
        assert result is True

    def test_valid_tmp_claude_directory(self) -> None:
        """Test valid path within /tmp/claude directory."""
        # Create temp file in /tmp/claude
        tmp_claude = Path("/tmp/claude")
        tmp_claude.mkdir(parents=True, exist_ok=True)
        test_file = tmp_claude / "test_transcript.jsonl"
        test_file.touch()
        try:
            result = validate_transcript_path(str(test_file))
            assert result is True
        finally:
            test_file.unlink(missing_ok=True)

    def test_invalid_path_outside_allowed(self, tmp_path: Path) -> None:
        """Test path outside allowed directories returns False."""
        test_file = tmp_path / "transcript.jsonl"
        test_file.touch()
        result = validate_transcript_path(str(test_file))
        assert result is False

    def test_empty_path(self) -> None:
        """Test empty path returns False."""
        assert validate_transcript_path("") is False
        assert validate_transcript_path(None) is False

    def test_path_traversal_attempt(self, tmp_path: Path) -> None:
        """Test path traversal attempts to escape allowed directories are rejected.

        Note: The validation resolves symlinks and checks the resolved path.
        A path that escapes to an unauthorized location should be rejected.
        """
        # Path that is completely outside allowed directories
        traversal_path = str(tmp_path / "evil" / "path" / "file.jsonl")
        result = validate_transcript_path(traversal_path)
        assert result is False

    def test_path_outside_home_claude(self) -> None:
        """Test that paths outside ~/.claude and /tmp/claude are rejected."""
        # A random path not in allowed directories
        result = validate_transcript_path("/var/log/some_file.jsonl")
        assert result is False

    @pytest.mark.usefixtures("mock_home")
    def test_symlinked_subdirectory(self, tmp_path: Path) -> None:
        """Test symlinked subdirectories are handled correctly."""
        # Create the .claude directory
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)

        # Create a target directory outside .claude
        target_dir = tmp_path / "dotfiles" / ".claude" / "projects"
        target_dir.mkdir(parents=True)
        target_file = target_dir / "transcript.jsonl"
        target_file.touch()

        # Create symlink from .claude/projects to the target
        symlink_path = claude_dir / "projects"
        symlink_path.symlink_to(target_dir)

        # The path through the symlink should be valid
        path_via_symlink = symlink_path / "transcript.jsonl"
        result = validate_transcript_path(str(path_via_symlink))
        assert result is True

    def test_nonexistent_path(self, mock_home: Any) -> None:
        """Test nonexistent path - validation is about path structure, not existence."""
        nonexistent = mock_home / ".claude" / "nonexistent" / "file.jsonl"
        result = validate_transcript_path(str(nonexistent))
        # Path structure is valid even if file doesn't exist
        assert result is True


# =============================================================================
# Tests for normalize_task_description()
# =============================================================================


class TestNormalizeTaskDescription:
    """Tests for normalize_task_description function."""

    def test_lowercase_conversion(self) -> None:
        """Test that text is converted to lowercase."""
        assert normalize_task_description("Create NEW Feature") == "create new feature"

    def test_whitespace_stripping(self) -> None:
        """Test that leading/trailing whitespace is stripped."""
        assert normalize_task_description("  task  ") == "task"

    def test_whitespace_collapsing(self) -> None:
        """Test that multiple whitespaces are collapsed to single space."""
        result = normalize_task_description("task   with    multiple   spaces")
        assert result == "task with multiple spaces"

    def test_commit_and_push_normalization(self) -> None:
        """Test normalization of commit and push variations."""
        assert "commit and push" in normalize_task_description("commit and push changes")
        assert "commit and push" in normalize_task_description("commit and push to main")

    def test_fix_issue_normalization(self) -> None:
        """Test normalization of fix issue variations."""
        assert "fix issue" in normalize_task_description("fix the issue")
        assert "fix issue" in normalize_task_description("fix issues")
        assert "fix issue" in normalize_task_description("fix the issues")

    def test_update_normalization(self) -> None:
        """Test normalization of update variations."""
        result = normalize_task_description("update the README")
        assert "update readme" in result

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert normalize_task_description("") == ""

    def test_preserves_content(self) -> None:
        """Test that core content is preserved after normalization."""
        result = normalize_task_description("Implement user authentication")
        assert "implement user authentication" == result

    def test_combined_normalizations(self) -> None:
        """Test multiple normalizations applied together."""
        result = normalize_task_description("  FIX   the ISSUE   and   commit  ")
        assert "fix issue" in result


# =============================================================================
# Tests for _is_code_block()
# =============================================================================


class TestIsCodeBlock:
    """Tests for _is_code_block function.

    The function checks if text:
    1. Starts with ``` (after stripping)
    2. Starts with 4 spaces (after stripping) - which means it never matches
       since strip() removes leading spaces
    3. Contains { and } and : (JSON-like)
    """

    def test_markdown_code_block(self) -> None:
        """Test detection of markdown code block with triple backticks."""
        assert _is_code_block("```python\nprint('hello')\n```") is True
        assert _is_code_block("```\nsome code\n```") is True

    def test_indented_code_block_behavior(self) -> None:
        """Test that indented code detection works as implemented.

        Note: The implementation checks text.strip().startswith("    "),
        which means indented text never matches because strip() removes
        leading whitespace. This tests the actual behavior.
        """
        # After strip(), the text no longer starts with spaces
        # So this returns False based on actual implementation
        assert _is_code_block("    def foo():\n        pass") is False
        # But text that literally starts with backticks after strip works
        assert _is_code_block("  ```python") is True

    def test_json_like_content(self) -> None:
        """Test detection of JSON-like content (has {, }, and :)."""
        assert _is_code_block('{"key": "value"}') is True
        # Single quotes with colon also matches
        assert _is_code_block("{'key': 'value'}") is True

    def test_regular_prose(self) -> None:
        """Test that regular prose is not detected as code."""
        assert _is_code_block("This is a regular sentence.") is False
        assert _is_code_block("I decided to use Python for this task.") is False

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert _is_code_block("") is False

    def test_whitespace_only(self) -> None:
        """Test whitespace-only string."""
        assert _is_code_block("   ") is False

    def test_json_like_requires_all_three(self) -> None:
        """Test that JSON-like detection requires {, }, AND :."""
        # Has braces but no colon
        assert _is_code_block("{param}") is False
        # Has colon and one brace
        assert _is_code_block("key: {value") is False
        # Has all three
        assert _is_code_block("{key: value}") is True


# =============================================================================
# Tests for _looks_like_code()
# =============================================================================


class TestLooksLikeCode:
    """Tests for _looks_like_code function.

    The function counts these indicators (requires 2+):
    - text.count("{") > 1  (more than one {)
    - text.count("}") > 1  (more than one })
    - text.count("(") > 2  (more than two ()
    - text.count(")") > 2  (more than two ))
    - text.count(";") > 1  (more than one ;)
    - text.count("import ") > 0  (contains "import ")
    - text.count("def ") > 0  (contains "def ")
    - text.count("class ") > 0  (contains "class ")
    - text.startswith("#")  (starts with #)
    - text.startswith("//")  (starts with //)
    """

    def test_python_code_with_multiple_indicators(self) -> None:
        """Test detection of Python-like code with 2+ indicators."""
        # "def " (1 indicator) + "import " (1 indicator) = 2 indicators
        assert _looks_like_code("import os\ndef foo(): pass") is True
        # "class " (1) + "def " (1) = 2 indicators
        assert _looks_like_code("class MyClass:\n    def method(self): pass") is True

    def test_single_python_keyword_not_enough(self) -> None:
        """Test that single Python keyword is not enough."""
        # Only "def " = 1 indicator, needs 2+
        assert _looks_like_code("def foo(): pass") is False
        # Only "import " = 1 indicator
        assert _looks_like_code("import os") is False

    def test_javascript_code_with_multiple_indicators(self) -> None:
        """Test detection of JavaScript-like code."""
        # Multiple { and multiple } = 2 indicators
        assert _looks_like_code("function foo() { if (x) { return bar; } }") is True

    def test_multiple_braces(self) -> None:
        """Test detection based on multiple braces (>1 each)."""
        # More than one { AND more than one } = 2 indicators
        assert _looks_like_code("{{a}, {b}, {c}}") is True

    def test_multiple_parentheses(self) -> None:
        """Test detection based on multiple parentheses (>2 each)."""
        # More than two ( AND more than two ) = 2 indicators
        assert _looks_like_code("foo(bar(baz(qux(x))))") is True

    def test_semicolons_need_additional_indicator(self) -> None:
        """Test that semicolons alone need another indicator."""
        # More than one ; = 1 indicator, needs another
        assert _looks_like_code("a; b; c;") is False
        # More than one ; + more than two ( and ) = 3 indicators
        assert _looks_like_code("foo(); bar(); baz();") is True

    def test_comment_starting_needs_additional_indicator(self) -> None:
        """Test that starting with # or // needs another indicator."""
        # Starts with # = 1 indicator only
        assert _looks_like_code("# This is a comment") is False
        # Starts with # AND contains "def " = 2 indicators - this IS code
        assert _looks_like_code("# comment\ndef foo(): pass") is True
        # Starts with # and contains "import " = 2 indicators
        assert _looks_like_code("# test\nimport os") is True
        # Only starts with # = 1 indicator, not enough
        assert _looks_like_code("# test") is False

    def test_combined_indicators(self) -> None:
        """Test combinations of indicators."""
        # "import " + "def " = 2 indicators
        assert _looks_like_code("import foo\ndef bar(): pass") is True
        # "class " + "def " = 2 indicators
        assert _looks_like_code("class Foo:\n    def bar(): pass") is True

    def test_regular_prose(self) -> None:
        """Test that regular prose is not detected as code."""
        assert _looks_like_code("I decided to implement a new feature.") is False
        assert _looks_like_code("The approach is to use a queue.") is False

    def test_single_indicator(self) -> None:
        """Test that single indicator is not enough."""
        # Contains "class " but that's about class (noun), not keyword
        # Actually the function just counts occurrences of "class "
        assert _looks_like_code("The class discussion was interesting.") is False
        # Contains "import " = 1 indicator
        assert _looks_like_code("I will import the data.") is False

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        assert _looks_like_code("") is False

    def test_starts_with_hash(self) -> None:
        """Test text starting with # (Python comment)."""
        # Only starts with # = 1 indicator, not enough
        assert _looks_like_code("#comment") is False
        # Starts with # AND contains "import " = 2 indicators
        assert _looks_like_code("#comment\nimport os") is True

    def test_starts_with_double_slash(self) -> None:
        """Test text starting with // (C-style comment)."""
        # Only starts with // = 1 indicator, not enough
        assert _looks_like_code("// comment") is False


# =============================================================================
# Tests for extract_from_transcript() - Helper Functions
# =============================================================================


def create_jsonl_entry(entry_type: str, **kwargs: Any) -> str:
    """Helper to create JSONL entries."""
    entry: dict[str, Any] = {"type": entry_type}
    entry.update(kwargs)
    return json.dumps(entry)


def write_transcript(path: Path, entries: list[str]) -> None:
    """Write entries to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(entry + "\n")


# =============================================================================
# Tests for extract_from_transcript() - Tool Call Extraction
# =============================================================================


class TestExtractFromTranscriptToolCalls:
    """Tests for extract_from_transcript - tool call extraction."""

    def test_task_tool_extraction(self, tmp_path: Path) -> None:
        """Test extraction of Task tool calls (agent delegations)."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task-1",
                            "name": "Task",
                            "input": {
                                "subagent_type": "python-expert",
                                "description": "Implement feature X",
                                "prompt": "Create a Python module for feature X",
                            },
                        }
                    ]
                },
            ),
            create_jsonl_entry(
                "user",
                message={
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "task-1",
                            "content": "Task completed successfully",
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["task"] == "Implement feature X"
        assert result["tasks"][0]["status"] == "completed"
        assert result["tasks"][0]["agent"] == "python-expert"

    def test_todowrite_extraction(self, tmp_path: Path) -> None:
        """Test extraction of TodoWrite tool calls."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "todo-1",
                            "name": "TodoWrite",
                            "input": {
                                "todos": [
                                    {
                                        "content": "Implement authentication",
                                        "status": "completed",
                                    },
                                    {
                                        "content": "Write unit tests",
                                        "status": "in_progress",
                                    },
                                    {
                                        "content": "Update documentation",
                                        "status": "pending",
                                    },
                                ]
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["tasks"]) == 3
        statuses = {t["status"] for t in result["tasks"]}
        assert statuses == {"completed", "in_progress", "pending"}

    def test_edit_tool_file_tracking(self, tmp_path: Path) -> None:
        """Test extraction of file modifications from Edit tool."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "edit-1",
                            "name": "Edit",
                            "input": {
                                "file_path": "/home/user/project/main.py",
                                "old_string": "old",
                                "new_string": "new",
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert "/home/user/project/main.py" in result["files_modified"]

    def test_write_tool_file_tracking(self, tmp_path: Path) -> None:
        """Test extraction of file modifications from Write tool."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "write-1",
                            "name": "Write",
                            "input": {
                                "file_path": "/home/user/project/config.json",
                                "content": "{}",
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert "/home/user/project/config.json" in result["files_modified"]

    def test_file_paths_from_agent_results(self, tmp_path: Path) -> None:
        """Test extraction of file paths from agent tool results."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        agent_result = json.dumps({
            "result": "success",
            "files": [
                {"file_path": "/project/src/module.py"},
                {"file_path": "/project/tests/test_module.py"},
            ],
        })

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task-1",
                            "name": "Task",
                            "input": {
                                "subagent_type": "python-expert",
                                "description": "Create module",
                            },
                        }
                    ]
                },
            ),
            create_jsonl_entry(
                "user",
                message={
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "task-1",
                            "content": agent_result,
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert "/project/src/module.py" in result["files_modified"]
        assert "/project/tests/test_module.py" in result["files_modified"]


# =============================================================================
# Tests for extract_from_transcript() - Task Deduplication
# =============================================================================


class TestExtractFromTranscriptDeduplication:
    """Tests for extract_from_transcript - task deduplication."""

    def test_duplicate_tasks_normalized(self, tmp_path: Path) -> None:
        """Test that similar tasks are deduplicated."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "todo-1",
                            "name": "TodoWrite",
                            "input": {
                                "todos": [
                                    {"content": "Fix the issue", "status": "pending"},
                                    {"content": "fix issues", "status": "pending"},
                                ]
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        # Should deduplicate "Fix the issue" and "fix issues"
        assert len(result["tasks"]) == 1

    def test_todowrite_takes_priority(self, tmp_path: Path) -> None:
        """Test that TodoWrite tasks take priority over Task tool calls."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "todo-1",
                            "name": "TodoWrite",
                            "input": {
                                "todos": [
                                    {
                                        "content": "Implement feature",
                                        "status": "in_progress",
                                    },
                                ]
                            },
                        }
                    ]
                },
            ),
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task-1",
                            "name": "Task",
                            "input": {
                                "subagent_type": "python-expert",
                                "description": "Implement feature",
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        # Should have one task (deduplicated), status from TodoWrite
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["status"] == "in_progress"

    def test_task_limit(self, tmp_path: Path) -> None:
        """Test that tasks are limited to 10."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        todos = [{"content": f"Task {i}", "status": "pending"} for i in range(15)]
        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "todo-1",
                            "name": "TodoWrite",
                            "input": {"todos": todos},
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["tasks"]) == 10


# =============================================================================
# Tests for extract_from_transcript() - Decision Extraction
# =============================================================================


class TestExtractFromTranscriptDecisions:
    """Tests for extract_from_transcript - decision extraction."""

    def test_decision_extraction_will_use(self, tmp_path: Path) -> None:
        """Test extraction of 'I will use' pattern decisions."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "text",
                            "text": "I'll use pytest for testing because it has great fixtures support.",
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        # Should extract the decision about using pytest
        assert len(result["decisions"]) >= 1
        # The exact match depends on regex capture group
        decision_found = any("pytest" in d.lower() for d in result["decisions"])
        assert decision_found

    def test_decision_extraction_decided(self, tmp_path: Path) -> None:
        """Test extraction of 'decided' pattern decisions."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "I decided to use a factory pattern for "
                                "creating test data because it provides flexibility."
                            ),
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["decisions"]) >= 1

    def test_decisions_limited(self, tmp_path: Path) -> None:
        """Test that decisions are limited to 5."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        # Create multiple entries with decision patterns
        entries = []
        for i in range(10):
            entries.append(
                create_jsonl_entry(
                    "assistant",
                    message={
                        "content": [
                            {
                                "type": "text",
                                "text": f"I'll use approach {i} for the implementation because it is optimal.",
                            }
                        ]
                    },
                )
            )
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["decisions"]) <= 5

    def test_code_blocks_excluded_from_decisions(self, tmp_path: Path) -> None:
        """Test that code blocks are not searched for decisions."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "text",
                            "text": "```python\ndef decide():\n    # I'll use this pattern\n    pass\n```",
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        # Code blocks should be excluded from decision search
        assert len(result["decisions"]) == 0


# =============================================================================
# Tests for extract_from_transcript() - User Request Handling
# =============================================================================


class TestExtractFromTranscriptUserRequest:
    """Tests for extract_from_transcript - user request handling."""

    def test_last_user_request_extraction(self, tmp_path: Path) -> None:
        """Test extraction of last user request."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "user",
                message={"content": "First request"},
            ),
            create_jsonl_entry(
                "user",
                message={"content": "Second request"},
            ),
            create_jsonl_entry(
                "user",
                message={"content": "Last request"},
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert result["last_user_request"] == "Last request"

    def test_user_request_truncation(self, tmp_path: Path) -> None:
        """Test that long user requests are truncated."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        long_request = "x" * 300
        entries = [
            create_jsonl_entry(
                "user",
                message={"content": long_request},
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["last_user_request"]) == 200

    def test_user_content_as_list(self, tmp_path: Path) -> None:
        """Test handling of user content as list (structured format)."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "user",
                message={"content": [{"type": "text", "text": "User request via structured content"}]},
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert result["last_user_request"] == "User request via structured content"


# =============================================================================
# Tests for extract_from_transcript() - Current Focus
# =============================================================================


class TestExtractFromTranscriptCurrentFocus:
    """Tests for extract_from_transcript - current focus determination."""

    def test_current_focus_from_in_progress_task(self, tmp_path: Path) -> None:
        """Test that current focus is set from in_progress task."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "todo-1",
                            "name": "TodoWrite",
                            "input": {
                                "todos": [
                                    {"content": "Completed task", "status": "completed"},
                                    {
                                        "content": "Current active task",
                                        "status": "in_progress",
                                    },
                                    {"content": "Pending task", "status": "pending"},
                                ]
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert result["current_focus"] == "Current active task"

    def test_current_focus_fallback_to_user_request(self, tmp_path: Path) -> None:
        """Test that current focus falls back to last user request."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "user",
                message={"content": "Please help me with testing"},
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert result["current_focus"] == "Please help me with testing"


# =============================================================================
# Tests for extract_from_transcript() - Edge Cases
# =============================================================================


class TestExtractFromTranscriptEdgeCases:
    """Tests for extract_from_transcript - edge cases."""

    def test_empty_path(self) -> None:
        """Test handling of empty transcript path."""
        result = extract_from_transcript("")
        assert result["tasks"] == []
        assert result["files_modified"] == []
        assert result["decisions"] == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Test handling of nonexistent transcript file."""
        nonexistent = tmp_path / ".claude" / "nonexistent.jsonl"
        result = extract_from_transcript(str(nonexistent))
        assert result["tasks"] == []

    def test_invalid_json_lines(self, tmp_path: Path) -> None:
        """Test handling of invalid JSON lines in transcript."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        with open(transcript, "w") as f:
            f.write("invalid json line\n")
            f.write('{"type": "user", "message": {"content": "valid"}}\n')
            f.write("another invalid line\n")

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        # Should process valid lines and skip invalid ones
        assert result["last_user_request"] == "valid"

    def test_empty_transcript_file(self, tmp_path: Path) -> None:
        """Test handling of empty transcript file."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)
        transcript.touch()

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert result["tasks"] == []
        assert result["files_modified"] == []

    def test_large_file_rejected(self, tmp_path: Path) -> None:
        """Test that files exceeding MAX_TRANSCRIPT_SIZE are rejected."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        # Create a file larger than 10MB
        with open(transcript, "w") as f:
            f.write("x" * (11 * 1024 * 1024))

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert result["tasks"] == []

    def test_files_modified_limit(self, tmp_path: Path) -> None:
        """Test that files modified are limited to 10."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = []
        for i in range(15):
            entries.append(
                create_jsonl_entry(
                    "assistant",
                    message={
                        "content": [
                            {
                                "type": "tool_use",
                                "id": f"edit-{i}",
                                "name": "Edit",
                                "input": {
                                    "file_path": f"/project/file{i}.py",
                                    "old_string": "old",
                                    "new_string": "new",
                                },
                            }
                        ]
                    },
                )
            )
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["files_modified"]) == 10

    def test_task_without_prompt_or_description(self, tmp_path: Path) -> None:
        """Test Task tool call without prompt or description."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task-1",
                            "name": "Task",
                            "input": {
                                "subagent_type": "python-expert",
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["tasks"]) == 1
        assert "python-expert" in result["tasks"][0]["task"]

    def test_long_prompt_truncation(self, tmp_path: Path) -> None:
        """Test that long prompts are truncated with ellipsis."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        long_prompt = "x" * 300
        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task-1",
                            "name": "Task",
                            "input": {
                                "subagent_type": "python-expert",
                                "prompt": long_prompt,
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert len(result["tasks"]) == 1
        task_text = result["tasks"][0]["task"]
        assert len(task_text) == 203  # 200 chars + "..."
        assert task_text.endswith("...")


# =============================================================================
# Tests for extract_from_transcript() - Regex File Path Extraction
# =============================================================================


class TestExtractFromTranscriptRegexFilePaths:
    """Tests for extract_from_transcript - regex-based file path extraction."""

    def test_file_paths_from_non_json_content(self, tmp_path: Path) -> None:
        """Test extraction of file paths from non-JSON tool result content."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        # Non-JSON content with file_path pattern
        content = 'Successfully edited "file_path": "/project/src/main.py" with changes'

        entries = [
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task-1",
                            "name": "Task",
                            "input": {"subagent_type": "python-expert"},
                        }
                    ]
                },
            ),
            create_jsonl_entry(
                "user",
                message={
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "task-1",
                            "content": content,
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        assert "/project/src/main.py" in result["files_modified"]


# =============================================================================
# Tests for extract_from_transcript() - Complex Scenarios
# =============================================================================


class TestExtractFromTranscriptComplexScenarios:
    """Tests for extract_from_transcript - complex real-world scenarios."""

    def test_full_session_simulation(self, tmp_path: Path) -> None:
        """Test a realistic session with multiple tool calls and messages."""
        transcript = tmp_path / ".claude" / "transcript.jsonl"
        transcript.parent.mkdir(parents=True)

        entries = [
            # User request
            create_jsonl_entry(
                "user",
                message={"content": "Create a test suite for the auth module"},
            ),
            # TodoWrite to plan
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "text",
                            "text": "I'll implement a comprehensive test suite for the auth module.",
                        },
                        {
                            "type": "tool_use",
                            "id": "todo-1",
                            "name": "TodoWrite",
                            "input": {
                                "todos": [
                                    {
                                        "content": "Analyze auth module",
                                        "status": "completed",
                                    },
                                    {
                                        "content": "Write unit tests",
                                        "status": "in_progress",
                                    },
                                    {
                                        "content": "Write integration tests",
                                        "status": "pending",
                                    },
                                ]
                            },
                        },
                    ]
                },
            ),
            # Delegate to python-expert
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "task-1",
                            "name": "Task",
                            "input": {
                                "subagent_type": "python-expert",
                                "description": "Write unit tests for auth module",
                            },
                        }
                    ]
                },
            ),
            # Result with file modifications
            create_jsonl_entry(
                "user",
                message={
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "task-1",
                            "content": json.dumps({
                                "status": "success",
                                "files": [
                                    {"file_path": "/project/tests/test_auth.py"},
                                    {"file_path": "/project/tests/conftest.py"},
                                ],
                            }),
                        }
                    ]
                },
            ),
            # Edit call for fixtures
            create_jsonl_entry(
                "assistant",
                message={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "edit-1",
                            "name": "Edit",
                            "input": {
                                "file_path": "/project/tests/fixtures.py",
                                "old_string": "# placeholder",
                                "new_string": "# fixtures",
                            },
                        }
                    ]
                },
            ),
        ]
        write_transcript(transcript, entries)

        with patch("pre_compact_snapshot.validate_transcript_path", return_value=True):
            result = extract_from_transcript(str(transcript))

        # Verify tasks
        assert len(result["tasks"]) >= 3  # From TodoWrite

        # Verify files modified
        assert "/project/tests/test_auth.py" in result["files_modified"]
        assert "/project/tests/conftest.py" in result["files_modified"]
        assert "/project/tests/fixtures.py" in result["files_modified"]

        # Verify current focus (should be in_progress task)
        assert "Write unit tests" in result["current_focus"]

        # Verify last user request
        assert "test suite" in result["last_user_request"].lower()

        # Verify decisions were extracted
        assert len(result["decisions"]) >= 1


# =============================================================================
# Run pytest if executed directly
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
