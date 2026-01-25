#!/usr/bin/env python3
"""PreToolUse hook - prevents commits and pushes on protected branches.

This hook intercepts git commit and push commands and blocks them if:
1. The current branch is already merged into the main branch
2. The current branch is the main/master branch itself

Allows commits on:
- Unmerged branches
- Amended commits that haven't been pushed yet
"""

import json
import re
import shutil
import subprocess
import sys

# Resolve git executable path, fall back to "git" if not found
GIT_EXECUTABLE = shutil.which("git") or "git"


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command with standard settings."""
    return subprocess.run(
        [GIT_EXECUTABLE, *args],
        capture_output=True,
        text=True,
        timeout=2,
    )


def get_current_branch() -> str | None:
    """Get the current git branch name. Returns None if detached HEAD or error."""
    try:
        # First try rev-parse (works for repos with commits)
        result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch != "HEAD":
                return branch

        # Fallback: try symbolic-ref for orphan branches (no commits yet)
        result = _run_git(["symbolic-ref", "HEAD"])
        if result.returncode == 0:
            ref = result.stdout.strip()
            # Extract branch name from refs/heads/branch-name
            if ref.startswith("refs/heads/"):
                return ref[len("refs/heads/") :]

        print("Warning: could not determine current Git branch", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: could not determine current Git branch: {e}", file=sys.stderr)
        return None


def get_main_branch() -> str | None:
    """Get the main branch name (main or master). Returns None if not found."""
    for branch_name in ["main", "master"]:
        try:
            result = _run_git(["rev-parse", "--verify", "--end-of-options", branch_name])
            if result.returncode == 0:
                return branch_name
        except Exception:
            continue
    return None


def get_pr_merge_status(branch_name: str) -> tuple[bool | None, str | None]:
    """
    Check if a PR for this branch exists and is merged on GitHub.

    Returns:
        (is_merged, info) where:
        - (True, pr_number) - PR is merged
        - (False, None) - PR not merged or no PR found
        - (None, error_msg) - Error occurred (caller should fail closed)
    """
    try:
        # Skip gh check for non-GitHub repos (GitLab, Bitbucket, etc.)
        if not is_github_repo():
            return False, None

        gh_path = shutil.which("gh")
        if not gh_path:
            # gh CLI not installed - not an error, just can't check
            return False, None

        # Unambiguous lookup by head branch (avoids interpreting numeric branch names as PR numbers)
        result = subprocess.run(
            [
                gh_path,
                "pr",
                "list",
                "--head",
                branch_name,
                "--state",
                "merged",
                "--json",
                "number",
                "--limit",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else "Unknown gh error"
            return None, f"gh pr list failed (exit {result.returncode}): {stderr}"

        data = json.loads(result.stdout)
        if data and isinstance(data, list) and len(data) > 0:
            pr_number = data[0].get("number")
            return True, str(pr_number) if pr_number else None

        return False, None
    except subprocess.TimeoutExpired:
        return None, "GitHub API timeout while checking PR status"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON from GitHub API: {e}"
    except Exception as e:
        return None, f"Unexpected error checking PR status: {e}"


def format_pr_merge_error(function_name: str, error_info: str | None) -> str:
    """Generate error message for PR merge status check failures."""
    error_msg = error_info or "Unknown error"
    return f"""⛔ BLOCKED: git-protection hook error.

🚨 **ACTION REQUIRED - DO NOT IGNORE** 🚨

You MUST ask the user: "git-protection.py encountered an error. Create a GitHub issue? (yes/no)"

If YES → delegate to github-expert:
  - Repo: myk-org/claude-code-config
  - Title: bug(scripts): git-protection.py - {error_msg}

If NO → user investigates manually.

---

