"""Unit tests for CodeRabbit rate limit module.

This test suite covers:
- _parse_wait_seconds: parsing wait time from rate limit messages
- _validate_owner_repo: validating owner/repo format
- run_check: checking rate limit status with mocked gh CLI
- run_trigger: triggering review with mocked gh CLI and time.sleep
"""

from __future__ import annotations

import json
from unittest.mock import patch

from myk_claude_tools.coderabbit.rate_limit import (
    _RATE_LIMITED_MARKER,
    _SUMMARY_MARKER,
    _parse_wait_seconds,
    _validate_owner_repo,
    run_check,
    run_trigger,
)

# =============================================================================
# Sample comment bodies for testing
# =============================================================================

RATE_LIMITED_BODY = (
    f"{_SUMMARY_MARKER}\n"
    f"{_RATE_LIMITED_MARKER}\n"
    "Please wait **22 minutes and 57 seconds** before requesting another review.\n"
)

NOT_RATE_LIMITED_BODY = f"{_SUMMARY_MARKER}\nThis is a normal summary comment without rate limiting.\n"


# =============================================================================
# Tests for _parse_wait_seconds
# =============================================================================


class TestParseWaitSeconds:
    """Tests for _parse_wait_seconds() time parsing."""

    def test_minutes_and_seconds(self) -> None:
        """Should parse minutes and seconds correctly."""
        body = "Please wait **22 minutes and 57 seconds**"
        assert _parse_wait_seconds(body) == 1377

    def test_seconds_only(self) -> None:
        """Should parse seconds-only message."""
        body = "Please wait **45 seconds**"
        assert _parse_wait_seconds(body) == 45

    def test_one_minute_and_zero_seconds(self) -> None:
        """Should parse 1 minute and 0 seconds."""
        body = "Please wait **1 minute and 0 seconds**"
        assert _parse_wait_seconds(body) == 60

    def test_zero_minutes_and_zero_seconds(self) -> None:
        """Should parse 0 minutes and 0 seconds."""
        body = "Please wait **0 minutes and 0 seconds**"
        assert _parse_wait_seconds(body) == 0

    def test_no_match_returns_none(self) -> None:
        """Should return None when no wait time pattern is found."""
        body = "This is a normal comment without wait time."
        assert _parse_wait_seconds(body) is None

    def test_empty_string_returns_none(self) -> None:
        """Should return None for empty string."""
        assert _parse_wait_seconds("") is None


# =============================================================================
# Tests for _validate_owner_repo
# =============================================================================


class TestValidateOwnerRepo:
    """Tests for _validate_owner_repo() format validation."""

    def test_valid_owner_repo(self) -> None:
        """Should return True for valid owner/repo format."""
        assert _validate_owner_repo("owner/repo") is True

    def test_no_slash(self) -> None:
        """Should return False when there is no slash."""
        assert _validate_owner_repo("invalid") is False

    def test_too_many_slashes(self) -> None:
        """Should return False when there are too many slashes."""
        assert _validate_owner_repo("a/b/c") is False

    def test_empty_string(self) -> None:
        """Should return False for empty string."""
        assert _validate_owner_repo("") is False


# =============================================================================
# Tests for run_check
# =============================================================================


def _mock_find_summary(comment_id: int | None, body: str | None, error: str = "") -> object:
    """Create a side_effect function for _find_summary_comment that returns fixed values."""

    def _side_effect(_owner_repo: str, _pr_number: int) -> tuple[int | None, str | None, str]:
        return comment_id, body, error

    return _side_effect


class TestRunCheck:
    """Tests for run_check() with mocked _run_gh."""

    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    def test_rate_limited(self, mock_find: object, capsys: object) -> None:
        """Should output JSON with rate_limited=True and wait_seconds when rate limited."""
        mock_find.side_effect = _mock_find_summary(12345, RATE_LIMITED_BODY)  # type: ignore[attr-defined]

        exit_code = run_check("owner/repo", 1)

        assert exit_code == 0
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        output = json.loads(captured.out)
        assert output["rate_limited"] is True
        assert output["wait_seconds"] == 1377
        assert output["comment_id"] == 12345

    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    def test_not_rate_limited(self, mock_find: object, capsys: object) -> None:
        """Should output JSON with rate_limited=False when not rate limited."""
        mock_find.side_effect = _mock_find_summary(12345, NOT_RATE_LIMITED_BODY)  # type: ignore[attr-defined]

        exit_code = run_check("owner/repo", 1)

        assert exit_code == 0
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        output = json.loads(captured.out)
        assert output["rate_limited"] is False

    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    def test_no_comment_found(self, mock_find: object, capsys: object) -> None:
        """Should return 1 when no summary comment is found."""
        mock_find.side_effect = _mock_find_summary(None, None, "No CodeRabbit summary comment found on this PR")  # type: ignore[attr-defined]

        exit_code = run_check("owner/repo", 1)

        assert exit_code == 1
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "No CodeRabbit summary comment found" in captured.out

    @patch("myk_claude_tools.coderabbit.rate_limit._find_summary_comment")
    def test_api_error(self, mock_find: object, capsys: object) -> None:
        """Should return 1 with API error message when GitHub API fails."""
        mock_find.side_effect = _mock_find_summary(None, None, "GitHub API error: Bad credentials")  # type: ignore[attr-defined]

        exit_code = run_check("owner/repo", 1)

        assert exit_code == 1
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        assert "GitHub API error" in captured.out

    def test_invalid_owner_repo(self) -> None:
        """Should return 1 for invalid owner/repo format."""
        exit_code = run_check("invalid", 1)
        assert exit_code == 1


