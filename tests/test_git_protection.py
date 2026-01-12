"""Comprehensive unit tests for git-protection.py hook script.

This test suite covers:
- is_git_subcommand() regex pattern matching
- is_commit_command() and is_push_command() wrapper functions
- is_amend_with_unpushed_commits() with mocked remote check
- format_pr_merge_error() message formatting
- Mock-based tests for git operations (subprocess.run)
- Integration-style tests for decision functions
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path for importing git-protection module
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_git_protection_module() -> ModuleType:
    """Load the git-protection module with hyphenated filename."""
    spec = importlib.util.spec_from_file_location("git_protection", SCRIPTS_DIR / "git-protection.py")
    if spec is None or spec.loader is None:
        raise ImportError("Could not load git-protection module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


git_protection = _load_git_protection_module()


# =============================================================================
# Tests for is_git_subcommand() - Regex Pattern Matching
# =============================================================================


class TestIsGitSubcommand:
    """Tests for is_git_subcommand() regex pattern matching."""

    # --- Commit subcommand tests ---

    def test_simple_git_commit(self) -> None:
        """Simple git commit command should match 'commit'."""
        assert git_protection.is_git_subcommand('git commit -m "message"', "commit")

    def test_git_commit_with_c_flag(self) -> None:
        """git -C /path commit should match 'commit'."""
        assert git_protection.is_git_subcommand('git -C /path commit -m "msg"', "commit")

    def test_git_commit_with_lowercase_c_config(self) -> None:
        """git -c user.name=foo commit should match 'commit'."""
        assert git_protection.is_git_subcommand('git -c user.name=foo commit -m "msg"', "commit")

    def test_git_commit_with_multiple_flags(self) -> None:
        """git with multiple flags before commit should match."""
        assert git_protection.is_git_subcommand('git -C /path -c user.name=foo commit -m "msg"', "commit")

    def test_git_log_grep_commit_not_match(self) -> None:
        """git log --grep=commit should NOT match 'commit' (false positive check)."""
        assert not git_protection.is_git_subcommand("git log --grep=commit", "commit")

    def test_git_show_commit_file_not_match(self) -> None:
        """git show HEAD:commit.txt should NOT match 'commit'."""
        assert not git_protection.is_git_subcommand("git show HEAD:commit.txt", "commit")

    def test_git_diff_commit_ref_not_match(self) -> None:
        """git diff commit~1 should NOT match 'commit' as subcommand."""
        # The word 'commit' here is a ref, not a subcommand
        # After 'diff' subcommand, 'commit' is an argument
        assert not git_protection.is_git_subcommand("git diff commit~1", "commit")

    def test_git_commit_amend(self) -> None:
        """git commit --amend should match 'commit'."""
        assert git_protection.is_git_subcommand("git commit --amend", "commit")

    def test_git_commit_verbose(self) -> None:
        """git commit -v should match 'commit'."""
        assert git_protection.is_git_subcommand("git commit -v", "commit")

    # --- Push subcommand tests ---

    def test_simple_git_push(self) -> None:
        """Simple git push origin main should match 'push'."""
        assert git_protection.is_git_subcommand("git push origin main", "push")

    def test_git_push_with_c_flag(self) -> None:
        """git -C /path push should match 'push'."""
        assert git_protection.is_git_subcommand("git -C /path push", "push")

    def test_git_push_force(self) -> None:
        """git push --force should match 'push'."""
        assert git_protection.is_git_subcommand("git push --force origin main", "push")

    def test_git_push_set_upstream(self) -> None:
        """git push -u origin branch should match 'push'."""
        assert git_protection.is_git_subcommand("git push -u origin feature-branch", "push")

    def test_git_config_push_default_not_match(self) -> None:
        """git config push.default should NOT match 'push'."""
        assert not git_protection.is_git_subcommand("git config push.default current", "push")

    def test_git_config_get_regexp_push_not_match(self) -> None:
        """git config --get-regexp push should NOT match 'push'."""
        assert not git_protection.is_git_subcommand("git config --get-regexp push", "push")

    def test_git_remote_push_url_not_match(self) -> None:
        """git remote set-url --push should NOT match 'push' as subcommand."""
        assert not git_protection.is_git_subcommand("git remote set-url --push origin url", "push")

    # --- Edge cases ---

    def test_git_with_path_containing_git(self) -> None:
        """Path containing 'git' should not cause false positives."""
        # This tests that we match 'git' as a word boundary
        assert not git_protection.is_git_subcommand("/usr/bin/github-cli commit", "commit")

    def test_echo_git_command(self) -> None:
        """echo 'git commit' should still match (embedded in larger command)."""
        # The regex finds git commit within the string
        assert git_protection.is_git_subcommand("echo 'git commit -m test'", "commit")

    def test_git_bare_command(self) -> None:
        """git alone should not match any subcommand."""
        assert not git_protection.is_git_subcommand("git", "commit")
        assert not git_protection.is_git_subcommand("git", "push")

    def test_git_help_commit(self) -> None:
        """git help commit should NOT match 'commit' as the subcommand (help is)."""
        # 'help' is the subcommand here, not 'commit'
        assert not git_protection.is_git_subcommand("git help commit", "commit")
        assert git_protection.is_git_subcommand("git help commit", "help")

    def test_git_subcommand_case_sensitive(self) -> None:
        """Subcommand matching should be case sensitive."""
        assert not git_protection.is_git_subcommand("git COMMIT -m msg", "commit")
        assert not git_protection.is_git_subcommand("git Commit -m msg", "commit")

    def test_git_with_verbose_flag(self) -> None:
        """git --verbose commit should match 'commit'."""
        assert git_protection.is_git_subcommand("git --verbose commit -m msg", "commit")

    def test_git_with_no_pager(self) -> None:
        """git --no-pager commit should match 'commit'."""
        assert git_protection.is_git_subcommand("git --no-pager commit -m msg", "commit")


# =============================================================================
# Tests for is_commit_command() and is_push_command()
# =============================================================================


class TestIsCommitCommand:
    """Tests for is_commit_command() wrapper function."""

    def test_basic_commit(self) -> None:
        """Basic git commit should be recognized."""
        assert git_protection.is_commit_command('git commit -m "test"')

    def test_commit_with_flags(self) -> None:
        """git commit with various flags should be recognized."""
        assert git_protection.is_commit_command("git commit --amend --no-edit")
        assert git_protection.is_commit_command("git commit -a -m 'all changes'")

    def test_not_commit_command(self) -> None:
        """Non-commit commands should not be recognized as commit."""
        assert not git_protection.is_commit_command("git push origin main")
        assert not git_protection.is_commit_command("git status")
        assert not git_protection.is_commit_command("git log --oneline")


class TestIsPushCommand:
    """Tests for is_push_command() wrapper function."""

    def test_basic_push(self) -> None:
        """Basic git push should be recognized."""
        assert git_protection.is_push_command("git push origin main")

    def test_push_with_flags(self) -> None:
        """git push with various flags should be recognized."""
        assert git_protection.is_push_command("git push --force origin main")
        assert git_protection.is_push_command("git push -u origin feature")

    def test_not_push_command(self) -> None:
        """Non-push commands should not be recognized as push."""
        assert not git_protection.is_push_command('git commit -m "test"')
        assert not git_protection.is_push_command("git status")
        assert not git_protection.is_push_command("git pull origin main")


# =============================================================================
# Tests for is_amend_with_unpushed_commits()
# =============================================================================


class TestIsAmendWithUnpushedCommits:
    """Tests for is_amend_with_unpushed_commits() function."""

    @patch.object(git_protection, "is_branch_ahead_of_remote")
    def test_amend_with_unpushed_commits(self, mock_ahead: Any) -> None:
        """Amend command with unpushed commits should return True."""
        mock_ahead.return_value = True
        result = git_protection.is_amend_with_unpushed_commits("git commit --amend --no-edit")
        assert result is True
        mock_ahead.assert_called_once()

    @patch.object(git_protection, "is_branch_ahead_of_remote")
    def test_amend_with_pushed_commits(self, mock_ahead: Any) -> None:
        """Amend command with already pushed commits should return False."""
        mock_ahead.return_value = False
        result = git_protection.is_amend_with_unpushed_commits("git commit --amend --no-edit")
        assert result is False
        mock_ahead.assert_called_once()

    @patch.object(git_protection, "is_branch_ahead_of_remote")
    def test_non_amend_command(self, mock_ahead: Any) -> None:
        """Non-amend commit should return False without checking remote."""
        mock_ahead.return_value = True
        result = git_protection.is_amend_with_unpushed_commits('git commit -m "test"')
        assert result is False
        # Should short-circuit and not call is_branch_ahead_of_remote
        mock_ahead.assert_not_called()

    @patch.object(git_protection, "is_branch_ahead_of_remote")
    def test_amend_short_flag(self, mock_ahead: Any) -> None:
        """Amend with -m flag should also be detected."""
        mock_ahead.return_value = True
        result = git_protection.is_amend_with_unpushed_commits('git commit --amend -m "updated"')
        assert result is True


# =============================================================================
# Tests for format_pr_merge_error()
# =============================================================================


class TestFormatPrMergeError:
    """Tests for format_pr_merge_error() message formatting."""

    def test_basic_error_formatting(self) -> None:
        """Error message should contain function name and error info."""
        result = git_protection.format_pr_merge_error("get_pr_merge_status()", "gh pr list failed (exit 1): auth error")
        assert "get_pr_merge_status()" in result
        assert "gh pr list failed (exit 1): auth error" in result
        assert "BLOCKED" in result
        assert "myk-org/claude-code-config" in result

    def test_none_error_info(self) -> None:
        """None error_info should show 'Unknown error'."""
        result = git_protection.format_pr_merge_error("test_function()", None)
        assert "Unknown error" in result
        assert "test_function()" in result

    def test_error_contains_action_required(self) -> None:
        """Error message should contain action required section."""
        result = git_protection.format_pr_merge_error("func()", "some error")
        assert "ACTION REQUIRED" in result
        assert "github-expert" in result

    def test_error_contains_issue_creation_info(self) -> None:
        """Error message should contain GitHub issue creation info."""
        result = git_protection.format_pr_merge_error("my_func()", "timeout error")
        assert "bug(scripts): git-protection.py" in result
        assert "timeout error" in result


# =============================================================================
# Mock-based tests for git operations (subprocess.run)
# =============================================================================


class TestGetCurrentBranch:
    """Tests for get_current_branch() with mocked subprocess."""

    @patch("subprocess.run")
    def test_normal_branch(self, mock_run: Any) -> None:
        """Normal branch name should be returned."""
        mock_run.return_value = MagicMock(returncode=0, stdout="feature-branch\n", stderr="")
        result = git_protection.get_current_branch()
        assert result == "feature-branch"

    @patch("subprocess.run")
    def test_detached_head(self, mock_run: Any) -> None:
        """Detached HEAD should return None."""
        mock_run.return_value = MagicMock(returncode=0, stdout="HEAD\n", stderr="")
        result = git_protection.get_current_branch()
        assert result is None

    @patch("subprocess.run")
    def test_git_error(self, mock_run: Any) -> None:
        """Git error should return None."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: not a git repository")
        result = git_protection.get_current_branch()
        assert result is None

    @patch("subprocess.run")
    def test_exception_handling(self, mock_run: Any) -> None:
        """Exception should be caught and return None."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=2)
        result = git_protection.get_current_branch()
        assert result is None

    @patch("subprocess.run")
    def test_main_branch(self, mock_run: Any) -> None:
        """Main branch should be returned correctly."""
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")
        result = git_protection.get_current_branch()
        assert result == "main"


class TestGetMainBranch:
    """Tests for get_main_branch() with mocked subprocess."""

    @patch("subprocess.run")
    def test_main_exists(self, mock_run: Any) -> None:
        """'main' should be returned if it exists."""
        mock_run.return_value = MagicMock(returncode=0, stdout="sha\n", stderr="")
        result = git_protection.get_main_branch()
        assert result == "main"

    @patch("subprocess.run")
    def test_master_exists(self, mock_run: Any) -> None:
        """'master' should be returned if 'main' does not exist."""

        def side_effect(cmd: list[str], *_args: object, **_kwargs: object) -> MagicMock:
            if "main" in cmd:
                return MagicMock(returncode=128, stdout="", stderr="fatal: not valid")
            if "master" in cmd:
                return MagicMock(returncode=0, stdout="sha\n", stderr="")
            return MagicMock(returncode=128, stdout="", stderr="")

        mock_run.side_effect = side_effect
        result = git_protection.get_main_branch()
        assert result == "master"

    @patch("subprocess.run")
    def test_neither_exists(self, mock_run: Any) -> None:
        """None should be returned if neither 'main' nor 'master' exists."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: not valid")
        result = git_protection.get_main_branch()
        assert result is None

    @patch("subprocess.run")
    def test_exception_continues(self, mock_run: Any) -> None:
        """Exception on 'main' should try 'master' next."""

        def side_effect(cmd: list[str], *_args: object, **_kwargs: object) -> MagicMock:
            if "main" in cmd:
                raise subprocess.TimeoutExpired(cmd="git", timeout=2)
            if "master" in cmd:
                return MagicMock(returncode=0, stdout="sha\n", stderr="")
            return MagicMock(returncode=128, stdout="", stderr="")

        mock_run.side_effect = side_effect
        result = git_protection.get_main_branch()
        assert result == "master"


