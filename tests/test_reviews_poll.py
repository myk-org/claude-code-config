"""Unit tests for reviews poll module.

This test suite covers:
- run() with no rate limit detected (proceeds straight to fetch)
- run() with rate limit detected (waits + triggers + fetches)
- run() with rate limit but unparseable wait time (uses default)
- run() with no summary comment found (proceeds to fetch)
- run() with trigger failure (still proceeds to fetch)
- run() with API error in summary comment lookup
- _RATE_LIMIT_BUFFER_SECONDS constant value
"""

from __future__ import annotations

from unittest.mock import patch

from myk_claude_tools.coderabbit.rate_limit import (
    _RATE_LIMITED_MARKER,
    _SUMMARY_MARKER,
)
from myk_claude_tools.reviews.poll import (
    _RATE_LIMIT_BUFFER_SECONDS,
    run,
)

# =============================================================================
# Sample comment bodies for testing
# =============================================================================

RATE_LIMITED_BODY = (
    f"{_SUMMARY_MARKER}\n"
    f"{_RATE_LIMITED_MARKER}\n"
    "Please wait **3 minutes and 30 seconds** before requesting another review.\n"
)

NOT_RATE_LIMITED_BODY = f"{_SUMMARY_MARKER}\nThis is a normal summary comment.\n"

RATE_LIMITED_NO_TIME_BODY = (
    f"{_SUMMARY_MARKER}\n{_RATE_LIMITED_MARKER}\nRate limit exceeded. No parseable wait time here.\n"
)


def _mock_find_summary(comment_id: int | None, body: str | None, error: str = "") -> object:
    """Create a side_effect function for _find_summary_comment that returns fixed values."""

    def _side_effect(_owner_repo: str, _pr_number: int) -> tuple[int | None, str | None, str]:
        return comment_id, body, error

    return _side_effect


# =============================================================================
# Tests for _RATE_LIMIT_BUFFER_SECONDS constant
# =============================================================================


class TestConstants:
    """Tests for module-level constants."""

    def test_buffer_seconds_value(self) -> None:
        """Buffer should be 30 seconds."""
        assert _RATE_LIMIT_BUFFER_SECONDS == 30


# =============================================================================
# Tests for run() - no rate limit
# =============================================================================


class TestRunNoRateLimit:
    """Tests for run() when CodeRabbit is NOT rate limited."""

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_rate_limit_proceeds_to_fetch(self, mock_pr_info: object, mock_find: object, mock_fetch: object) -> None:
        """When not rate limited, should skip trigger and go straight to fetch."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, NOT_RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        exit_code = run("https://github.com/owner/repo/pull/42")

        assert exit_code == 0
        mock_fetch.assert_called_once_with("https://github.com/owner/repo/pull/42")  # type: ignore[attr-defined]

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_rate_limit_does_not_call_trigger(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object
    ) -> None:
        """When not rate limited, run_trigger should not be called."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, NOT_RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        with patch("myk_claude_tools.coderabbit.rate_limit.run_trigger") as mock_trigger:
            run("https://github.com/owner/repo/pull/42")
            mock_trigger.assert_not_called()

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_returns_fetch_exit_code(self, mock_pr_info: object, mock_find: object, mock_fetch: object) -> None:
        """Should return the exit code from fetch_run."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, NOT_RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_fetch.return_value = 1  # type: ignore[attr-defined]

        exit_code = run()

        assert exit_code == 1


# =============================================================================
# Tests for run() - rate limited
# =============================================================================


class TestRunRateLimited:
    """Tests for run() when CodeRabbit IS rate limited."""

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit.run_trigger")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_rate_limited_calls_trigger_with_buffer(
        self, mock_pr_info: object, mock_find: object, mock_trigger: object, mock_fetch: object
    ) -> None:
        """When rate limited, should call run_trigger with wait_seconds + buffer."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_trigger.return_value = 0  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        # 3 minutes 30 seconds = 210 seconds + 30 buffer = 240
        mock_trigger.assert_called_once_with("owner/repo", 42, 240)  # type: ignore[attr-defined]

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit.run_trigger")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_rate_limited_still_fetches_after_trigger(
        self, mock_pr_info: object, mock_find: object, mock_trigger: object, mock_fetch: object
    ) -> None:
        """After trigger completes, should always proceed to fetch."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_trigger.return_value = 0  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        exit_code = run()

        assert exit_code == 0
        mock_fetch.assert_called_once()  # type: ignore[attr-defined]

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit.run_trigger")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_rate_limited_unparseable_wait_uses_default(
        self, mock_pr_info: object, mock_find: object, mock_trigger: object, mock_fetch: object
    ) -> None:
        """When rate limited but wait time is unparseable, should use 300s default."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, RATE_LIMITED_NO_TIME_BODY)  # type: ignore[attr-defined]
        mock_trigger.return_value = 0  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        # 300 default + 30 buffer = 330
        mock_trigger.assert_called_once_with("owner/repo", 42, 330)  # type: ignore[attr-defined]


