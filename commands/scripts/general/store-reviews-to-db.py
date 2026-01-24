#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Store completed review JSON to SQLite database for analytics.

This script runs AFTER the review flow completes. It reads the completed JSON file
(with all posted_at/resolved_at data) and stores it in SQLite for analytics.

Usage:
    uv run store-reviews-to-db.py <json_path>

The database is stored at: <project-root>/.claude/data/reviews.db
"""

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Schema for the reviews database
SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_number INTEGER NOT NULL,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(owner, repo, pr_number)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    source TEXT NOT NULL,
    thread_id TEXT,
    node_id TEXT,
    comment_id INTEGER,
    author TEXT,
    path TEXT,
    line INTEGER,
    body TEXT,
    priority TEXT,
    status TEXT,
    reply TEXT,
    skip_reason TEXT,
    posted_at TEXT,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_comments_review_id ON comments(review_id);
CREATE INDEX IF NOT EXISTS idx_comments_source ON comments(source);
CREATE INDEX IF NOT EXISTS idx_comments_status ON comments(status);
"""


def log(message: str) -> None:
    """Print message to stderr."""
    print(message, file=sys.stderr)


def get_project_root() -> Path:
    """Detect project root using git rev-parse --show-toplevel."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            log(f"Error: git rev-parse failed: {result.stderr.strip()}")
            sys.exit(1)
        return Path(result.stdout.strip())
    except subprocess.TimeoutExpired:
        log("Error: git command timed out")
        sys.exit(1)
    except FileNotFoundError:
        log("Error: git command not found")
        sys.exit(1)


def ensure_database_directory(db_path: Path) -> None:
    """Create database directory with 0700 permissions if needed."""
    db_dir = db_path.parent
    if not db_dir.exists():
        log(f"Creating directory: {db_dir}")
        db_dir.mkdir(parents=True, mode=0o700)


def create_tables(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript(SCHEMA)


def upsert_review(conn: sqlite3.Connection, owner: str, repo: str, pr_number: int) -> int:
    """Insert or update review record, returning the review_id."""
    cursor = conn.cursor()

    # Check if review already exists
    cursor.execute(
        "SELECT id FROM reviews WHERE owner = ? AND repo = ? AND pr_number = ?",
        (owner, repo, pr_number),
    )
    row = cursor.fetchone()

    created_at = datetime.now(timezone.utc).isoformat()

    if row:
        review_id: int = row[0]
        # Update created_at to reflect re-run
        cursor.execute(
            "UPDATE reviews SET created_at = ? WHERE id = ?",
            (created_at, review_id),
        )
    else:
        cursor.execute(
            "INSERT INTO reviews (owner, repo, pr_number, created_at) VALUES (?, ?, ?, ?)",
            (owner, repo, pr_number, created_at),
        )
        review_id = cursor.lastrowid or 0

    return review_id


def delete_existing_comments(conn: sqlite3.Connection, review_id: int) -> int:
    """Delete existing comments for this review_id. Returns count of deleted rows."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM comments WHERE review_id = ?", (review_id,))
    return cursor.rowcount


def insert_comment(conn: sqlite3.Connection, review_id: int, source: str, comment: dict[str, Any]) -> None:
    """Insert a single comment record."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO comments (
            review_id, source, thread_id, node_id, comment_id, author,
            path, line, body, priority, status, reply, skip_reason,
            posted_at, resolved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review_id,
            source,
            comment.get("thread_id"),
            comment.get("node_id"),
            comment.get("comment_id"),
            comment.get("author"),
            comment.get("path"),
            comment.get("line"),
            comment.get("body"),
            comment.get("priority"),
            comment.get("status"),
            comment.get("reply"),
            comment.get("skip_reason"),
            comment.get("posted_at"),
            comment.get("resolved_at"),
        ),
    )


def store_reviews(json_path: Path) -> None:
    """Main function to store reviews from JSON to SQLite."""
    # Read JSON file
    log(f"Reading JSON file: {json_path}")
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        log(f"Error: JSON file not found: {json_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        log(f"Error: Invalid JSON in file: {e}")
        sys.exit(1)

    # Extract review metadata (nested in metadata object)
    metadata = data.get("metadata", {})
    owner = metadata.get("owner", "")
    repo = metadata.get("repo", "")
    pr_number_raw = metadata.get("pr_number", 0)
    pr_number = int(pr_number_raw) if pr_number_raw else 0

    if not owner or not repo or not pr_number:
        log("Error: JSON missing required fields (owner, repo, pr_number)")
        sys.exit(1)

    log(f"Storing reviews for {owner}/{repo}#{pr_number}...")

    # Get project root and database path
    project_root = get_project_root()
    db_path = project_root / ".claude" / "data" / "reviews.db"

    log(f"Database: {db_path}")

    # Ensure directory exists
    ensure_database_directory(db_path)

    # Open database and perform operations in a transaction
    conn = sqlite3.connect(str(db_path))
    try:
        create_tables(conn)

        # Upsert review record
        review_id = upsert_review(conn, owner, repo, pr_number)

        # Delete existing comments for re-runs
        deleted_count = delete_existing_comments(conn, review_id)
        if deleted_count > 0:
            log(f"Deleted {deleted_count} existing comments (re-run)")

        # Count comments by source
        counts: dict[str, int] = {"human": 0, "qodo": 0, "coderabbit": 0}

        # Insert comments from each source
        for source in ["human", "qodo", "coderabbit"]:
            comments = data.get(source, [])
            for comment in comments:
                insert_comment(conn, review_id, source, comment)
                counts[source] += 1

        # Commit transaction
        conn.commit()

        total_comments = sum(counts.values())
        count_parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        count_summary = ", ".join(count_parts) if count_parts else "0 comments"

        log(f"Stored review with {total_comments} comments ({count_summary})")

    except sqlite3.Error as e:
        conn.rollback()
        log(f"Database error: {e}")
        sys.exit(1)
    finally:
        conn.close()

    # Delete JSON file after successful storage
    try:
        json_path.unlink()
        log(f"Deleted JSON file: {json_path}")
    except OSError as e:
        log(f"Warning: Could not delete JSON file: {e}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Store completed review JSON to SQLite database for analytics.")
    parser.add_argument(
        "json_path",
        type=Path,
        help="Path to the completed review JSON file",
    )
    args = parser.parse_args()

    json_path = args.json_path.resolve()

    if not json_path.exists():
        log(f"Error: JSON file does not exist: {json_path}")
        sys.exit(1)

    store_reviews(json_path)


if __name__ == "__main__":
    main()