class TestIsGitRepository:
    """Tests for is_git_repository() with mocked subprocess."""

    @patch("subprocess.run")
    def test_inside_git_repo(self, mock_run: Any) -> None:
        """Inside git repo should return True."""
        mock_run.return_value = MagicMock(returncode=0, stdout=".git\n", stderr="")
        result = git_protection.is_git_repository()
        assert result is True

    @patch("subprocess.run")
    def test_outside_git_repo(self, mock_run: Any) -> None:
        """Outside git repo should return False."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: not a git repository")
        result = git_protection.is_git_repository()
        assert result is False

    @patch("subprocess.run")
    def test_exception_returns_false(self, mock_run: Any) -> None:
        """Exception should return False."""
        mock_run.side_effect = Exception("some error")
        result = git_protection.is_git_repository()
        assert result is False


class TestIsGithubRepo:
    """Tests for is_github_repo() with mocked subprocess."""

    @patch("subprocess.run")
    def test_github_https_url(self, mock_run: Any) -> None:
        """GitHub HTTPS URL should return True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/user/repo.git\n", stderr="")
        result = git_protection.is_github_repo()
        assert result is True

    @patch("subprocess.run")
    def test_github_ssh_url(self, mock_run: Any) -> None:
        """GitHub SSH URL should return True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="git@github.com:user/repo.git\n", stderr="")
        result = git_protection.is_github_repo()
        assert result is True

    @patch("subprocess.run")
    def test_gitlab_url(self, mock_run: Any) -> None:
        """GitLab URL should return False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="https://gitlab.com/user/repo.git\n", stderr="")
        result = git_protection.is_github_repo()
        assert result is False

    @patch("subprocess.run")
    def test_bitbucket_url(self, mock_run: Any) -> None:
        """Bitbucket URL should return False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="git@bitbucket.org:user/repo.git\n", stderr="")
        result = git_protection.is_github_repo()
        assert result is False

    @patch("subprocess.run")
    def test_no_remote(self, mock_run: Any) -> None:
        """No remote should return False."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: No such remote 'origin'")
        result = git_protection.is_github_repo()
        assert result is False

    @patch("subprocess.run")
    def test_exception_returns_false(self, mock_run: Any) -> None:
        """Exception should return False."""
        mock_run.side_effect = Exception("network error")
        result = git_protection.is_github_repo()
        assert result is False