# =============================================================================
# Tests for run() - no summary comment found
# =============================================================================


class TestRunNoComment:
    """Tests for run() when no CodeRabbit summary comment exists."""

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_comment_proceeds_to_fetch(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object, capsys: object
    ) -> None:
        """When no summary comment found (sentinel error), should proceed to fetch with friendly message."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(None, None, "No CodeRabbit summary comment found on this PR")  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        exit_code = run()

        assert exit_code == 0
        mock_fetch.assert_called_once()  # type: ignore[attr-defined]
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "No CodeRabbit summary comment found" in captured.err
        assert "Could not check rate limit" not in captured.err

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_comment_does_not_trigger(self, mock_pr_info: object, mock_find: object, mock_fetch: object) -> None:
        """When no summary comment, should not call trigger."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(None, None)  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        with patch("myk_claude_tools.coderabbit.rate_limit.run_trigger") as mock_trigger:
            run()
            mock_trigger.assert_not_called()

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_comment_with_error_still_fetches(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object
    ) -> None:
        """When no comment with API error, should log error and still fetch."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(None, None, "GitHub API error: Bad credentials")  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        exit_code = run()

        assert exit_code == 0
        mock_fetch.assert_called_once()  # type: ignore[attr-defined]

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_comment_with_error_logs_accurate_message(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object, capsys: object
    ) -> None:
        """When API error occurs, stderr should say 'Could not check rate limit', not 'No rate limit detected'."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(None, None, "GitHub API error: Bad credentials")  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "Could not check rate limit" in captured.err
        assert "GitHub API error: Bad credentials" in captured.err
        assert "Proceeding to fetch anyway" in captured.err
        # Must NOT contain the misleading old message
        assert "No rate limit detected" not in captured.err
        assert "No CodeRabbit summary comment found" not in captured.err

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_comment_without_error_logs_no_summary_message(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object, capsys: object
    ) -> None:
        """When no comment and no error, stderr should say 'No CodeRabbit summary comment found'."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(None, None)  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "No CodeRabbit summary comment found" in captured.err
        assert "Proceeding to fetch" in captured.err
        # Must NOT contain the error-case message or old misleading message
        assert "Could not check rate limit" not in captured.err
        assert "No rate limit detected" not in captured.err

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_comment_sentinel_logs_friendly_message(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object, capsys: object
    ) -> None:
        """When sentinel error from _find_summary_comment, should log friendly message, not error."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(None, None, "No CodeRabbit summary comment found on this PR")  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "No CodeRabbit summary comment found" in captured.err
        assert "Could not check rate limit" not in captured.err


# =============================================================================
# Tests for run() - trigger failure
# =============================================================================


