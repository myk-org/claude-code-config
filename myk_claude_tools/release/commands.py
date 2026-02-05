"""Release-related CLI commands."""

import click

from myk_claude_tools.release.create import run as create_run
from myk_claude_tools.release.info import run as info_run


@click.group()
def release() -> None:
    """GitHub release commands."""
    pass


@release.command("info")
@click.option("--repo", help="Repository in owner/repo format")
def release_info(repo: str | None) -> None:
    """Fetch release validation info and commits since last tag."""
    info_run(repo)


@release.command("create")
@click.argument("owner_repo")
@click.argument("tag")
@click.argument("changelog_file")
@click.option("--prerelease", is_flag=True, help="Mark as pre-release")
@click.option("--draft", is_flag=True, help="Create as draft")
@click.option("--target", help="Target branch for the release")
def release_create(
    owner_repo: str,
    tag: str,
    changelog_file: str,
    prerelease: bool,
    draft: bool,
    target: str | None,
) -> None:
    """Create a GitHub release."""
    create_run(owner_repo, tag, changelog_file, prerelease, draft, target)