class TestIsBranchMerged:
    """Tests for is_branch_merged() with mocked subprocess."""

    @patch("subprocess.run")
    def test_branch_merged(self, mock_run: Any) -> None:
        """Merged branch should return True."""

        def side_effect(cmd: list[str], *_args: object, **_kwargs: object) -> MagicMock:
            if "rev-list" in cmd:
                # Has unique commits
                return MagicMock(returncode=0, stdout="5\n", stderr="")
            if "merge-base" in cmd:
                # Is ancestor (merged)
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        result = git_protection.is_branch_merged("feature", "main")
        assert result is True

    @patch("subprocess.run")
    def test_branch_not_merged(self, mock_run: Any) -> None:
        """Not merged branch should return False."""

        def side_effect(cmd: list[str], *_args: object, **_kwargs: object) -> MagicMock:
            if "rev-list" in cmd:
                # Has unique commits
                return MagicMock(returncode=0, stdout="3\n", stderr="")
            if "merge-base" in cmd:
                # Not ancestor (not merged)
                return MagicMock(returncode=1, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        result = git_protection.is_branch_merged("feature", "main")
        assert result is False

    @patch("subprocess.run")
    def test_fresh_branch_no_unique_commits(self, mock_run: Any) -> None:
        """Fresh branch with no unique commits should return False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="0\n", stderr="")
        result = git_protection.is_branch_merged("fresh-branch", "main")
        assert result is False

    @patch("subprocess.run")
    def test_rev_list_error(self, mock_run: Any) -> None:
        """Error in rev-list should return False."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: error")
        result = git_protection.is_branch_merged("feature", "main")
        assert result is False

    @patch("subprocess.run")
    def test_invalid_rev_list_output(self, mock_run: Any) -> None:
        """Invalid rev-list output should return False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="not-a-number\n", stderr="")
        result = git_protection.is_branch_merged("feature", "main")
        assert result is False

    @patch("subprocess.run")
    def test_exception_returns_false(self, mock_run: Any) -> None:
        """Exception should return False."""
        mock_run.side_effect = Exception("git error")
        result = git_protection.is_branch_merged("feature", "main")
        assert result is False


class TestIsBranchAheadOfRemote:
    """Tests for is_branch_ahead_of_remote() with mocked subprocess."""

    @patch("subprocess.run")
    def test_branch_ahead(self, mock_run: Any) -> None:
        """Branch ahead of remote should return True."""

        def side_effect(cmd: list[str], *_args: object, **_kwargs: object) -> MagicMock:
            if "@{u}" in cmd:
                # Has tracking branch
                return MagicMock(returncode=0, stdout="origin/feature\n", stderr="")
            if "status" in cmd:
                return MagicMock(returncode=0, stdout="## feature...origin/feature [ahead 2]\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        result = git_protection.is_branch_ahead_of_remote()
        assert result is True

    @patch("subprocess.run")
    def test_branch_not_ahead(self, mock_run: Any) -> None:
        """Branch not ahead of remote should return False."""

        def side_effect(cmd: list[str], *_args: object, **_kwargs: object) -> MagicMock:
            if "@{u}" in cmd:
                return MagicMock(returncode=0, stdout="origin/feature\n", stderr="")
            if "status" in cmd:
                return MagicMock(returncode=0, stdout="## feature...origin/feature\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        result = git_protection.is_branch_ahead_of_remote()
        assert result is False

    @patch("subprocess.run")
    def test_no_tracking_branch(self, mock_run: Any) -> None:
        """No tracking branch should return True (local-only branch)."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: no upstream")
        result = git_protection.is_branch_ahead_of_remote()
        assert result is True

    @patch("subprocess.run")
    def test_exception_returns_false(self, mock_run: Any) -> None:
        """Exception should return False."""
        mock_run.side_effect = Exception("error")
        result = git_protection.is_branch_ahead_of_remote()
        assert result is False


