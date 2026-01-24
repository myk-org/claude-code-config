"""Tests for review_db module."""

import json
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Add scripts directory to path for import
SCRIPTS_DIR = Path(__file__).parent.parent / "commands" / "scripts" / "general"
sys.path.insert(0, str(SCRIPTS_DIR))

from review_db import ReviewDB, _body_similarity  # noqa: E402

# Schema for test database (same as production)
SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_number INTEGER NOT NULL,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    created_at TEXT NOT NULL
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
"""


@pytest.fixture
def temp_db() -> Generator[Path, None, None]:
    """Create a temporary database with test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)

    # Insert test review
    conn.execute(
        "INSERT INTO reviews (pr_number, owner, repo, commit_sha, created_at) VALUES (?, ?, ?, ?, ?)",
        (123, "test-org", "test-repo", "abc123def456", "2024-01-01T00:00:00Z"),  # pragma: allowlist secret
    )
    review_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Insert test comments
    # Format: (review_id, source, path, line, body, priority, status, reply, author)
    test_comments = [
        (
            review_id,
            "qodo",
            "path/to/file.py",
            10,
            "Add error handling",
            "HIGH",
            "addressed",
            "Done",
            "qodo-code-review",
        ),
        (
            review_id,
            "qodo",
            "path/to/file.py",
            20,
            "Add skip option to prompt",
            "MEDIUM",
            "not_addressed",
            "Not addressed: User declined",
            "qodo-code-review",
        ),
        (
            review_id,
            "coderabbit",
            "path/to/other.py",
            5,
            "Add type hints",
            "LOW",
            "skipped",
            None,
            "coderabbitai",
        ),
        (
            review_id,
            "human",
            "README.md",
            1,
            "Fix typo",
            "LOW",
            "addressed",
            "Done",
            "reviewer1",
        ),
    ]

    for (
        rev_id,
        source,
        path,
        line,
        body,
        priority,
        status,
        reply,
        author,
    ) in test_comments:
        conn.execute(
            """INSERT INTO comments
               (review_id, source, path, line, body, priority, status, reply, author)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rev_id, source, path, line, body, priority, status, reply, author),
        )

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def empty_db() -> Generator[Path, None, None]:
    """Create an empty temporary database with schema only."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


class TestBodySimilarity:
    """Tests for the _body_similarity helper function."""

    def test_identical_bodies(self) -> None:
        """Test that identical bodies have similarity of 1.0."""
        body = "Add error handling for edge cases"
        assert _body_similarity(body, body) == 1.0

    def test_completely_different_bodies(self) -> None:
        """Test that completely different bodies have similarity of 0.0."""
        body1 = "foo bar baz"
        body2 = "one two three"
        assert _body_similarity(body1, body2) == 0.0

    def test_partial_overlap(self) -> None:
        """Test partial word overlap."""
        body1 = "Add error handling here"
        body2 = "Add error handling for edge cases"
        similarity = _body_similarity(body1, body2)
        # Common: "Add", "error", "handling" (3 words)
        # Union: "Add", "error", "handling", "here", "for", "edge", "cases" (7 words)
        assert similarity == pytest.approx(3 / 7)

    def test_empty_body(self) -> None:
        """Test that empty bodies return 0.0."""
        assert _body_similarity("", "some text") == 0.0
        assert _body_similarity("some text", "") == 0.0
        assert _body_similarity("", "") == 0.0

    def test_case_insensitive(self) -> None:
        """Test that comparison is case-insensitive."""
        body1 = "ADD ERROR HANDLING"
        body2 = "add error handling"
        assert _body_similarity(body1, body2) == 1.0


class TestReviewDB:
    """Tests for ReviewDB class."""

    def test_init_with_explicit_path(self, temp_db: Path) -> None:
        """Test initialization with explicit database path."""
        db = ReviewDB(db_path=temp_db)
        assert db.db_path == temp_db

    def test_get_dismissed_comments(self, temp_db: Path) -> None:
        """Test getting dismissed comments."""
        db = ReviewDB(db_path=temp_db)
        dismissed = db.get_dismissed_comments("test-org", "test-repo")

        assert len(dismissed) == 2  # not_addressed + skipped
        statuses = {c["status"] for c in dismissed}
        assert statuses == {"not_addressed", "skipped"}

    def test_get_dismissed_comments_empty_result(self, temp_db: Path) -> None:
        """Test getting dismissed comments when none exist."""
        db = ReviewDB(db_path=temp_db)
        dismissed = db.get_dismissed_comments("nonexistent-org", "nonexistent-repo")

        assert dismissed == []

    def test_get_dismissed_comments_nonexistent_db(self, tmp_path: Path) -> None:
        """Test getting dismissed comments when database doesn't exist."""
        db = ReviewDB(db_path=tmp_path / "nonexistent.db")
        dismissed = db.get_dismissed_comments("test-org", "test-repo")

        assert dismissed == []

    def test_find_similar_comment_exact_match(self, temp_db: Path) -> None:
        """Test finding similar comment with exact path match."""
        db = ReviewDB(db_path=temp_db)

        # Should find the "Add skip option" comment
        similar = db.find_similar_comment(
            "test-org",
            "test-repo",
            "path/to/file.py",
            "Add skip option to the user prompt",
            threshold=0.5,
        )

        assert similar is not None
        assert "skip" in similar["body"].lower()
        assert similar["status"] == "not_addressed"
        assert "similarity" in similar

    def test_find_similar_comment_no_match(self, temp_db: Path) -> None:
        """Test no match when body is too different."""
        db = ReviewDB(db_path=temp_db)

        similar = db.find_similar_comment(
            "test-org",
            "test-repo",
            "path/to/file.py",
            "Completely unrelated comment about something else entirely",
            threshold=0.5,
        )

        assert similar is None

    def test_find_similar_comment_wrong_path(self, temp_db: Path) -> None:
        """Test no match when path doesn't match."""
        db = ReviewDB(db_path=temp_db)

        # Same body as existing comment but different path
        similar = db.find_similar_comment(
            "test-org",
            "test-repo",
            "nonexistent/path.py",
            "Add skip option to prompt",
            threshold=0.5,
        )

        assert similar is None

    def test_find_similar_comment_nonexistent_db(self, tmp_path: Path) -> None:
        """Test finding similar comment when database doesn't exist."""
        db = ReviewDB(db_path=tmp_path / "nonexistent.db")
        similar = db.find_similar_comment("test-org", "test-repo", "path/to/file.py", "Some comment", threshold=0.5)

        assert similar is None

    def test_find_similar_comment_returns_best_match(self, temp_db: Path) -> None:
        """Test that the best match is returned when multiple exist."""
        # Add another comment with different similarity
        conn = sqlite3.connect(str(temp_db))
        review_id = conn.execute(
            "SELECT id FROM reviews WHERE owner = ? AND repo = ?",
            ("test-org", "test-repo"),
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO comments
               (review_id, source, path, line, body, status, author)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                review_id,
                "human",
                "path/to/file.py",
                30,
                "Add skip functionality to the main prompt interface",
                "skipped",
                "reviewer2",
            ),
        )
        conn.commit()
        conn.close()

        db = ReviewDB(db_path=temp_db)
        similar = db.find_similar_comment(
            "test-org",
            "test-repo",
            "path/to/file.py",
            "Add skip option to the user prompt",
            threshold=0.3,
        )

        assert similar is not None
        # Should return the most similar one
        assert similar["similarity"] > 0.3

    def test_get_stats_by_source(self, temp_db: Path) -> None:
        """Test stats by source."""
        db = ReviewDB(db_path=temp_db)
        stats = db.get_stats_by_source()

        assert len(stats) >= 1
        # Find qodo stats
        qodo_stats = next((s for s in stats if s["source"] == "qodo"), None)
        assert qodo_stats is not None
        assert qodo_stats["total"] == 2
        assert qodo_stats["addressed"] == 1
        assert qodo_stats["not_addressed"] == 1
        assert qodo_stats["skipped"] == 0
        assert "addressed_rate" in qodo_stats
        assert qodo_stats["addressed_rate"] == "50.0%"

    def test_get_stats_by_source_empty_db(self, empty_db: Path) -> None:
        """Test stats by source with empty database."""
        db = ReviewDB(db_path=empty_db)
        stats = db.get_stats_by_source()

        assert stats == []

    def test_get_stats_by_source_nonexistent_db(self, tmp_path: Path) -> None:
        """Test stats by source when database doesn't exist."""
        db = ReviewDB(db_path=tmp_path / "nonexistent.db")
        stats = db.get_stats_by_source()

        assert stats == []

    def test_get_reviewer_stats(self, temp_db: Path) -> None:
        """Test stats by reviewer."""
        db = ReviewDB(db_path=temp_db)
        stats = db.get_reviewer_stats()

        assert len(stats) >= 1
        authors = {s["author"] for s in stats}
        assert "qodo-code-review" in authors
        assert "coderabbitai" in authors
        assert "reviewer1" in authors

        # Find qodo-code-review stats
        qodo_reviewer = next((s for s in stats if s["author"] == "qodo-code-review"), None)
        assert qodo_reviewer is not None
        assert qodo_reviewer["total"] == 2
        assert qodo_reviewer["addressed"] == 1
        assert qodo_reviewer["not_addressed"] == 1

    def test_get_reviewer_stats_empty_db(self, empty_db: Path) -> None:
        """Test stats by reviewer with empty database."""
        db = ReviewDB(db_path=empty_db)
        stats = db.get_reviewer_stats()

        assert stats == []

    def test_get_duplicate_patterns(self, temp_db: Path) -> None:
        """Test finding duplicate patterns."""
        # Add duplicate comments to create a pattern
        conn = sqlite3.connect(str(temp_db))
        review_id = conn.execute(
            "SELECT id FROM reviews WHERE owner = ? AND repo = ?",
            ("test-org", "test-repo"),
        ).fetchone()[0]

        # Add 3 similar comments to create a pattern
        for i in range(3):
            conn.execute(
                """INSERT INTO comments
                   (review_id, source, path, line, body, status, reply, author)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review_id,
                    "qodo",
                    "src/utils.py",
                    10 + i,
                    "Add error handling for this function",
                    "not_addressed",
                    "Too generic",
                    "qodo-code-review",
                ),
            )
        conn.commit()
        conn.close()

        db = ReviewDB(db_path=temp_db)
        patterns = db.get_duplicate_patterns(min_occurrences=2)

        assert len(patterns) >= 1
        # Find the pattern we just created
        utils_pattern = next((p for p in patterns if p["path"] == "src/utils.py"), None)
        assert utils_pattern is not None
        assert utils_pattern["occurrences"] >= 2
        assert "error handling" in utils_pattern["body_sample"].lower()

    def test_get_duplicate_patterns_no_duplicates(self, temp_db: Path) -> None:
        """Test finding duplicate patterns when none exist."""
        db = ReviewDB(db_path=temp_db)
        # All comments in temp_db have different bodies, so no patterns with min=2
        patterns = db.get_duplicate_patterns(min_occurrences=5)

        assert patterns == []

    def test_query_select_only(self, temp_db: Path) -> None:
        """Test that only SELECT queries are allowed."""
        db = ReviewDB(db_path=temp_db)

        # SELECT should work
        result = db.query("SELECT COUNT(*) as count FROM comments")
        assert len(result) == 1
        assert result[0]["count"] == 4

    def test_query_with_params(self, temp_db: Path) -> None:
        """Test query with parameters."""
        db = ReviewDB(db_path=temp_db)

        result = db.query("SELECT COUNT(*) as count FROM comments WHERE status = ?", ("addressed",))
        assert len(result) == 1
        assert result[0]["count"] == 2

    def test_query_rejects_delete(self, temp_db: Path) -> None:
        """Test that DELETE queries are rejected."""
        db = ReviewDB(db_path=temp_db)

        with pytest.raises(ValueError, match="Only SELECT/CTE queries are allowed"):
            db.query("DELETE FROM comments")

    def test_query_rejects_update(self, temp_db: Path) -> None:
        """Test that UPDATE queries are rejected."""
        db = ReviewDB(db_path=temp_db)

        with pytest.raises(ValueError, match="Only SELECT/CTE queries are allowed"):
            db.query("UPDATE comments SET status = 'foo'")

    def test_query_rejects_insert(self, temp_db: Path) -> None:
        """Test that INSERT queries are rejected."""
        db = ReviewDB(db_path=temp_db)

        with pytest.raises(ValueError, match="Only SELECT/CTE queries are allowed"):
            db.query("INSERT INTO comments (source) VALUES ('test')")

    def test_query_rejects_drop(self, temp_db: Path) -> None:
        """Test that DROP queries are rejected."""
        db = ReviewDB(db_path=temp_db)

        with pytest.raises(ValueError, match="Only SELECT/CTE queries are allowed"):
            db.query("DROP TABLE comments")

    def test_query_case_insensitive_select(self, temp_db: Path) -> None:
        """Test that SELECT detection is case-insensitive."""
        db = ReviewDB(db_path=temp_db)

        # Lowercase select should work
        result = db.query("select count(*) as count from comments")
        assert len(result) == 1
        assert result[0]["count"] == 4

    def test_query_nonexistent_db(self, tmp_path: Path) -> None:
        """Test query when database doesn't exist."""
        db = ReviewDB(db_path=tmp_path / "nonexistent.db")
        result = db.query("SELECT * FROM comments")

        assert result == []

    def test_query_rejects_multi_statement(self, temp_db: Path) -> None:
        """Test that multi-statement queries are rejected."""
        db = ReviewDB(db_path=temp_db)

        with pytest.raises(ValueError, match="Multiple SQL statements"):
            db.query("SELECT * FROM comments; DELETE FROM comments")

    def test_query_rejects_dangerous_keywords(self, temp_db: Path) -> None:
        """Test that dangerous keywords are rejected even in SELECT context."""
        db = ReviewDB(db_path=temp_db)

        # Test various dangerous keywords
        dangerous_queries = [
            "SELECT * FROM comments UNION ALL SELECT * FROM sqlite_master; DROP TABLE comments",
            "SELECT * FROM comments WHERE INSERT = 1",
            "SELECT * FROM comments WHERE 1=1 DELETE",
            "SELECT ATTACH DATABASE 'x' AS y FROM comments",
        ]

        for query in dangerous_queries:
            with pytest.raises(ValueError):
                db.query(query)


class TestReviewDBCLI:
    """Tests for CLI interface."""

    def test_cli_stats_by_source(self, temp_db: Path) -> None:
        """Test CLI stats command with --by-source."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "stats",
                "--by-source",
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 1
        # Verify structure
        assert all("source" in item for item in data)
        assert all("total" in item for item in data)
        assert all("addressed_rate" in item for item in data)

    def test_cli_stats_by_reviewer(self, temp_db: Path) -> None:
        """Test CLI stats command with --by-reviewer."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "stats",
                "--by-reviewer",
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) >= 1
        # Verify structure
        assert all("author" in item for item in data)
        assert all("total" in item for item in data)

    def test_cli_query(self, temp_db: Path) -> None:
        """Test CLI query command."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "query",
                "SELECT COUNT(*) as count FROM comments",
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data[0]["count"] == 4

    def test_cli_query_rejects_non_select(self, temp_db: Path) -> None:
        """Test that CLI rejects non-SELECT queries."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "query",
                "DELETE FROM comments",
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "Only SELECT/CTE queries are allowed" in result.stderr

    def test_cli_query_rejects_multi_statement(self, temp_db: Path) -> None:
        """Test that CLI rejects multi-statement queries."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "query",
                "SELECT * FROM comments; DELETE FROM comments",
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "Multiple SQL statements" in result.stderr

    def test_cli_dismissed(self, temp_db: Path) -> None:
        """Test CLI dismissed command."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "dismissed",
                "--owner",
                "test-org",
                "--repo",
                "test-repo",
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2  # not_addressed + skipped
        statuses = {item["status"] for item in data}
        assert statuses == {"not_addressed", "skipped"}

    def test_cli_patterns(self, temp_db: Path) -> None:
        """Test CLI patterns command."""
        # Add duplicate comments to create a pattern
        conn = sqlite3.connect(str(temp_db))
        review_id = conn.execute(
            "SELECT id FROM reviews WHERE owner = ? AND repo = ?",
            ("test-org", "test-repo"),
        ).fetchone()[0]

        for i in range(3):
            conn.execute(
                """INSERT INTO comments
                   (review_id, source, path, line, body, status, reply, author)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    review_id,
                    "qodo",
                    "src/pattern.py",
                    10 + i,
                    "Add input validation for this parameter",
                    "not_addressed",
                    "Too generic",
                    "qodo-code-review",
                ),
            )
        conn.commit()
        conn.close()

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "patterns",
                "--min",
                "2",
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        # Should find the pattern we created
        pattern_paths = {item["path"] for item in data}
        assert "src/pattern.py" in pattern_paths

    def test_cli_find_similar(self, temp_db: Path) -> None:
        """Test CLI find-similar command."""
        input_json = json.dumps({"path": "path/to/file.py", "body": "Add skip option"})

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "find-similar",
                "--owner",
                "test-org",
                "--repo",
                "test-repo",
                "--json",
            ],
            capture_output=True,
            text=True,
            input=input_json,
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Should find a similar comment
        assert data is not None
        assert "skip" in data["body"].lower()

    def test_cli_find_similar_no_match(self, temp_db: Path) -> None:
        """Test CLI find-similar command when no match exists."""
        input_json = json.dumps({"path": "nonexistent/path.py", "body": "Unrelated comment"})

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "find-similar",
                "--owner",
                "test-org",
                "--repo",
                "test-repo",
                "--json",
            ],
            capture_output=True,
            text=True,
            input=input_json,
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data is None

    def test_cli_find_similar_invalid_json(self, temp_db: Path) -> None:
        """Test CLI find-similar command with invalid JSON input."""
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "review_db.py"),
                "--db-path",
                str(temp_db),
                "find-similar",
                "--owner",
                "test-org",
                "--repo",
                "test-repo",
                "--json",
            ],
            capture_output=True,
            text=True,
            input="not valid json",
        )

        assert result.returncode != 0
        assert "JSON" in result.stderr