# =============================================================================
# Tests for run_trigger
# =============================================================================


class TestRunTrigger:
    """Tests for run_trigger() with mocked _run_gh and time.sleep."""

    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    def test_review_starts_on_first_poll(
        self, mock_trigger: object, mock_is_limited: object, _mock_sleep: object
    ) -> None:
        """Should return 0 when review starts on the first poll."""
        mock_trigger.return_value = True  # type: ignore[attr-defined]
        mock_is_limited.return_value = False  # type: ignore[attr-defined]

        exit_code = run_trigger("owner/repo", 1, wait_seconds=0)

        assert exit_code == 0
        mock_trigger.assert_called_once_with("owner/repo", 1)  # type: ignore[attr-defined]

    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    def test_timeout_after_max_attempts(
        self, mock_trigger: object, mock_is_limited: object, _mock_sleep: object
    ) -> None:
        """Should return 1 when review never starts within max attempts."""
        mock_trigger.return_value = True  # type: ignore[attr-defined]
        mock_is_limited.return_value = True  # type: ignore[attr-defined]

        exit_code = run_trigger("owner/repo", 1, wait_seconds=0)

        assert exit_code == 1

    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    def test_failed_to_post_trigger(self, mock_trigger: object, mock_is_limited: object, _mock_sleep: object) -> None:
        """Should return 1 when the trigger comment fails to post."""
        mock_trigger.return_value = False  # type: ignore[attr-defined]

        exit_code = run_trigger("owner/repo", 1, wait_seconds=0)

        assert exit_code == 1
        mock_is_limited.assert_not_called()  # type: ignore[attr-defined]

    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    def test_consecutive_no_comment_results(
        self, mock_trigger: object, mock_is_limited: object, _mock_sleep: object
    ) -> None:
        """Should return 0 after two consecutive no_comment results (comment replaced)."""
        mock_trigger.return_value = True  # type: ignore[attr-defined]
        # Two consecutive no_comment means the comment was replaced (review started)
        mock_is_limited.side_effect = ["no_comment", "no_comment"]  # type: ignore[attr-defined]

        exit_code = run_trigger("owner/repo", 1, wait_seconds=0)

        assert exit_code == 0

    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    def test_wait_seconds_calls_sleep(self, mock_trigger: object, mock_is_limited: object, mock_sleep: object) -> None:
        """Should call time.sleep with the specified wait_seconds."""
        mock_trigger.return_value = True  # type: ignore[attr-defined]
        mock_is_limited.return_value = False  # type: ignore[attr-defined]

        run_trigger("owner/repo", 1, wait_seconds=120)

        # First sleep call should be the initial wait
        mock_sleep.assert_any_call(120)  # type: ignore[attr-defined]

    def test_invalid_owner_repo(self) -> None:
        """Should return 1 for invalid owner/repo format."""
        exit_code = run_trigger("invalid", 1)
        assert exit_code == 1

    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    def test_single_no_comment_then_not_limited(
        self, mock_trigger: object, mock_is_limited: object, _mock_sleep: object
    ) -> None:
        """Should retry on single no_comment and succeed when next poll shows not limited."""
        mock_trigger.return_value = True  # type: ignore[attr-defined]
        # Single no_comment followed by not rate limited
        mock_is_limited.side_effect = ["no_comment", False]  # type: ignore[attr-defined]

        exit_code = run_trigger("owner/repo", 1, wait_seconds=0)

        assert exit_code == 0

    @patch("myk_claude_tools.coderabbit.rate_limit.time.sleep")
    @patch("myk_claude_tools.coderabbit.rate_limit._is_rate_limited")
    @patch("myk_claude_tools.coderabbit.rate_limit._post_review_trigger")
    def test_api_errors_not_treated_as_success(
        self, mock_trigger: object, mock_is_limited: object, _mock_sleep: object
    ) -> None:
        """Should NOT treat consecutive API errors as review started."""
        mock_trigger.return_value = True  # type: ignore[attr-defined]
        # All attempts return "error" - should time out, not succeed
        mock_is_limited.return_value = "error"  # type: ignore[attr-defined]

        exit_code = run_trigger("owner/repo", 1, wait_seconds=0)

        assert exit_code == 1