class TestGetPrMergeStatus:
    """Tests for get_pr_merge_status() with mocked subprocess."""

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch.object(git_protection, "is_github_repo")
    def test_pr_merged(self, mock_is_github: Any, mock_run: Any, mock_which: Any) -> None:
        """Merged PR should return (True, pr_number)."""
        mock_is_github.return_value = True
        mock_which.return_value = "/usr/bin/gh"
        mock_run.return_value = MagicMock(returncode=0, stdout='[{"number": 42}]', stderr="")
        result = git_protection.get_pr_merge_status("feature-branch")
        assert result == (True, "42")

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch.object(git_protection, "is_github_repo")
    def test_pr_not_merged(self, mock_is_github: Any, mock_run: Any, mock_which: Any) -> None:
        """No merged PR should return (False, None)."""
        mock_is_github.return_value = True
        mock_which.return_value = "/usr/bin/gh"
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        result = git_protection.get_pr_merge_status("feature-branch")
        assert result == (False, None)

    @patch.object(git_protection, "is_github_repo")
    def test_not_github_repo(self, mock_is_github: Any) -> None:
        """Non-GitHub repo should return (False, None)."""
        mock_is_github.return_value = False
        result = git_protection.get_pr_merge_status("feature-branch")
        assert result == (False, None)

    @patch("shutil.which")
    @patch.object(git_protection, "is_github_repo")
    def test_gh_not_installed(self, mock_is_github: Any, mock_which: Any) -> None:
        """gh CLI not installed should return (False, None)."""
        mock_is_github.return_value = True
        mock_which.return_value = None
        result = git_protection.get_pr_merge_status("feature-branch")
        assert result == (False, None)

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch.object(git_protection, "is_github_repo")
    def test_gh_error(self, mock_is_github: Any, mock_run: Any, mock_which: Any) -> None:
        """gh CLI error should return (None, error_message)."""
        mock_is_github.return_value = True
        mock_which.return_value = "/usr/bin/gh"
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")
        result = git_protection.get_pr_merge_status("feature-branch")
        assert result[0] is None
        assert "auth error" in result[1]

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch.object(git_protection, "is_github_repo")
    def test_gh_timeout(self, mock_is_github: Any, mock_run: Any, mock_which: Any) -> None:
        """gh CLI timeout should return (None, error_message)."""
        mock_is_github.return_value = True
        mock_which.return_value = "/usr/bin/gh"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=5)
        result = git_protection.get_pr_merge_status("feature-branch")
        assert result[0] is None
        assert "timeout" in result[1].lower()

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch.object(git_protection, "is_github_repo")
    def test_gh_invalid_json(self, mock_is_github: Any, mock_run: Any, mock_which: Any) -> None:
        """Invalid JSON from gh should return (None, error_message)."""
        mock_is_github.return_value = True
        mock_which.return_value = "/usr/bin/gh"
        mock_run.return_value = MagicMock(returncode=0, stdout="not valid json", stderr="")
        result = git_protection.get_pr_merge_status("feature-branch")
        assert result[0] is None
        assert "JSON" in result[1]


