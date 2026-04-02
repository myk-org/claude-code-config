"""Unit tests for reviews CLI commands.

Tests that the 'poll' command is properly registered in the reviews group
and wires through to myk_claude_tools.reviews.poll.run correctly.
"""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from myk_claude_tools.reviews.commands import reviews


class TestPollCommand:
    """Tests for the 'reviews poll' click command."""

    def test_poll_command_registered(self) -> None:
        """The 'poll' command should be registered in the reviews group."""
        command_names = [cmd for cmd in reviews.commands]
        assert "poll" in command_names

    @patch("myk_claude_tools.reviews.poll.run")
    def test_poll_invokes_run_with_empty_url(self, mock_run: object) -> None:
        """Invoking 'poll' with no arguments should call run with empty string."""
        mock_run.return_value = 0  # type: ignore[attr-defined]
        runner = CliRunner()

        result = runner.invoke(reviews, ["poll"])

        mock_run.assert_called_once_with("")  # type: ignore[attr-defined]
        assert result.exit_code == 0

    @patch("myk_claude_tools.reviews.poll.run")
    def test_poll_invokes_run_with_review_url(self, mock_run: object) -> None:
        """Invoking 'poll' with a URL argument should forward it to run."""
        mock_run.return_value = 0  # type: ignore[attr-defined]
        runner = CliRunner()

        result = runner.invoke(reviews, ["poll", "https://github.com/o/r/pull/1#pullrequestreview-123"])

        mock_run.assert_called_once_with("https://github.com/o/r/pull/1#pullrequestreview-123")  # type: ignore[attr-defined]
        assert result.exit_code == 0

    @patch("myk_claude_tools.reviews.poll.run")
    def test_poll_exits_with_run_exit_code(self, mock_run: object) -> None:
        """Exit code from run() should be propagated via sys.exit."""
        mock_run.return_value = 1  # type: ignore[attr-defined]
        runner = CliRunner()

        result = runner.invoke(reviews, ["poll"])

        assert result.exit_code == 1
