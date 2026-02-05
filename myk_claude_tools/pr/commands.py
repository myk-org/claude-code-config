"""PR-related CLI commands."""

import click


@click.group()
def pr() -> None:
    """PR review and management commands."""
    pass


@pr.command("diff")
@click.argument("args", nargs=-1)
def pr_diff(args: tuple[str, ...]) -> None:
    """Fetch PR diff and metadata.

    Usage:
        pr diff <owner/repo> <pr_number>
        pr diff https://github.com/owner/repo/pull/123
        pr diff <pr_number>
    """
    from myk_claude_tools.pr.diff import run  # noqa: PLC0415

    run(list(args))


@pr.command("claude-md")
@click.argument("args", nargs=-1)
def pr_claude_md(args: tuple[str, ...]) -> None:
    """Fetch CLAUDE.md content for a PR's repository.

    Usage:
        pr claude-md <owner/repo> <pr_number>
        pr claude-md https://github.com/owner/repo/pull/123
        pr claude-md <pr_number>
    """
    from myk_claude_tools.pr.claude_md import run  # noqa: PLC0415

    run(list(args))


@pr.command("post-comment")
@click.argument("owner_repo")
@click.argument("pr_number")
@click.argument("commit_sha")
@click.argument("json_file")
def pr_post_comment(owner_repo: str, pr_number: str, commit_sha: str, json_file: str) -> None:
    """Post inline comments to a PR.

    Arguments:
        OWNER_REPO: Repository in format "owner/repo"
        PR_NUMBER: Pull request number
        COMMIT_SHA: The SHA of the commit to comment on
        JSON_FILE: Path to JSON file with comments, or "-" for stdin

    JSON format:
        [{"path": "file.py", "line": 42, "body": "Comment text"}]
    """
    from myk_claude_tools.pr.post_comment import run  # noqa: PLC0415

    run(owner_repo, pr_number, commit_sha, json_file)
