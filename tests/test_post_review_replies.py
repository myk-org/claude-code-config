"""Comprehensive unit tests for reviews post module.

This test suite covers:
- check_dependencies() validation
- JSON file validation and parsing
- Status handling (addressed, skipped, pending, failed, not_addressed)
- Thread ID lookup from node_id
- Reply message generation based on status
- Should-resolve logic for human vs AI reviews
- Atomic JSON updates
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from myk_claude_tools.reviews import post as post_review_replies

# =============================================================================
# Tests for check_dependencies()
# =============================================================================


class TestCheckDependencies:
    """Tests for check_dependencies() validation."""

    @patch("shutil.which")
    def test_gh_available(self, mock_which: Any) -> None:
        """Available gh should not exit."""
        mock_which.return_value = "/usr/bin/gh"

        # Should not raise
        post_review_replies.check_dependencies()

        mock_which.assert_called_with("gh")

    @patch("shutil.which")
    def test_gh_not_available(self, mock_which: Any) -> None:
        """Missing gh should exit with error."""
        mock_which.return_value = None

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.check_dependencies()

        assert excinfo.value.code == 1


# =============================================================================
# Tests for run_graphql()
# =============================================================================


class TestRunGraphql:
    """Tests for run_graphql() GraphQL execution."""

    @patch("subprocess.run")
    def test_successful_query(self, mock_run: Any) -> None:
        """Successful GraphQL query should return (True, data)."""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"data": {"test": "value"}}', stderr="")

        success, result = post_review_replies.run_graphql("query { test }", {})

        assert success is True
        assert result == {"data": {"test": "value"}}

    @patch("subprocess.run")
    def test_failed_query_returns_false(self, mock_run: Any) -> None:
        """Failed GraphQL query should return (False, error_string)."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")

        success, result = post_review_replies.run_graphql("query { test }", {})

        assert success is False
        assert "auth error" in str(result)

    @patch("subprocess.run")
    def test_invalid_json_response(self, mock_run: Any) -> None:
        """Invalid JSON response should return (False, error_string)."""
        mock_run.return_value = MagicMock(returncode=0, stdout="not valid json", stderr="")

        success, _ = post_review_replies.run_graphql("query { test }", {})

        assert success is False

    @patch("subprocess.run")
    def test_graphql_errors_in_response(self, mock_run: Any) -> None:
        """GraphQL errors in response should return (False, error_message)."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"errors": [{"message": "Field not found"}], "data": null}',
            stderr="",
        )

        success, result = post_review_replies.run_graphql("query { test }", {})

        assert success is False
        assert "Field not found" in str(result)

    @patch("subprocess.run")
    def test_variables_passed_via_stdin(self, mock_run: Any) -> None:
        """Variables should be passed via stdin as JSON payload."""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"data": {}}', stderr="")

        variables = {"key1": "value1", "key2": "value with spaces"}
        post_review_replies.run_graphql("query", variables)

        # New implementation uses --input - to pass JSON payload via stdin
        call_args = mock_run.call_args[0][0]
        assert "--input" in call_args
        assert "-" in call_args


# =============================================================================
# Tests for post_thread_reply()
# =============================================================================


class TestPostThreadReply:
    """Tests for post_thread_reply() reply posting."""

    @patch.object(post_review_replies, "run_graphql")
    def test_successful_reply(self, mock_graphql: Any) -> None:
        """Successful reply should return True."""
        mock_graphql.return_value = (True, {"data": {"addPullRequestReviewThreadReply": {"comment": {"id": "c1"}}}})

        result = post_review_replies.post_thread_reply("thread123", "Reply body")

        assert result is True

    @patch.object(post_review_replies, "run_graphql")
    def test_failed_reply(self, mock_graphql: Any) -> None:
        """Failed reply should return False."""
        mock_graphql.return_value = (False, "Error posting")

        result = post_review_replies.post_thread_reply("thread123", "Reply body")

        assert result is False

    @patch.object(post_review_replies, "run_graphql")
    def test_truncates_long_body(self, mock_graphql: Any) -> None:
        """Long body should be truncated."""
        mock_graphql.return_value = (True, {"data": {}})

        long_body = "x" * 70000

        post_review_replies.post_thread_reply("thread123", long_body)

        # Check that body was truncated
        call_args = mock_graphql.call_args
        passed_body = call_args[0][1]["body"]
        assert len(passed_body) <= 60000 + len("\n...[truncated]")
        assert passed_body.endswith("...[truncated]")


# =============================================================================
# Tests for resolve_thread()
# =============================================================================


class TestResolveThread:
    """Tests for resolve_thread() thread resolution."""

    @patch.object(post_review_replies, "run_graphql")
    def test_successful_resolve(self, mock_graphql: Any) -> None:
        """Successful resolve should return True."""
        mock_graphql.return_value = (
            True,
            {"data": {"resolveReviewThread": {"thread": {"id": "t1", "isResolved": True}}}},
        )

        result = post_review_replies.resolve_thread("thread123")

        assert result is True

    @patch.object(post_review_replies, "run_graphql")
    def test_failed_resolve(self, mock_graphql: Any) -> None:
        """Failed resolve should return False."""
        mock_graphql.return_value = (False, "Error resolving")

        result = post_review_replies.resolve_thread("thread123")

        assert result is False


# =============================================================================
# Tests for lookup_thread_id_from_node_id()
# =============================================================================


class TestLookupThreadIdFromNodeId:
    """Tests for lookup_thread_id_from_node_id() thread ID lookup."""

    @patch.object(post_review_replies, "run_graphql")
    def test_successful_lookup(self, mock_graphql: Any) -> None:
        """Successful lookup should return thread_id."""
        mock_graphql.return_value = (
            True,
            {"data": {"node": {"pullRequestReviewThread": {"id": "thread_abc"}}}},
        )

        result = post_review_replies.lookup_thread_id_from_node_id("node123")

        assert result == "thread_abc"

    @patch.object(post_review_replies, "run_graphql")
    def test_failed_lookup(self, mock_graphql: Any) -> None:
        """Failed lookup should return None."""
        mock_graphql.return_value = (False, "Error looking up")

        result = post_review_replies.lookup_thread_id_from_node_id("node123")

        assert result is None

    @patch.object(post_review_replies, "run_graphql")
    def test_missing_thread_id(self, mock_graphql: Any) -> None:
        """Missing thread ID in response should return None."""
        mock_graphql.return_value = (True, {"data": {"node": None}})

        result = post_review_replies.lookup_thread_id_from_node_id("node123")

        assert result is None

    @patch.object(post_review_replies, "run_graphql")
    def test_non_dict_response(self, mock_graphql: Any) -> None:
        """Non-dict response should return None."""
        mock_graphql.return_value = (True, "not a dict")

        result = post_review_replies.lookup_thread_id_from_node_id("node123")

        assert result is None

    @patch.object(post_review_replies, "run_graphql")
    def test_empty_thread_id(self, mock_graphql: Any) -> None:
        """Empty thread ID should return None."""
        mock_graphql.return_value = (
            True,
            {"data": {"node": {"pullRequestReviewThread": {"id": ""}}}},
        )

        result = post_review_replies.lookup_thread_id_from_node_id("node123")

        assert result is None


# =============================================================================
# Tests for get_utc_timestamp()
# =============================================================================


class TestGetUtcTimestamp:
    """Tests for get_utc_timestamp() timestamp generation."""

    def test_returns_iso_format(self) -> None:
        """Timestamp should be in ISO format."""
        result = post_review_replies.get_utc_timestamp()

        # Should match pattern like 2024-01-15T10:30:45Z
        assert len(result) == 20
        assert result.endswith("Z")
        assert "T" in result

    def test_contains_date_parts(self) -> None:
        """Timestamp should contain date parts."""
        result = post_review_replies.get_utc_timestamp()

        # Should have year-month-day format
        parts = result.split("T")[0].split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # Year
        assert len(parts[1]) == 2  # Month
        assert len(parts[2]) == 2  # Day


# =============================================================================
# Tests for apply_updates_to_json()
# =============================================================================


class TestApplyUpdatesToJson:
    """Tests for apply_updates_to_json() atomic updates."""

    def test_empty_updates(self, tmp_path: Path) -> None:
        """Empty updates should not modify file."""
        json_path = tmp_path / "reviews.json"
        data = {"human": [{"status": "pending"}]}
        json_path.write_text(json.dumps(data))

        post_review_replies.apply_updates_to_json(json_path, [])

        # File should be unchanged
        result = json.loads(json_path.read_text())
        assert result == data

    def test_applies_updates(self, tmp_path: Path) -> None:
        """Updates should be applied to JSON."""
        json_path = tmp_path / "reviews.json"
        data = {"human": [{"status": "pending"}], "qodo": [], "coderabbit": []}
        json_path.write_text(json.dumps(data))

        updates = [{"cat": "human", "idx": 0, "field": "posted_at", "ts": "2024-01-15T10:00:00Z"}]

        post_review_replies.apply_updates_to_json(json_path, updates)

        result = json.loads(json_path.read_text())
        assert result["human"][0]["posted_at"] == "2024-01-15T10:00:00Z"

    def test_applies_multiple_updates(self, tmp_path: Path) -> None:
        """Multiple updates should all be applied."""
        json_path = tmp_path / "reviews.json"
        data = {"human": [{"status": "pending"}, {"status": "pending"}], "qodo": [], "coderabbit": []}
        json_path.write_text(json.dumps(data))

        updates = [
            {"cat": "human", "idx": 0, "field": "posted_at", "ts": "2024-01-15T10:00:00Z"},
            {"cat": "human", "idx": 1, "field": "resolved_at", "ts": "2024-01-15T11:00:00Z"},
        ]

        post_review_replies.apply_updates_to_json(json_path, updates)

        result = json.loads(json_path.read_text())
        assert result["human"][0]["posted_at"] == "2024-01-15T10:00:00Z"
        assert result["human"][1]["resolved_at"] == "2024-01-15T11:00:00Z"


# =============================================================================
# Tests for main() - Status Handling
# =============================================================================


class TestMainStatusHandling:
    """Tests for main() status handling logic."""

    def _create_test_json(self, tmp_path: Path, threads: dict[str, list[dict[str, Any]]]) -> Path:
        """Helper to create test JSON file."""
        json_path = tmp_path / "reviews.json"
        data = {
            "metadata": {"owner": "test-owner", "repo": "test-repo", "pr_number": "123"},
            **threads,
        }
        json_path.write_text(json.dumps(data))
        return json_path

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_addressed_status_posts_and_resolves(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path
    ) -> None:
        """Addressed status should post reply and resolve."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [{"thread_id": "t1", "status": "addressed", "reply": "Fixed", "path": "file.py"}],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 0
        mock_post.assert_called_once()
        mock_resolve.assert_called_once()

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_pending_status_skipped(self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path) -> None:
        """Pending status should be skipped."""
        del mock_deps  # Injected by @patch decorator, unused in test
        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [{"thread_id": "t1", "status": "pending", "path": "file.py"}],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 0
        mock_post.assert_not_called()
        mock_resolve.assert_not_called()

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_skipped_status_posts_and_resolves_ai(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path
    ) -> None:
        """Skipped status for AI should post skip reason and resolve."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [],
                "qodo": [{"thread_id": "t1", "status": "skipped", "skip_reason": "Not applicable", "path": "file.py"}],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 0
        mock_post.assert_called_once()
        mock_resolve.assert_called_once()

        # Check that skip reason was included in reply
        call_args = mock_post.call_args
        body = call_args[0][1]
        assert "Not applicable" in body

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_human_skipped_not_resolved(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path
    ) -> None:
        """Human skipped status should post but NOT resolve."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [
                    {"thread_id": "t1", "status": "skipped", "skip_reason": "Will address later", "path": "file.py"}
                ],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 0
        mock_post.assert_called_once()
        mock_resolve.assert_not_called()

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_not_addressed_human_not_resolved(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path
    ) -> None:
        """Human not_addressed status should post but NOT resolve."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [{"thread_id": "t1", "status": "not_addressed", "reply": "Cannot fix now", "path": "file.py"}],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 0
        mock_post.assert_called_once()
        mock_resolve.assert_not_called()


# =============================================================================
# Tests for main() - Thread ID Resolution
# =============================================================================


class TestMainThreadIdResolution:
    """Tests for main() thread ID resolution logic."""

    def _create_test_json(self, tmp_path: Path, threads: dict[str, list[dict[str, Any]]]) -> Path:
        """Helper to create test JSON file."""
        json_path = tmp_path / "reviews.json"
        data = {
            "metadata": {"owner": "test-owner", "repo": "test-repo", "pr_number": "123"},
            **threads,
        }
        json_path.write_text(json.dumps(data))
        return json_path

    @patch.object(post_review_replies, "lookup_thread_id_from_node_id")
    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_uses_thread_id_first(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, mock_lookup: Any, tmp_path: Path
    ) -> None:
        """Thread ID should be used if available."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [
                    {
                        "thread_id": "real_thread_id",
                        "node_id": "node123",
                        "status": "addressed",
                        "reply": "Fixed",
                        "path": "file.py",
                    }
                ],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        # Should use thread_id directly, not look up from node_id
        mock_lookup.assert_not_called()
        call_args = mock_post.call_args
        assert call_args[0][0] == "real_thread_id"

    @patch.object(post_review_replies, "lookup_thread_id_from_node_id")
    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_falls_back_to_node_id(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, mock_lookup: Any, tmp_path: Path
    ) -> None:
        """Should look up thread_id from node_id if thread_id missing."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True
        mock_lookup.return_value = "looked_up_thread_id"

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [
                    {
                        "thread_id": None,
                        "node_id": "node123",
                        "status": "addressed",
                        "reply": "Fixed",
                        "path": "file.py",
                    }
                ],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        mock_lookup.assert_called_once_with("node123")
        call_args = mock_post.call_args
        assert call_args[0][0] == "looked_up_thread_id"

    @patch.object(post_review_replies, "lookup_thread_id_from_node_id")
    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_skips_when_no_thread_id(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, mock_lookup: Any, tmp_path: Path
    ) -> None:
        """Should skip thread when no thread_id can be resolved."""
        del mock_deps, mock_resolve  # Injected by @patch decorator, unused in test
        mock_lookup.return_value = None

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [
                    {
                        "thread_id": None,
                        "node_id": None,
                        "status": "addressed",
                        "reply": "Fixed",
                        "path": "file.py",
                    }
                ],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        mock_post.assert_not_called()


# =============================================================================
# Tests for main() - Reply Message Generation
# =============================================================================


class TestMainReplyMessageGeneration:
    """Tests for main() reply message generation."""

    def _create_test_json(self, tmp_path: Path, threads: dict[str, list[dict[str, Any]]]) -> Path:
        """Helper to create test JSON file."""
        json_path = tmp_path / "reviews.json"
        data = {
            "metadata": {"owner": "test-owner", "repo": "test-repo", "pr_number": "123"},
            **threads,
        }
        json_path.write_text(json.dumps(data))
        return json_path

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_addressed_uses_reply(self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path) -> None:
        """Addressed status should use reply field."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [
                    {"thread_id": "t1", "status": "addressed", "reply": "Custom reply message", "path": "file.py"}
                ],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        call_args = mock_post.call_args
        assert call_args[0][1] == "Custom reply message"

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_addressed_default_message(self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path) -> None:
        """Addressed without reply should use default message."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [{"thread_id": "t1", "status": "addressed", "reply": "", "path": "file.py"}],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        call_args = mock_post.call_args
        assert call_args[0][1] == "Addressed."

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_skipped_uses_skip_reason(self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path) -> None:
        """Skipped status should format skip reason."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [],
                "qodo": [{"thread_id": "t1", "status": "skipped", "skip_reason": "Out of scope", "path": "file.py"}],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        call_args = mock_post.call_args
        assert call_args[0][1] == "Skipped: Out of scope"

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_skipped_uses_reply_when_no_reason(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path
    ) -> None:
        """Skipped without skip_reason should use reply field."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [],
                "qodo": [
                    {
                        "thread_id": "t1",
                        "status": "skipped",
                        "skip_reason": "",
                        "reply": "Using reply",
                        "path": "file.py",
                    }
                ],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        call_args = mock_post.call_args
        assert call_args[0][1] == "Using reply"


# =============================================================================
# Tests for main() - Input Validation
# =============================================================================


class TestMainInputValidation:
    """Tests for main() input validation."""

    @patch.object(post_review_replies, "check_dependencies")
    def test_missing_json_file(self, mock_deps: Any, tmp_path: Path) -> None:
        """Missing JSON file should exit with error."""
        del mock_deps  # Injected by @patch decorator, unused in test
        json_path = tmp_path / "nonexistent.json"

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 1

    @patch.object(post_review_replies, "check_dependencies")
    def test_invalid_json_file(self, mock_deps: Any, tmp_path: Path) -> None:
        """Invalid JSON should exit with error."""
        del mock_deps  # Injected by @patch decorator, unused in test
        json_path = tmp_path / "invalid.json"
        json_path.write_text("not valid json {{{")

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 1

    @patch.object(post_review_replies, "check_dependencies")
    def test_missing_metadata(self, mock_deps: Any, tmp_path: Path) -> None:
        """Missing metadata should exit with error."""
        del mock_deps  # Injected by @patch decorator, unused in test
        json_path = tmp_path / "reviews.json"
        json_path.write_text('{"human": [], "qodo": [], "coderabbit": []}')

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 1

    @patch.object(post_review_replies, "check_dependencies")
    def test_missing_owner(self, mock_deps: Any, tmp_path: Path) -> None:
        """Missing owner in metadata should exit with error."""
        del mock_deps  # Injected by @patch decorator, unused in test
        json_path = tmp_path / "reviews.json"
        data = {
            "metadata": {"repo": "test-repo", "pr_number": "123"},
            "human": [],
            "qodo": [],
            "coderabbit": [],
        }
        json_path.write_text(json.dumps(data))

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 1

    @patch.object(post_review_replies, "check_dependencies")
    def test_empty_path_argument(self, mock_deps: Any) -> None:
        """Empty path should exit with error."""
        del mock_deps  # Injected by @patch decorator, unused in test
        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run("")  # Empty path triggers validation error

        # Empty path fails file validation
        assert excinfo.value.code == 1


# =============================================================================
# Tests for main() - Already Posted Handling
# =============================================================================


class TestMainAlreadyPostedHandling:
    """Tests for main() already posted thread handling."""

    def _create_test_json(self, tmp_path: Path, threads: dict[str, list[dict[str, Any]]]) -> Path:
        """Helper to create test JSON file."""
        json_path = tmp_path / "reviews.json"
        data = {
            "metadata": {"owner": "test-owner", "repo": "test-repo", "pr_number": "123"},
            **threads,
        }
        json_path.write_text(json.dumps(data))
        return json_path

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_skips_already_posted(self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path) -> None:
        """Already posted threads should be skipped."""
        del mock_deps  # Injected by @patch decorator, unused in test
        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [
                    {
                        "thread_id": "t1",
                        "status": "addressed",
                        "reply": "Fixed",
                        "posted_at": "2024-01-15T10:00:00Z",
                        "resolved_at": "2024-01-15T10:00:00Z",
                        "path": "file.py",
                    }
                ],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        mock_post.assert_not_called()
        mock_resolve.assert_not_called()

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_retries_resolve_only(self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path) -> None:
        """Posted but not resolved should retry resolve only."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [
                    {
                        "thread_id": "t1",
                        "status": "addressed",
                        "reply": "Fixed",
                        "posted_at": "2024-01-15T10:00:00Z",
                        "resolved_at": "",
                        "path": "file.py",
                    }
                ],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        # Should not post again, only resolve
        mock_post.assert_not_called()
        mock_resolve.assert_called_once()

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_human_posted_not_resolved_skipped(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path
    ) -> None:
        """Human thread posted but not resolved (by policy) should be skipped."""
        del mock_deps  # Injected by @patch decorator, unused in test
        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [
                    {
                        "thread_id": "t1",
                        "status": "skipped",
                        "reply": "Will address later",
                        "posted_at": "2024-01-15T10:00:00Z",
                        "resolved_at": "",
                        "path": "file.py",
                    }
                ],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        # Should not post or resolve (already posted, not resolving by policy)
        mock_post.assert_not_called()
        mock_resolve.assert_not_called()


