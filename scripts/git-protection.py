#!/usr/bin/env python3
"""PreToolUse hook - prevents commits on already-merged branches.

This hook intercepts git commit commands and blocks them if:
1. The current branch is already merged into the main branch
2. The current branch is the main/master branch itself

Allows commits on:
- Unmerged branches
- Amended commits that haven't been pushed yet
"""

import json
import subprocess
import sys


def get_current_branch():
    """Get the current git branch name. Returns None if detached HEAD or error."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return None if branch == "HEAD" else branch
        return None
    except Exception:
        return None


def get_main_branch():
    """Get the main branch name (main or master). Returns None if not found."""
    for branch_name in ["main", "master"]:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch_name],
                capture_output=True,
                timeout=2,
            )
            if result.returncode == 0:
                return branch_name
        except Exception:
            continue
    return None


def is_branch_merged(current_branch, main_branch):
    """Check if current_branch is merged into main_branch."""
    try:
        # Get the merge base between current and main
        merge_base_result = subprocess.run(
            ["git", "merge-base", current_branch, main_branch],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if merge_base_result.returncode != 0:
            return False

        merge_base = merge_base_result.stdout.strip()

        # Get HEAD of current branch
        branch_head_result = subprocess.run(
            ["git", "rev-parse", current_branch],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if branch_head_result.returncode != 0:
            return False

        branch_head = branch_head_result.stdout.strip()

        # Branch is merged if merge-base equals branch HEAD
        return merge_base == branch_head
    except Exception:
        return False


def is_branch_ahead_of_remote():
    """Check if current branch has unpushed commits or no remote tracking."""
    try:
        # First check if branch has a remote tracking branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        # If no remote tracking branch, allow amend (local-only branch)
        if result.returncode != 0:
            return True

        # Check if ahead of remote
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return "ahead" in result.stdout
        return False
    except Exception:
        return False


def is_git_repository():
    """Check if current directory is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_commit_command(command):
    """Check if command is a git commit command."""
    cmd = command.strip()
    return cmd.startswith("git commit")


def is_amend_with_unpushed_commits(command):
    """Check if this is an amend on unpushed commits (which should be allowed)."""
    return "--amend" in command and is_branch_ahead_of_remote()


def should_block_commit(command):
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
        # Detached HEAD - allow
        return False, None

    # Get main branch
    main_branch = get_main_branch()
    if not main_branch:
        # Can't determine main branch - allow
        return False, None

    # Block if on main/master branch
    if current_branch in ["main", "master"]:
        return True, f"Cannot commit directly to {current_branch} branch. Create a feature branch first."

    # Allow amend on unpushed commits
    if is_amend_with_unpushed_commits(command):
        return False, None

    # Check if branch is merged
    if is_branch_merged(current_branch, main_branch):
        return True, (
            f"Branch '{current_branch}' is already merged into '{main_branch}'. "
            f"Create a new branch for additional changes."
        )

    return False, None


def main():
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
                            "permissionDecisionReason": reason
                        }
                    }
                    print(json.dumps(output))
                    sys.exit(0)

        # Allow everything else
        sys.exit(0)

    except Exception:
        # Fail open on errors
        sys.exit(0)


if __name__ == "__main__":
    main()