# =============================================================================
# Integration-style tests for decision functions
# =============================================================================


class TestShouldBlockCommit:
    """Tests for should_block_commit() with mocked dependencies."""

    @patch.object(git_protection, "is_git_repository")
    def test_not_git_repo(self, mock_is_repo: Any) -> None:
        """Not in git repo should allow commit."""
        mock_is_repo.return_value = False
        should_block, reason = git_protection.should_block_commit('git commit -m "test"')
        assert should_block is False
        assert reason is None

    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_detached_head(self, mock_is_repo: Any, mock_branch: Any) -> None:
        """Detached HEAD should block commit."""
        mock_is_repo.return_value = True
        mock_branch.return_value = None
        should_block, reason = git_protection.should_block_commit('git commit -m "test"')
        assert should_block is True
        assert "detached HEAD" in reason

    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_pr_merged(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any) -> None:
        """Merged PR should block commit."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_pr_status.return_value = (True, "42")
        should_block, reason = git_protection.should_block_commit('git commit -m "test"')
        assert should_block is True
        assert "PR #42" in reason
        assert "MERGED" in reason

    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_pr_status_error(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any) -> None:
        """PR status error should block commit (fail closed)."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_pr_status.return_value = (None, "API timeout")
        should_block, reason = git_protection.should_block_commit('git commit -m "test"')
        assert should_block is True
        assert "API timeout" in reason

    @patch.object(git_protection, "get_main_branch")
    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_on_main_branch(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any, mock_main: Any) -> None:
        """On main branch should block commit."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "main"
        mock_pr_status.return_value = (False, None)
        mock_main.return_value = "main"
        should_block, reason = git_protection.should_block_commit('git commit -m "test"')
        assert should_block is True
        assert "'main'" in reason
        assert "protected" in reason.lower()

    @patch.object(git_protection, "get_main_branch")
    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_on_master_branch(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any, mock_main: Any) -> None:
        """On master branch should block commit."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "master"
        mock_pr_status.return_value = (False, None)
        mock_main.return_value = "master"
        should_block, reason = git_protection.should_block_commit('git commit -m "test"')
        assert should_block is True
        assert "'master'" in reason

    @patch.object(git_protection, "is_amend_with_unpushed_commits")
    @patch.object(git_protection, "is_branch_merged")
    @patch.object(git_protection, "get_main_branch")
    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_amend_unpushed_allowed(
        self,
        mock_is_repo: Any,
        mock_branch: Any,
        mock_pr_status: Any,
        mock_main: Any,
        _mock_merged: Any,
        mock_amend: Any,
    ) -> None:
        """Amend on unpushed commits should be allowed."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature"
        mock_pr_status.return_value = (False, None)
        mock_main.return_value = "main"
        mock_amend.return_value = True
        should_block, reason = git_protection.should_block_commit("git commit --amend --no-edit")
        assert should_block is False
        assert reason is None

    @patch.object(git_protection, "is_amend_with_unpushed_commits")
    @patch.object(git_protection, "is_branch_merged")
    @patch.object(git_protection, "get_main_branch")
    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_branch_merged_blocked(
        self,
        mock_is_repo: Any,
        mock_branch: Any,
        mock_pr_status: Any,
        mock_main: Any,
        mock_merged: Any,
        mock_amend: Any,
    ) -> None:
        """Merged branch should block commit."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature"
        mock_pr_status.return_value = (False, None)
        mock_main.return_value = "main"
        mock_amend.return_value = False
        mock_merged.return_value = True
        should_block, reason = git_protection.should_block_commit('git commit -m "test"')
        assert should_block is True
        assert "merged" in reason.lower()

    @patch.object(git_protection, "is_amend_with_unpushed_commits")
    @patch.object(git_protection, "is_branch_merged")
    @patch.object(git_protection, "get_main_branch")
    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_feature_branch_allowed(
        self,
        mock_is_repo: Any,
        mock_branch: Any,
        mock_pr_status: Any,
        mock_main: Any,
        mock_merged: Any,
        mock_amend: Any,
    ) -> None:
        """Normal feature branch should allow commit."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_pr_status.return_value = (False, None)
        mock_main.return_value = "main"
        mock_amend.return_value = False
        mock_merged.return_value = False
        should_block, reason = git_protection.should_block_commit('git commit -m "test"')
        assert should_block is False
        assert reason is None

    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_no_main_branch_allows_commit(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any) -> None:
        """Unable to determine main branch should allow commit."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature"
        mock_pr_status.return_value = (False, None)
        with patch.object(git_protection, "get_main_branch", return_value=None):
            should_block, reason = git_protection.should_block_commit('git commit -m "test"')
            assert should_block is False
            assert reason is None


