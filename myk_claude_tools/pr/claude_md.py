"""Fetch CLAUDE.md content for a repository.

Usage:
    myk-claude-tools pr claude-md <owner/repo> <pr_number>
    myk-claude-tools pr claude-md https://github.com/owner/repo/pull/123
    myk-claude-tools pr claude-md <pr_number>

Checks local files first if current git repo matches target repo,
then falls back to GitHub API.

Output: CLAUDE.md content (or empty if not found)
"""

from __future__ import annotations

import base64
import binascii
import re
import subprocess
from pathlib import Path

from myk_claude_tools.pr.common import PRInfo
from myk_claude_tools.pr.common import parse_args as _parse_args


def parse_args(args: list[str]) -> PRInfo:
    """Parse command line arguments for the claude-md command.

    Args:
        args: Command line arguments.

    Returns:
        PRInfo with owner, repo, and pr_number.
    """
    return _parse_args(args, command_name="claude-md", docstring=__doc__)


def is_current_repo(target_repo: str) -> bool:
    """Check if current git repo matches target repo.

    Args:
        target_repo: Target repository in owner/repo format.

    Returns:
        True if current repo matches target.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        current_remote = result.stdout.strip()
    except subprocess.CalledProcessError:
        return False

    # Extract owner/repo from remote URL (supports both HTTPS and SSH)
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", current_remote)
    if not match:
        return False

    current_repo_name = f"{match.group(1)}/{match.group(2)}"

    # Compare (case-insensitive)
    return current_repo_name.lower() == target_repo.lower()


def fetch_from_github(owner: str, repo: str, file_path: str) -> str | None:
    """Fetch file content from GitHub API.

    Args:
        owner: Repository owner.
        repo: Repository name.
        file_path: Path to the file in the repository.

    Returns:
        File content as string, or None if not found.
    """
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{owner}/{repo}/contents/{file_path}",
                "--jq",
                ".content",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        content_base64 = result.stdout.strip()
        if not content_base64:
            return None
        # Decode base64 content
        return base64.b64decode(content_base64).decode("utf-8")
    except (subprocess.CalledProcessError, binascii.Error, UnicodeDecodeError):
        return None


def run(args: list[str]) -> None:
    """Main entry point for the pr-claude-md command.

    Strategy: Check in order, stop on first match
    1. Check local ./CLAUDE.md if current repo matches
    2. Check local ./.claude/CLAUDE.md if current repo matches
    3. Fetch upstream CLAUDE.md from GitHub API
    4. Fetch upstream .claude/CLAUDE.md from GitHub API
    5. If nothing found, output empty string and exit 0

    Args:
        args: Command line arguments.
    """
    pr_info = parse_args(args)

    # Check if current git repo matches target
    if is_current_repo(pr_info.repo_full_name):
        # Check local ./CLAUDE.md
        local_claude_md = Path("./CLAUDE.md")
        if local_claude_md.is_file():
            print(local_claude_md.read_text())
            return

        # Check local ./.claude/CLAUDE.md
        local_claude_dir_md = Path("./.claude/CLAUDE.md")
        if local_claude_dir_md.is_file():
            print(local_claude_dir_md.read_text())
            return

    # Fetch upstream CLAUDE.md
    content = fetch_from_github(pr_info.owner, pr_info.repo, "CLAUDE.md")
    if content:
        print(content)
        return

    # Fetch upstream .claude/CLAUDE.md
    content = fetch_from_github(pr_info.owner, pr_info.repo, ".claude/CLAUDE.md")
    if content:
        print(content)
        return

    # Nothing found - output empty string
    print("")
