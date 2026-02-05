"""Review handler CLI commands."""

import sys

import click


@click.group()
def reviews() -> None:
    """Review handling commands."""
    pass


@reviews.command("fetch")
@click.argument("review_url", required=False, default="")
def reviews_fetch(review_url: str) -> None:
    """Fetch unresolved review threads from current PR.

    Fetches ALL unresolved review threads from the current branch's PR
    and categorizes them by source (human, qodo, coderabbit).

    Saves output to /tmp/claude/pr-<number>-reviews.json

    REVIEW_URL: Optional specific review URL for context
    (e.g., #pullrequestreview-XXX or #discussion_rXXX)
    """
    from myk_claude_tools.reviews.fetch import run  # noqa: PLC0415

    exit_code = run(review_url)
    sys.exit(exit_code)


@reviews.command("post")
@click.argument("json_path")
def reviews_post(json_path: str) -> None:
    """Post replies and resolve review threads.

    Reads a JSON file created by 'reviews fetch' and processed by an AI handler,
    then posts replies and resolves threads based on status.

    Updates the JSON file with posted_at timestamps.

    JSON_PATH: Path to JSON file with review data
    """
    from myk_claude_tools.reviews.post import run  # noqa: PLC0415

    run(json_path)


@reviews.command("store")
@click.argument("json_path")
def reviews_store(json_path: str) -> None:
    """Store completed review to database.

    Stores the completed review JSON to SQLite database for analytics.
    The database is stored at: <project-root>/.claude/data/reviews.db

    This command should run AFTER the review flow completes.
    The JSON file is deleted after successful storage.

    JSON_PATH: Path to the completed review JSON file
    """
    from myk_claude_tools.reviews.store import run  # noqa: PLC0415

    run(json_path)
