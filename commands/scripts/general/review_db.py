#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Query interface for the reviews SQLite database.

This module provides both a Python API (ReviewDB class) for importing into other scripts
and a CLI interface for AI/bash usage.

Database location: <git-root>/.claude/data/reviews.db

Usage as module:
    from review_db import ReviewDB
    db = ReviewDB()
    dismissed = db.get_dismissed_comments("myk-org", "claude-code-config")

Usage as CLI:
    uv run review_db.py dismissed --owner myk-org --repo claude-code-config [--json]
    uv run review_db.py find-similar --owner myk-org --repo claude-code-config --json < input.json
    uv run review_db.py stats --by-source [--json]
    uv run review_db.py stats --by-reviewer [--json]
    uv run review_db.py patterns [--min 2] [--json]
    uv run review_db.py query "SELECT * FROM comments WHERE status = 'skipped'" [--json]
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote


def log(message: str) -> None:
    """Print message to stderr."""
    print(message, file=sys.stderr)


def _get_git_root() -> Path:
    """Detect git root using git rev-parse --show-toplevel.

    Returns:
        Path to the git repository root.

    Raises:
        RuntimeError: If git command fails or times out.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git rev-parse failed: {result.stderr.strip()}")
        return Path(result.stdout.strip())
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("git command timed out") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("git command not found") from exc


def _body_similarity(body1: str, body2: str) -> float:
    """Calculate word overlap ratio between two bodies using Jaccard similarity."""
    tokens1 = set(re.findall(r"[a-z0-9]+", body1.lower()))
    tokens2 = set(re.findall(r"[a-z0-9]+", body2.lower()))
    if not tokens1 or not tokens2:
        return 0.0

    # Guard against huge bodies (e.g., pasted logs)
    # Sort before truncating for deterministic behavior
    if len(tokens1) > 2000:
        tokens1 = set(sorted(tokens1)[:2000])
    if len(tokens2) > 2000:
        tokens2 = set(sorted(tokens2)[:2000])

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)


class ReviewDB:
    """Query interface for the reviews SQLite database.

    This class provides methods to query review comments stored in the SQLite database.
    It can auto-detect the database path from the git root or accept an explicit path.

    Attributes:
        db_path: Path to the SQLite database file.

    Example:
        >>> db = ReviewDB()
        >>> dismissed = db.get_dismissed_comments("myk-org", "my-repo")
        >>> for comment in dismissed:
        ...     print(f"{comment['path']}:{comment['line']} - {comment['status']}")
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize ReviewDB with optional database path.

        Args:
            db_path: Path to the SQLite database. If None, auto-detects from git root.
                     The auto-detected path is: <git-root>/.claude/data/reviews.db

        Raises:
            RuntimeError: If git root detection fails when db_path is None.

        Example:
            >>> db = ReviewDB()  # Auto-detect from git root
            >>> db = ReviewDB(Path("/path/to/reviews.db"))  # Explicit path
        """
        if db_path is None:
            git_root = _get_git_root()
            self.db_path = git_root / ".claude" / "data" / "reviews.db"
        else:
            self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        """Create a database connection with row factory for dict results."""
        db_path = self.db_path.resolve()
        path_str = db_path.as_posix()
        db_uri = f"file:{quote(path_str, safe='/:')}?mode=ro"
        try:
            conn = sqlite3.connect(db_uri, uri=True)
        except sqlite3.Error as e:
            raise RuntimeError(f"Failed to open database (read-only): {db_path}") from e
        conn.row_factory = sqlite3.Row
        return conn

    def get_dismissed_comments(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """Get all not_addressed or skipped comments for a repository.

        Retrieves comments that were dismissed (not addressed or skipped) during
        review processing. Useful for identifying recurring patterns or auto-skip logic.

        Args:
            owner: GitHub repository owner (org or user).
            repo: GitHub repository name.

        Returns:
            List of dicts with keys: path, line, body, status, reply (reason for dismissal).
            Returns empty list if database doesn't exist or on error.

        Example:
            >>> db = ReviewDB()
            >>> dismissed = db.get_dismissed_comments("myk-org", "claude-code-config")
            >>> for c in dismissed:
            ...     print(f"{c['path']}:{c['line']} - {c['status']}: {c['reply']}")
        """
        if not self.db_path.exists():
            log(f"Database not found: {self.db_path}")
            return []

        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.path, c.line, c.body, c.status, c.reply, c.skip_reason, c.author
                FROM comments c
                JOIN reviews r ON c.review_id = r.id
                WHERE r.owner = ? AND r.repo = ?
                  AND c.status IN ('not_addressed', 'skipped')
                ORDER BY c.path, c.line
                """,
                (owner, repo),
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "path": row["path"],
                    "line": row["line"],
                    "body": row["body"],
                    "status": row["status"],
                    "reply": row["reply"] or row["skip_reason"],
                    "author": row["author"],
                })
            return results
        except sqlite3.Error as e:
            log(f"Database error: {e}")
            return []
        finally:
            conn.close()

    def find_similar_comment(
        self, owner: str, repo: str, path: str, body: str, threshold: float = 0.6
    ) -> dict[str, Any] | None:
        """Find a previously dismissed comment that matches the given path and body.

        Uses exact path match combined with body similarity (Jaccard word overlap).
        This is useful for auto-skip logic: if a similar comment was previously
        dismissed with a reason, the same reason may apply.

        Args:
            owner: GitHub repository owner (org or user).
            repo: GitHub repository name.
            path: File path to match exactly.
            body: Comment body to compare for similarity.
            threshold: Minimum similarity score (0.0-1.0) to consider a match.
                       Default 0.6 means 60% word overlap required.

        Returns:
            Dict with matching comment (path, line, body, status, reply, similarity)
            or None if no match found above threshold.

        Example:
            >>> db = ReviewDB()
            >>> match = db.find_similar_comment(
            ...     "myk-org", "my-repo",
            ...     "src/utils.py", "Add error handling for edge cases"
            ... )
            >>> if match:
            ...     print(f"Found similar: {match['reply']} (similarity: {match['similarity']:.2f})")
        """
        if not self.db_path.exists():
            log(f"Database not found: {self.db_path}")
            return None

        conn = self._connect()
        try:
            cursor = conn.cursor()
            # Get all dismissed comments for this path in the repo
            cursor.execute(
                """
                SELECT c.path, c.line, c.body, c.status, c.reply, c.skip_reason, c.author
                FROM comments c
                JOIN reviews r ON c.review_id = r.id
                WHERE r.owner = ? AND r.repo = ?
                  AND c.path = ?
                  AND c.status IN ('not_addressed', 'skipped')
                  AND c.body IS NOT NULL
                """,
                (owner, repo, path),
            )

            best_match: dict[str, Any] | None = None
            best_similarity = 0.0

            for row in cursor.fetchall():
                similarity = _body_similarity(body, row["body"])
                if similarity >= threshold and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = {
                        "path": row["path"],
                        "line": row["line"],
                        "body": row["body"],
                        "status": row["status"],
                        "reply": row["reply"] or row["skip_reason"],
                        "author": row["author"],
                        "similarity": similarity,
                    }

            return best_match
        except sqlite3.Error as e:
            log(f"Database error: {e}")
            return None
        finally:
            conn.close()

    def get_stats_by_source(self) -> list[dict[str, Any]]:
        """Get addressed rate statistics grouped by comment source.

        Calculates how often comments from each source (human, qodo, coderabbit)
        are addressed vs not_addressed vs skipped. Useful for understanding
        which review sources provide the most actionable feedback.

        Returns:
            List of dicts with keys: source, total, addressed, not_addressed,
            skipped, addressed_rate (as percentage string like "75.0%").
            Returns empty list if database doesn't exist or on error.

        Example:
            >>> db = ReviewDB()
            >>> stats = db.get_stats_by_source()
            >>> for s in stats:
            ...     print(f"{s['source']}: {s['addressed_rate']} addressed")
        """
        if not self.db_path.exists():
            log(f"Database not found: {self.db_path}")
            return []

        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    source,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'addressed' THEN 1 ELSE 0 END) as addressed,
                    SUM(CASE WHEN status = 'not_addressed' THEN 1 ELSE 0 END) as not_addressed,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
                FROM comments
                GROUP BY source
                ORDER BY total DESC
                """
            )

            results = []
            for row in cursor.fetchall():
                total = row["total"]
                addressed = row["addressed"]
                rate = (addressed / total * 100) if total > 0 else 0.0
                results.append({
                    "source": row["source"],
                    "total": total,
                    "addressed": addressed,
                    "not_addressed": row["not_addressed"],
                    "skipped": row["skipped"],
                    "addressed_rate": f"{rate:.1f}%",
                })
            return results
        except sqlite3.Error as e:
            log(f"Database error: {e}")
            return []
        finally:
            conn.close()

    def get_duplicate_patterns(self, min_occurrences: int = 2) -> list[dict[str, Any]]:
        """Find recurring dismissed patterns (same path + similar body).

        Identifies comments that appear multiple times with similar content,
        suggesting a pattern that should perhaps be configured as an auto-skip rule.

        Args:
            min_occurrences: Minimum number of times a pattern must appear.
                             Default is 2.

        Returns:
            List of dicts with keys: path, body_sample (first occurrence),
            occurrences (count), reason (most common reply).
            Returns empty list if database doesn't exist or on error.

        Example:
            >>> db = ReviewDB()
            >>> patterns = db.get_duplicate_patterns(min_occurrences=3)
            >>> for p in patterns:
            ...     print(f"{p['path']}: {p['occurrences']} occurrences")
            ...     print(f"  Sample: {p['body_sample'][:50]}...")
        """
        if not self.db_path.exists():
            log(f"Database not found: {self.db_path}")
            return []

        conn = self._connect()
        try:
            cursor = conn.cursor()

            # Get all dismissed comments
            cursor.execute(
                """
                SELECT path, body, reply, skip_reason
                FROM comments
                WHERE status IN ('not_addressed', 'skipped')
                  AND body IS NOT NULL
                  AND path IS NOT NULL
                ORDER BY path
                """
            )

            # Group by path and find similar bodies
            path_comments: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in cursor.fetchall():
                path_comments[row["path"]].append({
                    "body": row["body"],
                    "reason": row["reply"] or row["skip_reason"],
                })

            # Find patterns within each path
            patterns = []
            for path, comments in path_comments.items():
                # Simple clustering: group comments with >60% similarity
                clusters: list[list[dict[str, Any]]] = []
                for comment in comments:
                    added_to_cluster = False
                    for cluster in clusters:
                        # Compare with first item in cluster
                        if _body_similarity(comment["body"], cluster[0]["body"]) >= 0.6:
                            cluster.append(comment)
                            added_to_cluster = True
                            break
                    if not added_to_cluster:
                        clusters.append([comment])

                # Report clusters with min_occurrences or more
                for cluster in clusters:
                    if len(cluster) >= min_occurrences:
                        # Get most common reason
                        reasons = [c["reason"] for c in cluster if c["reason"]]
                        most_common_reason = Counter(reasons).most_common(1)[0][0] if reasons else None
                        patterns.append({
                            "path": path,
                            "body_sample": cluster[0]["body"],
                            "occurrences": len(cluster),
                            "reason": most_common_reason,
                        })

            # Sort by occurrences descending
            patterns.sort(key=lambda x: x["occurrences"], reverse=True)
            return patterns
        except sqlite3.Error as e:
            log(f"Database error: {e}")
            return []
        finally:
            conn.close()

    def get_reviewer_stats(self) -> list[dict[str, Any]]:
        """Get statistics grouped by reviewer author.

        Calculates how often comments from each reviewer are addressed.
        Useful for understanding which reviewers provide the most actionable feedback.

        Returns:
            List of dicts with keys: author, total, addressed, not_addressed, skipped.
            Returns empty list if database doesn't exist or on error.

        Example:
            >>> db = ReviewDB()
            >>> stats = db.get_reviewer_stats()
            >>> for s in stats:
            ...     print(f"{s['author']}: {s['total']} comments, {s['addressed']} addressed")
        """
        if not self.db_path.exists():
            log(f"Database not found: {self.db_path}")
            return []

        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COALESCE(author, 'unknown') as author,
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'addressed' THEN 1 ELSE 0 END) as addressed,
                    SUM(CASE WHEN status = 'not_addressed' THEN 1 ELSE 0 END) as not_addressed,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
                FROM comments
                GROUP BY author
                ORDER BY total DESC
                """
            )

            results = []
            for row in cursor.fetchall():
                results.append({
                    "author": row["author"],
                    "total": row["total"],
                    "addressed": row["addressed"],
                    "not_addressed": row["not_addressed"],
                    "skipped": row["skipped"],
                })
            return results
        except sqlite3.Error as e:
            log(f"Database error: {e}")
            return []
        finally:
            conn.close()

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Run a raw SELECT query against the database.

        Only SELECT statements are allowed for safety. This method is useful
        for ad-hoc queries and AI-driven exploration of the data.

        Args:
            sql: SQL SELECT statement to execute.
            params: Parameters to bind to the query (prevents SQL injection).

        Returns:
            List of dicts representing the result rows.
            Returns empty list if database doesn't exist or on error.

        Raises:
            ValueError: If the SQL statement is not a SELECT.

        Example:
            >>> db = ReviewDB()
            >>> results = db.query(
            ...     "SELECT path, COUNT(*) as cnt FROM comments WHERE status = ? GROUP BY path",
            ...     ("skipped",)
            ... )
            >>> for r in results:
            ...     print(f"{r['path']}: {r['cnt']} skipped")
        """
        # Safety check: only allow SELECT/CTE statements
        sql_stripped = sql.strip()

        # Helper functions to strip SQL comments and strings before safety checks
        def _strip_sql_comments(s: str) -> str:
            # Remove block comments then line comments
            s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
            s = re.sub(r"--[^\n]*", "", s)
            return s

        def _strip_sql_strings(s: str) -> str:
            # Remove single-quoted string literals (handles escaped '' within strings)
            return re.sub(r"'([^']|'')*'", "''", s)

        # Strip comments first, then compute uppercase for all checks
        # Use .lstrip() to handle queries with leading comments like "/*note*/ SELECT ..."
        sql_for_checks = _strip_sql_comments(sql_stripped).lstrip()
        sql_upper = sql_for_checks.upper()

        # Block multiple statements (semicolon separating statements, not in strings/comments)
        sql_stmt_check = _strip_sql_strings(sql_for_checks).rstrip(";")
        if ";" in sql_stmt_check:
            raise ValueError("Multiple SQL statements are not allowed")

        # Allow SELECT and WITH (CTE) as read-only entrypoints
        if not sql_upper.startswith(("SELECT", "WITH")):
            raise ValueError("Only SELECT/CTE queries are allowed for safety")

        # Block dangerous keywords that shouldn't appear in read-only queries
        dangerous_keywords = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "CREATE",
            "ATTACH",
            "DETACH",
            "PRAGMA",
        ]

        sql_upper_stripped = _strip_sql_strings(sql_upper)

        for keyword in dangerous_keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", sql_upper_stripped):
                raise ValueError(f"SQL keyword '{keyword}' is not allowed in queries")

        if not self.db_path.exists():
            log(f"Database not found: {self.db_path}")
            return []

        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)

            results = []
            for row in cursor.fetchall():
                results.append(dict(row))
            return results
        except sqlite3.Error as e:
            log(f"Database error: {e}")
            return []
        finally:
            conn.close()


def _format_table(data: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    """Format data as a human-readable table.

    Args:
        data: List of dicts to format.
        columns: Column order. If None, uses keys from first row.

    Returns:
        Formatted table string.
    """
    if not data:
        return "(no results)"

    if columns is None:
        columns = list(data[0].keys())

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in data:
        for col in columns:
            val = str(row.get(col, ""))
            # Truncate long values for display
            if len(val) > 60:
                val = val[:57] + "..."
            widths[col] = max(widths[col], len(val))

    # Build header
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    separator = "-+-".join("-" * widths[col] for col in columns)

    # Build rows
    rows = []
    for row in data:
        values = []
        for col in columns:
            val = str(row.get(col, ""))
            if len(val) > 60:
                val = val[:57] + "..."
            values.append(val.ljust(widths[col]))
        rows.append(" | ".join(values))

    return "\n".join([header, separator, *rows])


def _cmd_dismissed(args: argparse.Namespace) -> None:
    """Handle 'dismissed' subcommand."""
    db_path = Path(args.db_path) if args.db_path else None
    db = ReviewDB(db_path=db_path)
    results = db.get_dismissed_comments(args.owner, args.repo)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(_format_table(results, ["path", "line", "status", "reply", "author"]))


def _cmd_find_similar(args: argparse.Namespace) -> None:
    """Handle 'find-similar' subcommand."""
    # Read JSON from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        log(f"Error: Invalid JSON input: {e}")
        sys.exit(1)

    path = input_data.get("path", "")
    body = input_data.get("body", "")

    if not path or not body:
        log("Error: JSON must contain 'path' and 'body' fields")
        sys.exit(1)

    db_path = Path(args.db_path) if args.db_path else None
    db = ReviewDB(db_path=db_path)
    result = db.find_similar_comment(args.owner, args.repo, path, body, threshold=args.threshold)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result:
            print(f"Found similar comment (similarity: {result['similarity']:.2f}):")
            print(f"  Path: {result['path']}:{result['line']}")
            print(f"  Status: {result['status']}")
            print(f"  Reason: {result['reply']}")
            print(f"  Original body: {result['body'][:100]}...")
        else:
            print("No similar comment found")


def _cmd_stats(args: argparse.Namespace) -> None:
    """Handle 'stats' subcommand."""
    db_path = Path(args.db_path) if args.db_path else None
    db = ReviewDB(db_path=db_path)

    # Safely check flags with defaults (both default to False when not specified)
    by_source = getattr(args, "by_source", False)
    by_reviewer = getattr(args, "by_reviewer", False)

    # If neither flag is set, default to by-source behavior
    if not by_source and not by_reviewer:
        by_source = True

    if by_reviewer:
        results = db.get_reviewer_stats()
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(_format_table(results, ["author", "total", "addressed", "not_addressed", "skipped"]))
    elif by_source:
        results = db.get_stats_by_source()
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            columns = ["source", "total", "addressed", "not_addressed", "skipped", "addressed_rate"]
            print(_format_table(results, columns))


def _cmd_patterns(args: argparse.Namespace) -> None:
    """Handle 'patterns' subcommand."""
    db_path = Path(args.db_path) if args.db_path else None
    db = ReviewDB(db_path=db_path)
    results = db.get_duplicate_patterns(min_occurrences=args.min)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(_format_table(results, ["path", "occurrences", "reason", "body_sample"]))


def _cmd_query(args: argparse.Namespace) -> None:
    """Handle 'query' subcommand."""
    db_path = Path(args.db_path) if args.db_path else None
    db = ReviewDB(db_path=db_path)

    try:
        results = db.query(args.sql)
    except ValueError as e:
        log(f"Error: {e}")
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(_format_table(results))


def main() -> None:
    """Entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Query interface for the reviews SQLite database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get dismissed comments for auto-skip
  uv run review_db.py dismissed --owner myk-org --repo claude-code-config

  # Find similar comment (JSON from stdin)
  echo '{"path": "foo.py", "body": "Add error handling..."}' | \\
      uv run review_db.py find-similar --owner myk-org --repo claude-code-config --json

  # Stats by source
  uv run review_db.py stats --by-source --json

  # Duplicate patterns
  uv run review_db.py patterns --min 2

  # Raw query
  uv run review_db.py query "SELECT * FROM comments WHERE status = 'skipped'"

  # Use custom database path (for testing)
  uv run review_db.py stats --by-source --db-path /path/to/reviews.db