# =============================================================================
# Tests for edge cases
# =============================================================================


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def _create_test_json(self, tmp_path: Path, threads: dict[str, list[dict[str, Any]]]) -> Path:
        """Helper to create test JSON file."""
        json_path = tmp_path / "reviews.json"
        data = {
            "metadata": {"owner": "test-owner", "repo": "test-repo", "pr_number": "123"},
            **threads,
        }
        json_path.write_text(json.dumps(data))
        return json_path

    @patch.object(post_review_replies, "check_dependencies")
    def test_empty_threads(self, mock_deps: Any, tmp_path: Path) -> None:
        """Empty thread arrays should exit successfully."""
        del mock_deps  # Injected by @patch decorator, unused in test
        json_path = self._create_test_json(
            tmp_path,
            {"human": [], "qodo": [], "coderabbit": []},
        )

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 0

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_unknown_status_skipped(self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path) -> None:
        """Unknown status should be skipped with warning."""
        del mock_deps, mock_resolve  # Injected by @patch decorator, unused in test
        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [{"thread_id": "t1", "status": "unknown_status", "reply": "Test", "path": "file.py"}],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        mock_post.assert_not_called()

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_failed_post_counted(self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path) -> None:
        """Failed post should increment fail count and exit with error."""
        del mock_deps, mock_resolve  # Injected by @patch decorator, unused in test
        mock_post.return_value = False

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [{"thread_id": "t1", "status": "addressed", "reply": "Fixed", "path": "file.py"}],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 1

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_thread_id_null_string_handled(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path
    ) -> None:
        """Thread ID as literal 'null' string should be handled."""
        del mock_deps  # Injected by @patch decorator, unused in test
        mock_post.return_value = True
        mock_resolve.return_value = True

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [],
                "qodo": [],
                "coderabbit": [
                    {
                        "thread_id": "null",
                        "node_id": None,
                        "status": "addressed",
                        "reply": "Fixed",
                        "path": "file.py",
                    }
                ],
            },
        )

        with pytest.raises(SystemExit):
            post_review_replies.run(str(json_path))

        # Should skip - "null" string is treated as invalid
        mock_post.assert_not_called()

    @patch.object(post_review_replies, "resolve_thread")
    @patch.object(post_review_replies, "post_thread_reply")
    @patch.object(post_review_replies, "check_dependencies")
    def test_failed_post_prints_retry_instruction_to_stdout(
        self, mock_deps: Any, mock_post: Any, mock_resolve: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Failed posts should print retry instruction to stdout."""
        del mock_deps, mock_resolve  # Injected by @patch decorator, unused in test
        mock_post.return_value = False

        json_path = self._create_test_json(
            tmp_path,
            {
                "human": [{"thread_id": "t1", "status": "addressed", "reply": "Fixed", "path": "file.py"}],
                "qodo": [],
                "coderabbit": [],
            },
        )

        with pytest.raises(SystemExit) as excinfo:
            post_review_replies.run(str(json_path))

        assert excinfo.value.code == 1

        captured = capsys.readouterr()
        assert "ACTION REQUIRED" in captured.out
        assert "myk-claude-tools reviews post" in captured.out
        assert str(json_path) in captured.out
        assert "Failed:" in captured.err
        assert "Failed:" not in captured.out
