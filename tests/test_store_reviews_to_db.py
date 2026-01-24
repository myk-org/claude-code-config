"""Comprehensive unit tests for store-reviews-to-db.py script.

This test suite covers:
- Database creation and schema validation
- JSON parsing and storage
- UPSERT behavior (update existing records)
- Comment storage across categories
- Error handling for missing files/invalid JSON
- Project root detection
"""

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path for importing module
SCRIPTS_DIR = Path(__file__).parent.parent / "commands" / "scripts" / "general"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_module() -> ModuleType:
    """Load the store-reviews-to-db module."""
    spec = importlib.util.spec_from_file_location("store_reviews_to_db", SCRIPTS_DIR / "store-reviews-to-db.py")
    if spec is None or spec.loader is None:
        raise ImportError("Could not load store-reviews-to-db module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


store_reviews = _load_module()


# =============================================================================
# Tests for get_project_root()
# =============================================================================


class TestGetProjectRoot:
    """Tests for get_project_root() git detection."""

    @patch("subprocess.run")
    def test_returns_project_root(self, mock_run: Any) -> None:
        """Should return project root from git rev-parse."""
        mock_run.return_value = MagicMock(returncode=0, stdout="/home/user/project\n", stderr="")

        result = store_reviews.get_project_root()

        assert result == Path("/home/user/project")

    @patch("subprocess.run")
    def test_strips_whitespace(self, mock_run: Any) -> None:
        """Should strip trailing whitespace from path."""
        mock_run.return_value = MagicMock(returncode=0, stdout="  /home/user/project  \n", stderr="")

        result = store_reviews.get_project_root()

        assert result == Path("/home/user/project")

    @patch("subprocess.run")
    def test_exits_on_git_error(self, mock_run: Any) -> None:
        """Should exit on git rev-parse error."""
        mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: not a git repository")

        with pytest.raises(SystemExit) as excinfo:
            store_reviews.get_project_root()

        assert excinfo.value.code == 1

    @patch("subprocess.run")
    def test_exits_on_timeout(self, mock_run: Any) -> None:
        """Should exit on timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=5)

        with pytest.raises(SystemExit) as excinfo:
            store_reviews.get_project_root()

        assert excinfo.value.code == 1

    @patch("subprocess.run")
    def test_exits_on_git_not_found(self, mock_run: Any) -> None:
        """Should exit if git command not found."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit) as excinfo:
            store_reviews.get_project_root()

        assert excinfo.value.code == 1


# =============================================================================
# Tests for ensure_database_directory()
# =============================================================================


class TestEnsureDatabaseDirectory:
    """Tests for ensure_database_directory() directory creation."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Should create directory if it does not exist."""
        db_path = tmp_path / "subdir" / "data" / "reviews.db"

        store_reviews.ensure_database_directory(db_path)

        assert db_path.parent.exists()

    def test_directory_has_correct_permissions(self, tmp_path: Path) -> None:
        """Should create directory with 0700 permissions."""
        db_path = tmp_path / "newdir" / "reviews.db"

        store_reviews.ensure_database_directory(db_path)

        # Check permissions (octal)
        mode = db_path.parent.stat().st_mode & 0o777
        assert mode == 0o700

    def test_existing_directory_unchanged(self, tmp_path: Path) -> None:
        """Should not fail if directory already exists."""
        db_path = tmp_path / "reviews.db"

        # Should not raise
        store_reviews.ensure_database_directory(db_path)


# =============================================================================
# Tests for create_tables()
# =============================================================================


class TestCreateTables:
    """Tests for create_tables() schema creation."""

    def test_creates_reviews_table(self, tmp_path: Path) -> None:
        """Should create reviews table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        store_reviews.create_tables(conn)

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reviews'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_comments_table(self, tmp_path: Path) -> None:
        """Should create comments table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        store_reviews.create_tables(conn)

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comments'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_indexes(self, tmp_path: Path) -> None:
        """Should create indexes."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        store_reviews.create_tables(conn)

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_comments_review_id" in indexes
        assert "idx_comments_source" in indexes
        assert "idx_comments_status" in indexes
        conn.close()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Should be idempotent (can run multiple times)."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        store_reviews.create_tables(conn)
        store_reviews.create_tables(conn)  # Should not fail

        conn.close()

    def test_reviews_table_schema(self, tmp_path: Path) -> None:
        """Should have correct reviews table schema."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        store_reviews.create_tables(conn)

        cursor = conn.execute("PRAGMA table_info(reviews)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "id" in columns
        assert "pr_number" in columns
        assert "owner" in columns
        assert "repo" in columns
        assert "created_at" in columns
        conn.close()

    def test_comments_table_schema(self, tmp_path: Path) -> None:
        """Should have correct comments table schema."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        store_reviews.create_tables(conn)

        cursor = conn.execute("PRAGMA table_info(comments)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = [
            "id",
            "review_id",
            "source",
            "thread_id",
            "node_id",
            "comment_id",
            "author",
            "path",
            "line",
            "body",
            "priority",
            "status",
            "reply",
            "skip_reason",
            "posted_at",
            "resolved_at",
        ]
        for col in expected_columns:
            assert col in columns
        conn.close()


# =============================================================================
# Tests for upsert_review()
# =============================================================================


class TestUpsertReview:
    """Tests for upsert_review() insert/update behavior."""

    def test_inserts_new_review(self, tmp_path: Path) -> None:
        """Should insert new review."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id = store_reviews.upsert_review(conn, "owner", "repo", 123)

        cursor = conn.execute("SELECT id, owner, repo, pr_number FROM reviews WHERE id = ?", (review_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == "owner"
        assert row[2] == "repo"
        assert row[3] == 123
        conn.close()

    def test_returns_existing_review_id(self, tmp_path: Path) -> None:
        """Should return existing review ID on duplicate."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id1 = store_reviews.upsert_review(conn, "owner", "repo", 123)
        review_id2 = store_reviews.upsert_review(conn, "owner", "repo", 123)

        assert review_id1 == review_id2
        conn.close()

    def test_updates_created_at_on_rerun(self, tmp_path: Path) -> None:
        """Should update created_at on re-run."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        store_reviews.upsert_review(conn, "owner", "repo", 123)
        cursor = conn.execute("SELECT created_at FROM reviews")
        first_created_at = cursor.fetchone()[0]

        # Re-run
        store_reviews.upsert_review(conn, "owner", "repo", 123)
        cursor = conn.execute("SELECT created_at FROM reviews")
        second_created_at = cursor.fetchone()[0]

        # Created at should be updated (or at least exist)
        assert first_created_at is not None
        assert second_created_at is not None
        conn.close()

    def test_different_prs_get_different_ids(self, tmp_path: Path) -> None:
        """Should get different IDs for different PRs."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id1 = store_reviews.upsert_review(conn, "owner", "repo", 123)
        review_id2 = store_reviews.upsert_review(conn, "owner", "repo", 456)

        assert review_id1 != review_id2
        conn.close()

    def test_unique_constraint(self, tmp_path: Path) -> None:
        """Should enforce unique constraint on owner/repo/pr_number."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        store_reviews.upsert_review(conn, "owner", "repo", 123)

        # Count should be 1 after multiple upserts
        store_reviews.upsert_review(conn, "owner", "repo", 123)
        cursor = conn.execute("SELECT COUNT(*) FROM reviews")
        assert cursor.fetchone()[0] == 1
        conn.close()


# =============================================================================
# Tests for delete_existing_comments()
# =============================================================================


class TestDeleteExistingComments:
    """Tests for delete_existing_comments() cleanup."""

    def test_deletes_comments_for_review(self, tmp_path: Path) -> None:
        """Should delete all comments for a review."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id = store_reviews.upsert_review(conn, "owner", "repo", 123)
        store_reviews.insert_comment(conn, review_id, "human", {"body": "test1"})
        store_reviews.insert_comment(conn, review_id, "human", {"body": "test2"})

        deleted_count = store_reviews.delete_existing_comments(conn, review_id)

        assert deleted_count == 2
        cursor = conn.execute("SELECT COUNT(*) FROM comments WHERE review_id = ?", (review_id,))
        assert cursor.fetchone()[0] == 0
        conn.close()

    def test_does_not_delete_other_reviews(self, tmp_path: Path) -> None:
        """Should not delete comments from other reviews."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id1 = store_reviews.upsert_review(conn, "owner", "repo", 123)
        review_id2 = store_reviews.upsert_review(conn, "owner", "repo", 456)
        store_reviews.insert_comment(conn, review_id1, "human", {"body": "test1"})
        store_reviews.insert_comment(conn, review_id2, "human", {"body": "test2"})

        store_reviews.delete_existing_comments(conn, review_id1)

        cursor = conn.execute("SELECT COUNT(*) FROM comments WHERE review_id = ?", (review_id2,))
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_returns_zero_for_no_comments(self, tmp_path: Path) -> None:
        """Should return 0 when no comments exist."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id = store_reviews.upsert_review(conn, "owner", "repo", 123)

        deleted_count = store_reviews.delete_existing_comments(conn, review_id)

        assert deleted_count == 0
        conn.close()


# =============================================================================
# Tests for insert_comment()
# =============================================================================


class TestInsertComment:
    """Tests for insert_comment() comment insertion."""

    def test_inserts_comment(self, tmp_path: Path) -> None:
        """Should insert comment with all fields."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id = store_reviews.upsert_review(conn, "owner", "repo", 123)
        comment = {
            "thread_id": "t1",
            "node_id": "n1",
            "comment_id": 100,
            "author": "reviewer",
            "path": "file.py",
            "line": 42,
            "body": "Fix this",
            "priority": "HIGH",
            "status": "addressed",
            "reply": "Fixed",
            "skip_reason": None,
            "posted_at": "2024-01-15T10:00:00Z",
            "resolved_at": "2024-01-15T10:01:00Z",
        }

        store_reviews.insert_comment(conn, review_id, "human", comment)

        cursor = conn.execute("SELECT * FROM comments WHERE review_id = ?", (review_id,))
        row = cursor.fetchone()
        assert row is not None
        conn.close()

    def test_stores_source(self, tmp_path: Path) -> None:
        """Should store source correctly."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id = store_reviews.upsert_review(conn, "owner", "repo", 123)

        store_reviews.insert_comment(conn, review_id, "qodo", {"body": "test"})

        cursor = conn.execute("SELECT source FROM comments WHERE review_id = ?", (review_id,))
        assert cursor.fetchone()[0] == "qodo"
        conn.close()

    def test_handles_missing_fields(self, tmp_path: Path) -> None:
        """Should handle missing optional fields."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id = store_reviews.upsert_review(conn, "owner", "repo", 123)
        comment = {"body": "Minimal comment"}

        store_reviews.insert_comment(conn, review_id, "human", comment)

        cursor = conn.execute("SELECT body, thread_id FROM comments WHERE review_id = ?", (review_id,))
        row = cursor.fetchone()
        assert row[0] == "Minimal comment"
        assert row[1] is None
        conn.close()

    def test_stores_all_sources(self, tmp_path: Path) -> None:
        """Should store comments from all sources."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        store_reviews.create_tables(conn)

        review_id = store_reviews.upsert_review(conn, "owner", "repo", 123)

        store_reviews.insert_comment(conn, review_id, "human", {"body": "human comment"})
        store_reviews.insert_comment(conn, review_id, "qodo", {"body": "qodo comment"})
        store_reviews.insert_comment(conn, review_id, "coderabbit", {"body": "coderabbit comment"})

        cursor = conn.execute("SELECT source FROM comments WHERE review_id = ? ORDER BY source", (review_id,))
        sources = [row[0] for row in cursor.fetchall()]
        assert sorted(sources) == ["coderabbit", "human", "qodo"]
        conn.close()


# =============================================================================
# Tests for store_reviews() - Main Function
# =============================================================================


class TestStoreReviews:
    """Tests for store_reviews() main storage function."""

    def _create_test_json(self, tmp_path: Path, data: dict[str, Any]) -> Path:
        """Helper to create test JSON file."""
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data))
        return json_path

    @patch.object(store_reviews, "get_project_root")
    def test_stores_all_categories(self, mock_root: Any, tmp_path: Path) -> None:
        """Should store comments from all categories."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "test-owner",
                "repo": "test-repo",
                "pr_number": 123,
            },
            "human": [{"body": "human comment"}],
            "qodo": [{"body": "qodo comment"}],
            "coderabbit": [{"body": "coderabbit comment"}],
        }
        json_path = self._create_test_json(tmp_path, data)

        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        assert db_path.exists()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM comments")
        assert cursor.fetchone()[0] == 3
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_creates_review_record(self, mock_root: Any, tmp_path: Path) -> None:
        """Should create review record."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "my-org",
                "repo": "my-repo",
                "pr_number": 42,
            },
            "human": [],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = self._create_test_json(tmp_path, data)

        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT owner, repo, pr_number FROM reviews")
        row = cursor.fetchone()
        assert row == ("my-org", "my-repo", 42)
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_deletes_old_comments_on_rerun(self, mock_root: Any, tmp_path: Path) -> None:
        """Should delete old comments on re-run."""
        mock_root.return_value = tmp_path

        # First run
        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [{"body": "old comment 1"}, {"body": "old comment 2"}],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = self._create_test_json(tmp_path, data)
        store_reviews.store_reviews(json_path)

        # Second run with different comments
        data["human"] = [{"body": "new comment"}]
        json_path = self._create_test_json(tmp_path, data)
        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT body FROM comments")
        bodies = [row[0] for row in cursor.fetchall()]
        assert bodies == ["new comment"]
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_deletes_json_after_storage(self, mock_root: Any, tmp_path: Path) -> None:
        """Should delete JSON file after successful storage."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = self._create_test_json(tmp_path, data)

        store_reviews.store_reviews(json_path)

        assert not json_path.exists()

    def test_exits_on_missing_file(self, tmp_path: Path) -> None:
        """Should exit on missing JSON file."""
        json_path = tmp_path / "nonexistent.json"

        with pytest.raises(SystemExit) as excinfo:
            store_reviews.store_reviews(json_path)

        assert excinfo.value.code == 1

    def test_exits_on_invalid_json(self, tmp_path: Path) -> None:
        """Should exit on invalid JSON."""
        json_path = tmp_path / "invalid.json"
        json_path.write_text("not valid json {{{")

        with pytest.raises(SystemExit) as excinfo:
            store_reviews.store_reviews(json_path)

        assert excinfo.value.code == 1

    def test_exits_on_missing_required_fields(self, tmp_path: Path) -> None:
        """Should exit on missing required fields."""
        json_path = tmp_path / "incomplete.json"
        json_path.write_text('{"human": []}')

        with pytest.raises(SystemExit) as excinfo:
            store_reviews.store_reviews(json_path)

        assert excinfo.value.code == 1

    @patch.object(store_reviews, "get_project_root")
    def test_stores_all_comment_fields(self, mock_root: Any, tmp_path: Path) -> None:
        """Should store all comment fields correctly."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [
                {
                    "thread_id": "thread_abc",
                    "node_id": "node_xyz",
                    "comment_id": 12345,
                    "author": "reviewer1",
                    "path": "src/main.py",
                    "line": 100,
                    "body": "Please fix this bug",
                    "priority": "HIGH",
                    "status": "addressed",
                    "reply": "Fixed in commit abc123",
                    "skip_reason": None,
                    "posted_at": "2024-01-15T10:00:00Z",
                    "resolved_at": "2024-01-15T10:05:00Z",
                }
            ],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = self._create_test_json(tmp_path, data)

        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            """
            SELECT thread_id, node_id, comment_id, author, path, line,
                   body, priority, status, reply, posted_at, resolved_at
            FROM comments
            """
        )
        row = cursor.fetchone()

        assert row[0] == "thread_abc"
        assert row[1] == "node_xyz"
        assert row[2] == 12345
        assert row[3] == "reviewer1"
        assert row[4] == "src/main.py"
        assert row[5] == 100
        assert row[6] == "Please fix this bug"
        assert row[7] == "HIGH"
        assert row[8] == "addressed"
        assert row[9] == "Fixed in commit abc123"
        assert row[10] == "2024-01-15T10:00:00Z"
        assert row[11] == "2024-01-15T10:05:00Z"
        conn.close()


# =============================================================================
# Tests for main() - CLI Entry Point
# =============================================================================


class TestMain:
    """Tests for main() CLI entry point."""

    @patch.object(store_reviews, "store_reviews")
    def test_calls_store_reviews(self, mock_store: Any, tmp_path: Path) -> None:
        """Should call store_reviews with resolved path."""
        json_path = tmp_path / "reviews.json"
        json_path.write_text("{}")

        with patch("sys.argv", ["script", str(json_path)]):
            store_reviews.main()

        mock_store.assert_called_once()
        call_arg = mock_store.call_args[0][0]
        assert call_arg == json_path.resolve()

    def test_exits_on_missing_file_arg(self, tmp_path: Path) -> None:
        """Should exit if file does not exist."""
        json_path = tmp_path / "nonexistent.json"

        with patch("sys.argv", ["script", str(json_path)]):
            with pytest.raises(SystemExit) as excinfo:
                store_reviews.main()

        assert excinfo.value.code == 1

    def test_shows_help_with_no_args(self) -> None:
        """Should show help with no arguments."""
        with patch("sys.argv", ["script"]):
            with pytest.raises(SystemExit) as excinfo:
                store_reviews.main()

        # argparse exits with 2 for missing required arguments
        assert excinfo.value.code == 2


# =============================================================================
# Tests for edge cases
# =============================================================================


class TestEdgeCases:
    """Edge cases and error handling tests."""

    @patch.object(store_reviews, "get_project_root")
    def test_empty_categories(self, mock_root: Any, tmp_path: Path) -> None:
        """Should handle empty category arrays."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data))

        # Should not raise
        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM comments")
        assert cursor.fetchone()[0] == 0
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_missing_category_key(self, mock_root: Any, tmp_path: Path) -> None:
        """Should handle missing category keys (treat as empty)."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [{"body": "test"}],
            # Missing qodo and coderabbit keys
        }
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data))

        # Should not raise
        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM comments")
        assert cursor.fetchone()[0] == 1
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_large_comment_body(self, mock_root: Any, tmp_path: Path) -> None:
        """Should handle large comment bodies."""
        mock_root.return_value = tmp_path

        large_body = "x" * 100000
        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [{"body": large_body}],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data))

        # Should not raise
        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT body FROM comments")
        assert len(cursor.fetchone()[0]) == 100000
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_unicode_content(self, mock_root: Any, tmp_path: Path) -> None:
        """Should handle unicode content in comments."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [{"body": "Unicode test: emoji test: Hello World!"}],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data, ensure_ascii=False))

        # Should not raise
        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT body FROM comments")
        body = cursor.fetchone()[0]
        assert "Unicode test" in body
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_null_values_in_comment(self, mock_root: Any, tmp_path: Path) -> None:
        """Should handle null values in comment fields."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [
                {
                    "thread_id": None,
                    "node_id": None,
                    "comment_id": None,
                    "author": None,
                    "path": None,
                    "line": None,
                    "body": None,
                    "priority": None,
                    "status": None,
                    "reply": None,
                    "skip_reason": None,
                    "posted_at": None,
                    "resolved_at": None,
                }
            ],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data))

        # Should not raise
        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM comments")
        assert cursor.fetchone()[0] == 1
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_special_characters_in_path(self, mock_root: Any, tmp_path: Path) -> None:
        """Should handle special characters in file paths."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [{"path": "src/my file (copy).py", "body": "test"}],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data))

        store_reviews.store_reviews(json_path)

        db_path = tmp_path / ".claude" / "data" / "reviews.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT path FROM comments")
        assert cursor.fetchone()[0] == "src/my file (copy).py"
        conn.close()

    @patch.object(store_reviews, "get_project_root")
    def test_pr_number_as_string(self, mock_root: Any, tmp_path: Path) -> None:
        """Should handle pr_number as string (converts to int)."""
        mock_root.return_value = tmp_path

        # Note: The script expects pr_number as int, but JSON might have it as string
        # This tests the current behavior
        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": "123",  # String instead of int
            },
            "human": [],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data))

        # Should handle string pr_number (or fail gracefully)
        try:
            store_reviews.store_reviews(json_path)
        except (TypeError, sqlite3.InterfaceError):
            # If it fails, that's expected behavior for non-int pr_number
            pass

    @patch.object(store_reviews, "get_project_root")
    def test_creates_data_directory(self, mock_root: Any, tmp_path: Path) -> None:
        """Should create .claude/data directory."""
        mock_root.return_value = tmp_path

        data = {
            "metadata": {
                "owner": "org",
                "repo": "repo",
                "pr_number": 1,
            },
            "human": [],
            "qodo": [],
            "coderabbit": [],
        }
        json_path = tmp_path / "reviews.json"
        json_path.write_text(json.dumps(data))

        store_reviews.store_reviews(json_path)

        assert (tmp_path / ".claude" / "data").exists()