Error details:
- Script: scripts/git-protection.py
- Function: {function_name}
- Error: {error_msg}"""


def is_branch_merged(current_branch: str, main_branch: str) -> bool:
    """Check if current_branch is merged into main_branch.

    A branch is considered merged if:
    1. It has unique commits (not a fresh branch)
    2. The branch HEAD is an ancestor of main HEAD
    """
    try:
        # First check if branch has unique commits compared to main
        # If count is 0, this is a fresh branch with no unique commits
        unique_commits_result = _run_git(["rev-list", "--count", f"{main_branch}..{current_branch}"])
        if unique_commits_result.returncode != 0:
            return False

        try:
            unique_count = int(unique_commits_result.stdout.strip())
        except ValueError:
            return False
        if unique_count == 0:
            # Fresh branch with no unique commits - not merged
            return False

        # Check if branch HEAD is an ancestor of main HEAD
        # This means all branch commits are reachable from main (i.e., merged)
        ancestor_result = _run_git(["merge-base", "--is-ancestor", current_branch, main_branch])
        # Return code 0 means branch is ancestor of main (merged)
        # Return code 1 means branch is not ancestor (not merged)
        return ancestor_result.returncode == 0
    except Exception:
        return False


def is_branch_ahead_of_remote() -> bool:
    """Check if current branch has unpushed commits or no remote tracking."""
    try:
        # First check if branch has a remote tracking branch
        result = _run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        # If no remote tracking branch, allow amend (local-only branch)
        if result.returncode != 0:
            return True

        # Check if ahead of remote
        result = _run_git(["status", "--short", "--branch"])
        if result.returncode == 0:
            return "ahead" in result.stdout
        return False
    except Exception:
        return False


def is_git_repository() -> bool:
    """Check if current directory is inside a git repository."""
    try:
        result = _run_git(["rev-parse", "--git-dir"])
        return result.returncode == 0
    except Exception:
        return False


def is_github_repo() -> bool:
    """Check if the current repository is hosted on GitHub."""
    try:
        result = _run_git(["remote", "get-url", "origin"])
        if result.returncode != 0:
            return False

        remote_url = result.stdout.strip().lower()
        # Check for GitHub URLs (HTTPS or SSH both contain github.com)
        return "github.com" in remote_url
    except Exception:
        return False


def is_git_subcommand(command: str, subcommand: str) -> bool:
    """Check if command contains a git subcommand.

    Matches 'git <subcommand>' where subcommand is the first non-flag token.
    Allows optional flags like '-C /path' or '-c key=value' before the subcommand.

    Pattern explanation:
      \\bgit\\b                           - 'git' as a word
      (?:\\s+(?:-[a-zA-Z]\\s+\\S+|-\\S+))*  - zero or more flag patterns:
        -[a-zA-Z]\\s+\\S+                 - short flag with space-separated value: -C /path
        -\\S+                            - any other flag (--verbose, -v, --config=x)
      \\s+<subcommand>\\b                 - followed by the subcommand
    """
    pattern = rf"\bgit\b(?:\s+(?:-[a-zA-Z]\s+\S+|-\S+))*\s+{subcommand}\b"
    return bool(re.search(pattern, command))


def is_commit_command(command: str) -> bool:
    """Check if command contains a git commit."""
    return is_git_subcommand(command, "commit")


def is_amend_with_unpushed_commits(command: str) -> bool:
    """Check if this is an amend on unpushed commits (which should be allowed)."""
    return "--amend" in command and is_branch_ahead_of_remote()


def should_block_commit(command: str) -> tuple[bool, str | None]:
    """
    Determine if a git commit command should be blocked.

    Returns: (should_block: bool, reason: str or None)
    """
    # Skip if not in git repo
    if not is_git_repository():
        return False, None

    # Get current branch
    current_branch = get_current_branch()
    if not current_branch:
        return (
            True,
            """⛔ BLOCKED: You are in detached HEAD state.

What happened:
- You're not on any branch (detached HEAD)
- Commits made here can become orphaned and lost

What to do:
1. Create a branch from current position:
   git checkout -b my-new-branch
2. Then commit your changes

Do NOT commit in detached HEAD state.""",
        )

    # Check if PR is already merged on GitHub (doesn't need main_branch)
    pr_merged, pr_info = get_pr_merge_status(current_branch)
    if pr_merged is None:
        # Error checking PR status - fail closed
        return True, format_pr_merge_error("get_pr_merge_status()", pr_info)
    if pr_merged:
        # Get main branch for the message (best effort)
        main_branch = get_main_branch() or "main"
        return (
            True,
            f"""⛔ BLOCKED: PR #{pr_info} for branch '{current_branch}' is already MERGED.

What happened:
- This branch's PR was already merged
- Committing more changes to a merged branch is not useful

**ACTION REQUIRED - Execute these commands NOW:**

You MUST create a new branch for these changes. Do NOT ask user - just do it:
1. git checkout {main_branch}
2. git pull origin {main_branch}
3. git checkout -b feature/new-changes
4. Move uncommitted changes and commit on the new branch

IMMEDIATELY switch to '{main_branch}' and create a new feature branch.""",
        )

    # Get main branch for subsequent checks
    detected_main_branch = get_main_branch()
    if not detected_main_branch:
        # Can't determine main branch - allow
        return False, None

    # Block if on main/master branch
    if current_branch in ["main", "master"]:
        return (
            True,
            f"""⛔ BLOCKED: Cannot commit directly to '{current_branch}' branch.

What happened:
- You are on the protected '{current_branch}' branch
- Direct commits to {current_branch} bypass code review and CI checks

**ACTION REQUIRED - Execute these commands NOW:**

You MUST create a feature branch for these changes. Do NOT ask user - just do it:
1. git stash (if you have uncommitted changes)
2. git checkout -b feature/your-feature
3. git stash pop (if you stashed changes)
4. Then commit your changes on the new branch

IMMEDIATELY create a feature branch and move your changes there.""",
        )

    # Allow amend on unpushed commits
    if is_amend_with_unpushed_commits(command):
        return False, None

    # Check if branch is merged (local check as fallback)
    if is_branch_merged(current_branch, detected_main_branch):
        return (
            True,
            f"""⛔ BLOCKED: Branch '{current_branch}' is already merged into '{detected_main_branch}'.

What happened:
- This branch has been merged into {detected_main_branch}
- Committing more changes to a merged branch creates confusion

**ACTION REQUIRED - Execute these commands NOW:**