class TestRunTriggerFailure:
    """Tests for run() when trigger returns non-zero."""

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit.run_trigger")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_trigger_failure_still_fetches(
        self, mock_pr_info: object, mock_find: object, mock_trigger: object, mock_fetch: object
    ) -> None:
        """When trigger returns non-zero, should still proceed to fetch."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_trigger.return_value = 1  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        exit_code = run()

        assert exit_code == 0
        mock_fetch.assert_called_once()  # type: ignore[attr-defined]


# =============================================================================
# Tests for run() - review_url parameter forwarding
# =============================================================================


class TestRunUrlForwarding:
    """Tests for run() passing review_url through the pipeline."""

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_review_url_forwarded_to_get_pr_info(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object
    ) -> None:
        """review_url should be forwarded to get_pr_info."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, NOT_RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run("https://github.com/owner/repo/pull/42#pullrequestreview-123")

        mock_pr_info.assert_called_once_with("https://github.com/owner/repo/pull/42#pullrequestreview-123")  # type: ignore[attr-defined]

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_review_url_forwarded_to_fetch_run(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object
    ) -> None:
        """review_url should be forwarded to fetch_run."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, NOT_RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run("https://github.com/owner/repo/pull/42#pullrequestreview-123")

        mock_fetch.assert_called_once_with("https://github.com/owner/repo/pull/42#pullrequestreview-123")  # type: ignore[attr-defined]

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_empty_review_url_defaults(self, mock_pr_info: object, mock_find: object, mock_fetch: object) -> None:
        """Empty review_url should pass empty string through."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, NOT_RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        mock_pr_info.assert_called_once_with("")  # type: ignore[attr-defined]
        mock_fetch.assert_called_once_with("")  # type: ignore[attr-defined]


# =============================================================================
# Tests for run() - stderr output verification
# =============================================================================


class TestRunStderrOutput:
    """Tests for run() stderr progress messages."""

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_no_rate_limit_logs_to_stderr(
        self, mock_pr_info: object, mock_find: object, mock_fetch: object, capsys: object
    ) -> None:
        """Progress messages should go to stderr, not stdout."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, NOT_RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        # Progress messages should be on stderr
        assert "[poll]" in captured.err
        # No poll messages on stdout (stdout is for JSON output from fetch_run)
        assert "[poll]" not in captured.out

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit.run_trigger")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_rate_limited_logs_wait_time(
        self, mock_pr_info: object, mock_find: object, mock_trigger: object, mock_fetch: object, capsys: object
    ) -> None:
        """Rate limited message should include total wait time on stderr."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_trigger.return_value = 0  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "rate limited" in captured.err.lower()
        assert "240" in captured.err  # 210 + 30 buffer


# =============================================================================
# Tests for run() - run_trigger stdout redirect to stderr
# =============================================================================


class TestRunTriggerStdoutRedirect:
    """Tests for run() redirecting run_trigger's stdout to stderr.

    run_trigger uses print() (stdout) for progress messages like
    "Posting @coderabbitai review..." and "Review started!".
    When called from poll.run(), those prints must go to stderr
    to keep stdout clean for JSON output.
    """

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_trigger_stdout_redirected_to_stderr(
        self,
        mock_pr_info: object,
        mock_find: object,
        _mock_sleep: object,
        mock_post_trigger: object,
        mock_is_limited: object,
        mock_fetch: object,
        capsys: object,
    ) -> None:
        """run_trigger's print() output should appear on stderr, not stdout."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_post_trigger.return_value = True  # type: ignore[attr-defined]
        mock_is_limited.return_value = False  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        # run_trigger prints "Posting @coderabbitai review..." to stdout.
        # With redirect, this should appear on stderr instead.
        assert "Posting @coderabbitai review" in captured.err
        assert "Posting @coderabbitai review" not in captured.out

    @patch("myk_claude_tools.reviews.fetch.run")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    @patch("myk_claude_tools.reviews.fetch.get_pr_info")
    def test_trigger_review_started_on_stderr(
        self,
        mock_pr_info: object,
        mock_find: object,
        _mock_sleep: object,
        mock_post_trigger: object,
        mock_is_limited: object,
        mock_fetch: object,
        capsys: object,
    ) -> None:
        """run_trigger's 'Review started!' message should appear on stderr."""
        mock_pr_info.return_value = ("owner", "repo", "42")  # type: ignore[attr-defined]
        mock_find.side_effect = _mock_find_summary(123, RATE_LIMITED_BODY)  # type: ignore[attr-defined]
        mock_post_trigger.return_value = True  # type: ignore[attr-defined]
        mock_is_limited.return_value = False  # type: ignore[attr-defined]
        mock_fetch.return_value = 0  # type: ignore[attr-defined]

        run()

        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "Review started!" in captured.err
        assert "Review started!" not in captured.out