class TestShouldBlockPush:
    """Tests for should_block_push() with mocked dependencies."""

    @patch.object(git_protection, "is_git_repository")
    def test_not_git_repo(self, mock_is_repo: Any) -> None:
        """Not in git repo should allow push."""
        mock_is_repo.return_value = False
        should_block, reason = git_protection.should_block_push()
        assert should_block is False
        assert reason is None

    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_detached_head_allowed(self, mock_is_repo: Any, mock_branch: Any) -> None:
        """Detached HEAD should allow push (intentional hash push)."""
        mock_is_repo.return_value = True
        mock_branch.return_value = None
        should_block, reason = git_protection.should_block_push()
        assert should_block is False
        assert reason is None

    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_pr_merged(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any) -> None:
        """Merged PR should block push."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_pr_status.return_value = (True, "99")
        should_block, reason = git_protection.should_block_push()
        assert should_block is True
        assert "PR #99" in reason
        assert "MERGED" in reason

    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_pr_status_error(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any) -> None:
        """PR status error should block push (fail closed)."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_pr_status.return_value = (None, "Network error")
        should_block, reason = git_protection.should_block_push()
        assert should_block is True
        assert "Network error" in reason

    @patch.object(git_protection, "get_main_branch")
    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_on_main_branch(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any, mock_main: Any) -> None:
        """On main branch should block push."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "main"
        mock_pr_status.return_value = (False, None)
        mock_main.return_value = "main"
        should_block, reason = git_protection.should_block_push()
        assert should_block is True
        assert "'main'" in reason
        assert "protected" in reason.lower()

    @patch.object(git_protection, "is_branch_merged")
    @patch.object(git_protection, "get_main_branch")
    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_branch_merged_blocked(
        self,
        mock_is_repo: Any,
        mock_branch: Any,
        mock_pr_status: Any,
        mock_main: Any,
        mock_merged: Any,
    ) -> None:
        """Merged branch should block push."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature"
        mock_pr_status.return_value = (False, None)
        mock_main.return_value = "main"
        mock_merged.return_value = True
        should_block, reason = git_protection.should_block_push()
        assert should_block is True
        assert "merged" in reason.lower()

    @patch.object(git_protection, "is_branch_merged")
    @patch.object(git_protection, "get_main_branch")
    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_feature_branch_allowed(
        self,
        mock_is_repo: Any,
        mock_branch: Any,
        mock_pr_status: Any,
        mock_main: Any,
        mock_merged: Any,
    ) -> None:
        """Normal feature branch should allow push."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_pr_status.return_value = (False, None)
        mock_main.return_value = "main"
        mock_merged.return_value = False
        should_block, reason = git_protection.should_block_push()
        assert should_block is False
        assert reason is None

    @patch.object(git_protection, "get_pr_merge_status")
    @patch.object(git_protection, "get_current_branch")
    @patch.object(git_protection, "is_git_repository")
    def test_no_main_branch_allows_push(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any) -> None:
        """Unable to determine main branch should allow push."""
        mock_is_repo.return_value = True
        mock_branch.return_value = "feature"
        mock_pr_status.return_value = (False, None)
        with patch.object(git_protection, "get_main_branch", return_value=None):
            should_block, reason = git_protection.should_block_push()
            assert should_block is False
            assert reason is None


# =============================================================================
# Tests for main() function
# =============================================================================


class TestMain:
    """Tests for main() function with mocked stdin."""

    @patch.object(git_protection, "should_block_commit")
    @patch.object(git_protection, "is_commit_command")
    @patch("sys.stdin")
    def test_commit_blocked(self, mock_stdin: Any, mock_is_commit: Any, mock_should_block: Any) -> None:
        """Blocked commit should output deny decision."""
        mock_stdin.read.return_value = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "test"'},
        })
        mock_is_commit.return_value = True
        mock_should_block.return_value = (True, "Branch is merged")

        with pytest.raises(SystemExit) as excinfo:
            git_protection.main()

        assert excinfo.value.code == 0

    @patch.object(git_protection, "is_commit_command")
    @patch("sys.stdin")
    def test_non_git_command_allowed(self, mock_stdin: Any, mock_is_commit: Any) -> None:
        """Non-git command should be allowed."""
        mock_stdin.read.return_value = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
        mock_is_commit.return_value = False

        with pytest.raises(SystemExit) as excinfo:
            git_protection.main()

        assert excinfo.value.code == 0

    @patch("sys.stdin")
    def test_non_bash_tool_allowed(self, mock_stdin: Any) -> None:
        """Non-Bash tool should be allowed."""
        mock_stdin.read.return_value = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/tmp/test.txt"}})

        with pytest.raises(SystemExit) as excinfo:
            git_protection.main()

        assert excinfo.value.code == 0

    @patch("sys.stdin")
    def test_invalid_json_fails_closed(self, mock_stdin: Any) -> None:
        """Invalid JSON input should fail closed (block)."""
        mock_stdin.read.return_value = "not valid json"

        with pytest.raises(SystemExit) as excinfo:
            git_protection.main()

        # Should exit 0 but with deny output
        assert excinfo.value.code == 0

    @patch.object(git_protection, "should_block_push")
    @patch.object(git_protection, "is_push_command")
    @patch.object(git_protection, "is_commit_command")
    @patch("sys.stdin")
    def test_push_blocked(
        self, mock_stdin: Any, mock_is_commit: Any, mock_is_push: Any, mock_should_block: Any
    ) -> None:
        """Blocked push should output deny decision."""
        mock_stdin.read.return_value = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
        })
        mock_is_commit.return_value = False
        mock_is_push.return_value = True
        mock_should_block.return_value = (True, "On protected branch")

        with pytest.raises(SystemExit) as excinfo:
            git_protection.main()

        assert excinfo.value.code == 0


# =============================================================================
# Edge case and regression tests
# =============================================================================


class TestEdgeCases:
    """Edge cases and regression tests."""

    def test_empty_command(self) -> None:
        """Empty command should not match any subcommand."""
        assert not git_protection.is_git_subcommand("", "commit")
        assert not git_protection.is_git_subcommand("", "push")

    def test_whitespace_only_command(self) -> None:
        """Whitespace-only command should not match."""
        assert not git_protection.is_git_subcommand("   ", "commit")

    def test_git_in_path_not_command(self) -> None:
        """'git' in path should not trigger false positive."""
        assert not git_protection.is_git_subcommand("cat /home/user/git-repos/file.txt", "commit")

    def test_git_command_in_quotes(self) -> None:
        """git command in quotes (like for echo) still matches."""
        assert git_protection.is_git_subcommand('echo "git commit -m test"', "commit")

    def test_piped_git_command(self) -> None:
        """Piped git command should match."""
        assert git_protection.is_git_subcommand('git log --oneline | head -5 && git commit -m "test"', "commit")

    def test_git_with_env_vars(self) -> None:
        """git with environment variables should match."""
        assert git_protection.is_git_subcommand('GIT_AUTHOR_NAME="Test" git commit -m "msg"', "commit")

    def test_heredoc_with_git_command(self) -> None:
        """git command in heredoc should match."""
        cmd = """cat <<EOF
