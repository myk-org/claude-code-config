"""Main CLI entry point for myk-claude-tools."""

import click

from myk_claude_tools.db import commands as db_commands
from myk_claude_tools.pr import commands as pr_commands
from myk_claude_tools.release import commands as release_commands
from myk_claude_tools.reviews import commands as reviews_commands


@click.group()
@click.version_option()
def cli() -> None:
    """CLI utilities for Claude Code plugins."""
    pass


cli.add_command(pr_commands.pr, name="pr")
cli.add_command(release_commands.release, name="release")
cli.add_command(reviews_commands.reviews, name="reviews")
cli.add_command(db_commands.db, name="db")


def main() -> None:
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