""",
    )

    # Global option for database path (useful for testing)
    parser.add_argument(
        "--db-path",
        help="Path to database file (default: auto-detect from git root)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # dismissed subcommand
    dismissed_parser = subparsers.add_parser(
        "dismissed",
        help="Get all not_addressed/skipped comments for a repo",
    )
    dismissed_parser.add_argument("--owner", required=True, help="Repository owner (org or user)")
    dismissed_parser.add_argument("--repo", required=True, help="Repository name")
    dismissed_parser.add_argument("--json", action="store_true", help="Output as JSON")
    dismissed_parser.set_defaults(func=_cmd_dismissed)

    # find-similar subcommand
    similar_parser = subparsers.add_parser(
        "find-similar",
        help="Find a previously dismissed comment matching path/body (reads JSON from stdin)",
    )
    similar_parser.add_argument("--owner", required=True, help="Repository owner (org or user)")
    similar_parser.add_argument("--repo", required=True, help="Repository name")
    similar_parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Minimum similarity threshold (0.0-1.0, default: 0.6)",
    )
    similar_parser.add_argument("--json", action="store_true", help="Output as JSON")
    similar_parser.set_defaults(func=_cmd_find_similar)

    # stats subcommand
    stats_parser = subparsers.add_parser(
        "stats",
        help="Get statistics (by source or by reviewer)",
    )
    stats_group = stats_parser.add_mutually_exclusive_group()
    stats_group.add_argument(
        "--by-source",
        action="store_true",
        help="Group by source (human/qodo/coderabbit)",
    )
    stats_group.add_argument(
        "--by-reviewer",
        action="store_true",
        help="Group by reviewer author",
    )
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")
    stats_parser.set_defaults(func=_cmd_stats)

    # patterns subcommand
    patterns_parser = subparsers.add_parser(
        "patterns",
        help="Find recurring dismissed patterns",
    )
    patterns_parser.add_argument(
        "--min",
        type=int,
        default=2,
        help="Minimum occurrences to report (default: 2)",
    )
    patterns_parser.add_argument("--json", action="store_true", help="Output as JSON")
    patterns_parser.set_defaults(func=_cmd_patterns)

    # query subcommand
    query_parser = subparsers.add_parser(
        "query",
        help="Run a raw SELECT query (SELECT only for safety)",
    )
    query_parser.add_argument("sql", help="SQL SELECT statement to execute")
    query_parser.add_argument("--json", action="store_true", help="Output as JSON")
    query_parser.set_defaults(func=_cmd_query)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