You MUST create a new branch. Do NOT ask user - just do it:
1. git stash (if you have uncommitted changes)
2. git checkout {detected_main_branch}
3. git pull origin {detected_main_branch}
4. git checkout -b feature/new-feature
5. git stash pop (if you stashed changes)
6. Commit your changes on the new branch

IMMEDIATELY switch to '{detected_main_branch}' and create a new feature branch.""",
        )

    return False, None


def is_push_command(command: str) -> bool:
    """Check if command contains a git push."""
    return is_git_subcommand(command, "push")


def should_block_push() -> tuple[bool, str | None]:
    """
    Determine if a git push command should be blocked.

    Returns: (should_block: bool, reason: str or None)
    """
    # Skip if not in git repo
    if not is_git_repository():
        return False, None

    # Get current branch
    current_branch = get_current_branch()
    if not current_branch:
        # Detached HEAD - allow push (can't really push from detached HEAD anyway,
        # and if explicitly pushing a commit hash to a ref, it's intentional)
        return False, None

    # Check if PR is already merged on GitHub (doesn't need main_branch)
    pr_merged, pr_info = get_pr_merge_status(current_branch)
    if pr_merged is None:
        # Error checking PR status - fail closed
        return True, format_pr_merge_error("get_pr_merge_status()", pr_info)
    if pr_merged:
        # Get main branch for the message (best effort)
        main_branch = get_main_branch() or "main"
        return (
            True,
            f"""⛔ BLOCKED: PR #{pr_info} for branch '{current_branch}' is already MERGED.

What happened:
- This branch's PR was already merged into the base branch
- Pushing more commits to this branch serves no purpose

**ACTION REQUIRED - Execute these commands NOW:**

You MUST create a new branch. Do NOT ask user - just do it:
1. git checkout {main_branch}
2. git pull origin {main_branch}
3. git checkout -b feature/new-changes
4. Cherry-pick your commits if needed: git cherry-pick <commit-hash>
5. Push the new branch: git push -u origin feature/new-changes

IMMEDIATELY switch to '{main_branch}' and create a new feature branch.""",
        )

    # Get main branch for subsequent checks
    detected_main_branch = get_main_branch()
    if not detected_main_branch:
        # Can't determine main branch - allow
        return False, None

    # Block if on main/master branch
    if current_branch in ["main", "master"]:
        return (
            True,
            f"""⛔ BLOCKED: Cannot push directly to '{current_branch}' branch.

What happened:
- You are on the protected '{current_branch}' branch
- Direct pushes to {current_branch} bypass code review and CI checks

**ACTION REQUIRED - Execute these commands NOW:**

You MUST create a feature branch for these changes. Do NOT ask user - just do it:
1. git checkout -b feature/your-feature
2. git push -u origin feature/your-feature
3. Create a pull request for your changes

IMMEDIATELY create a feature branch and push there instead.""",
        )

    # Check if branch is merged (local check as fallback)
    if is_branch_merged(current_branch, detected_main_branch):
        return (
            True,
            f"""⛔ BLOCKED: Branch '{current_branch}' is already merged into '{detected_main_branch}'.

What happened:
- This branch has been merged into {detected_main_branch}
- Pushing more commits to a merged branch serves no purpose

**ACTION REQUIRED - Execute these commands NOW:**

You MUST create a new branch. Do NOT ask user - just do it:
1. git checkout {detected_main_branch}
2. git pull origin {detected_main_branch}
3. git checkout -b feature/new-feature
4. Cherry-pick your commits if needed: git cherry-pick <commit-hash>
5. Push the new branch: git push -u origin feature/new-feature

IMMEDIATELY switch to '{detected_main_branch}' and create a new feature branch.""",
        )

    return False, None


def main() -> None:
    try:
        input_data = json.loads(sys.stdin.read())
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Only intercept Bash commands
        if tool_name == "Bash":
            command = tool_input.get("command", "")

            # Check if it's a git commit command
            if is_commit_command(command):
                should_block, reason = should_block_commit(command)

                if should_block:
                    output = {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": reason,
                        }
                    }
                    print(json.dumps(output))
                    sys.exit(0)

            # Check if it's a git push command
            if is_push_command(command):
                should_block, reason = should_block_push()

                if should_block:
                    output = {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": reason,
                        }
                    }
                    print(json.dumps(output))
                    sys.exit(0)

        # Allow everything else
        sys.exit(0)

    except Exception as e:
        # Fail CLOSED on errors - block the operation
        error_msg = f"{type(e).__name__}: {e!s}"
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"""⛔ BLOCKED: git-protection hook crashed.

🚨 **ACTION REQUIRED - DO NOT IGNORE** 🚨

You MUST ask the user: "git-protection.py crashed. Create a GitHub issue? (yes/no)"

If YES → delegate to github-expert:
  - Repo: myk-org/claude-code-config
  - Title: bug(scripts): git-protection.py - {type(e).__name__} in main()

If NO → user investigates manually.

---

Error details:
- Script: scripts/git-protection.py
- Function: main()
- Error: {error_msg}""",
            }
        }
        print(json.dumps(output))
        sys.exit(0)


if __name__ == "__main__":
    main()