git commit -m "test"
EOF"""
        assert git_protection.is_git_subcommand(cmd, "commit")

    @patch.object(git_protection, "is_git_repository")
    def test_should_block_commit_not_called_for_non_repo(self, mock_is_repo: Any) -> None:
        """should_block_commit should short-circuit for non-repo."""
        mock_is_repo.return_value = False
        result = git_protection.should_block_commit('git commit -m "test"')
        assert result == (False, None)
        mock_is_repo.assert_called_once()

    def test_git_with_long_flags(self) -> None:
        """git with long flags before subcommand should match."""
        assert git_protection.is_git_subcommand("git --git-dir=/path/.git commit -m msg", "commit")
        assert git_protection.is_git_subcommand("git --work-tree=/path push origin main", "push")

    def test_commit_in_branch_name(self) -> None:
        """Branch name containing 'commit' should not cause false match."""
        # git checkout commit-fix is 'checkout' command, not 'commit'
        assert not git_protection.is_git_subcommand("git checkout commit-fix", "commit")
        assert git_protection.is_git_subcommand("git checkout commit-fix", "checkout")

    def test_push_in_branch_name(self) -> None:
        """Branch name containing 'push' should not cause false match."""
        assert not git_protection.is_git_subcommand("git checkout push-feature", "push")
        assert git_protection.is_git_subcommand("git checkout push-feature", "checkout")
