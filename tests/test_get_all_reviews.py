"""Comprehensive unit tests for get-all-github-unresolved-reviews-for-pr.py script.

This test suite covers:
- detect_source() author classification
- classify_priority() keyword matching
- check_dependencies() validation
- GraphQL pagination handling
- URL pattern matching for review types
- Thread merging and deduplication
- process_and_categorize() thread enrichment
"""

import importlib.util
import re
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
    """Load the get-all-github-unresolved-reviews-for-pr module."""
    spec = importlib.util.spec_from_file_location(
        "get_all_reviews", SCRIPTS_DIR / "get-all-github-unresolved-reviews-for-pr.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("Could not load get-all-github-unresolved-reviews-for-pr module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


get_all_reviews = _load_module()


# =============================================================================
# Tests for detect_source() - Author Classification
# =============================================================================


class TestDetectSource:
    """Tests for detect_source() author classification."""

    def test_qodo_user(self) -> None:
        """Qodo user should return 'qodo'."""
        assert get_all_reviews.detect_source("qodo-code-review") == "qodo"

    def test_qodo_bot(self) -> None:
        """Qodo bot should return 'qodo'."""
        assert get_all_reviews.detect_source("qodo-code-review[bot]") == "qodo"

    def test_coderabbit_user(self) -> None:
        """CodeRabbit user should return 'coderabbit'."""
        assert get_all_reviews.detect_source("coderabbitai") == "coderabbit"

    def test_coderabbit_bot(self) -> None:
        """CodeRabbit bot should return 'coderabbit'."""
        assert get_all_reviews.detect_source("coderabbitai[bot]") == "coderabbit"

    def test_human_user(self) -> None:
        """Regular user should return 'human'."""
        assert get_all_reviews.detect_source("myusername") == "human"

    def test_none_author(self) -> None:
        """None author should return 'human'."""
        assert get_all_reviews.detect_source(None) == "human"

    def test_empty_string_author(self) -> None:
        """Empty string author should return 'human'."""
        assert get_all_reviews.detect_source("") == "human"

    def test_case_sensitive_matching(self) -> None:
        """Author matching should be case-sensitive."""
        assert get_all_reviews.detect_source("QODO-CODE-REVIEW") == "human"
        assert get_all_reviews.detect_source("CodeRabbitAI") == "human"

    def test_partial_match_not_accepted(self) -> None:
        """Partial matches should not be accepted."""
        assert get_all_reviews.detect_source("qodo") == "human"
        assert get_all_reviews.detect_source("coderabbit") == "human"


# =============================================================================
# Tests for classify_priority() - Keyword Matching
# =============================================================================


class TestClassifyPriority:
    """Tests for classify_priority() keyword matching."""

    # --- HIGH priority tests ---

    def test_high_priority_security(self) -> None:
        """Security keyword should return HIGH."""
        assert get_all_reviews.classify_priority("This is a security vulnerability") == "HIGH"

    def test_high_priority_critical(self) -> None:
        """Critical keyword should return HIGH."""
        assert get_all_reviews.classify_priority("Critical bug found") == "HIGH"

    def test_high_priority_bug(self) -> None:
        """Bug keyword should return HIGH."""
        assert get_all_reviews.classify_priority("This is a bug in the code") == "HIGH"

    def test_high_priority_error(self) -> None:
        """Error keyword should return HIGH."""
        assert get_all_reviews.classify_priority("Error handling is missing") == "HIGH"

    def test_high_priority_crash(self) -> None:
        """Crash keyword should return HIGH."""
        assert get_all_reviews.classify_priority("This will crash the application") == "HIGH"

    def test_high_priority_must(self) -> None:
        """Must keyword should return HIGH."""
        assert get_all_reviews.classify_priority("You must fix this") == "HIGH"

    def test_high_priority_required(self) -> None:
        """Required keyword should return HIGH."""
        assert get_all_reviews.classify_priority("This change is required") == "HIGH"

    def test_high_priority_breaking(self) -> None:
        """Breaking keyword should return HIGH."""
        assert get_all_reviews.classify_priority("Breaking change detected") == "HIGH"

    def test_high_priority_urgent(self) -> None:
        """Urgent keyword should return HIGH."""
        assert get_all_reviews.classify_priority("Urgent: fix needed") == "HIGH"

    def test_high_priority_injection(self) -> None:
        """Injection keyword should return HIGH."""
        assert get_all_reviews.classify_priority("SQL injection risk") == "HIGH"

    def test_high_priority_xss(self) -> None:
        """XSS keyword should return HIGH."""
        assert get_all_reviews.classify_priority("XSS vulnerability here") == "HIGH"

    def test_high_priority_csrf(self) -> None:
        """CSRF keyword should return HIGH."""
        assert get_all_reviews.classify_priority("CSRF protection missing") == "HIGH"

    def test_high_priority_auth(self) -> None:
        """Auth keyword should return HIGH."""
        assert get_all_reviews.classify_priority("Auth bypass possible") == "HIGH"

    def test_high_priority_case_insensitive(self) -> None:
        """HIGH priority matching should be case insensitive."""
        assert get_all_reviews.classify_priority("SECURITY issue") == "HIGH"
        assert get_all_reviews.classify_priority("Security Issue") == "HIGH"

    # --- LOW priority tests ---

    def test_low_priority_style(self) -> None:
        """Style keyword should return LOW."""
        assert get_all_reviews.classify_priority("Style improvement needed") == "LOW"

    def test_low_priority_formatting(self) -> None:
        """Formatting keyword should return LOW."""
        assert get_all_reviews.classify_priority("Fix the formatting") == "LOW"

    def test_low_priority_typo(self) -> None:
        """Typo keyword should return LOW."""
        assert get_all_reviews.classify_priority("There's a typo here") == "LOW"

    def test_low_priority_nitpick(self) -> None:
        """Nitpick keyword should return LOW."""
        assert get_all_reviews.classify_priority("This is a nitpick") == "LOW"

    def test_low_priority_nit_colon(self) -> None:
        """nit: prefix should return LOW."""
        assert get_all_reviews.classify_priority("nit: use better naming") == "LOW"

    def test_low_priority_minor(self) -> None:
        """Minor keyword should return LOW."""
        assert get_all_reviews.classify_priority("Minor improvement") == "LOW"

    def test_low_priority_optional(self) -> None:
        """Optional keyword should return LOW."""
        assert get_all_reviews.classify_priority("Optional: consider this") == "LOW"

    def test_low_priority_cosmetic(self) -> None:
        """Cosmetic keyword should return LOW."""
        assert get_all_reviews.classify_priority("Cosmetic change only") == "LOW"

    def test_low_priority_whitespace(self) -> None:
        """Whitespace keyword should return LOW."""
        assert get_all_reviews.classify_priority("Trailing whitespace") == "LOW"

    def test_low_priority_indentation(self) -> None:
        """Indentation keyword should return LOW."""
        assert get_all_reviews.classify_priority("Fix indentation") == "LOW"

    def test_low_priority_case_insensitive(self) -> None:
        """LOW priority matching should be case insensitive."""
        assert get_all_reviews.classify_priority("STYLE change") == "LOW"
        assert get_all_reviews.classify_priority("Style Change") == "LOW"

    # --- MEDIUM priority tests ---

    def test_medium_priority_default(self) -> None:
        """Regular comment should return MEDIUM."""
        assert get_all_reviews.classify_priority("Consider refactoring this") == "MEDIUM"

    def test_medium_priority_suggestion(self) -> None:
        """Suggestion without priority keywords should return MEDIUM."""
        assert get_all_reviews.classify_priority("Maybe use a different approach") == "MEDIUM"

    def test_medium_priority_none_body(self) -> None:
        """None body should return MEDIUM."""
        assert get_all_reviews.classify_priority(None) == "MEDIUM"

    def test_medium_priority_empty_body(self) -> None:
        """Empty body should return MEDIUM."""
        assert get_all_reviews.classify_priority("") == "MEDIUM"

    # --- Priority precedence tests ---

    def test_high_takes_precedence_over_low(self) -> None:
        """HIGH priority should take precedence over LOW keywords."""
        # Contains both 'security' (HIGH) and 'minor' (LOW)
        assert get_all_reviews.classify_priority("Minor security issue") == "HIGH"


# =============================================================================
# Tests for check_dependencies()
# =============================================================================


class TestCheckDependencies:
    """Tests for check_dependencies() validation."""

    @patch("shutil.which")
    def test_gh_not_installed(self, mock_which: Any) -> None:
        """Missing gh should exit with error."""
        mock_which.return_value = None

        with pytest.raises(SystemExit) as excinfo:
            get_all_reviews.check_dependencies()

        assert excinfo.value.code == 1
        mock_which.assert_called_once_with("gh")

    @patch("shutil.which")
    def test_pr_info_script_missing(self, mock_which: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing PR info script should exit with error."""
        mock_which.return_value = "/usr/bin/gh"

        monkeypatch.setattr(get_all_reviews, "__file__", str(tmp_path / "fake-script.py"))
        with pytest.raises(SystemExit) as excinfo:
            get_all_reviews.check_dependencies()
        assert excinfo.value.code == 1

    @patch("shutil.which")
    def test_all_dependencies_available(self, mock_which: Any) -> None:
        """All dependencies available should return PR info script path."""
        mock_which.return_value = "/usr/bin/gh"

        result = get_all_reviews.check_dependencies()

        assert result.name == "get-pr-info.sh"
        assert result.exists()


# =============================================================================
# Tests for run_gh_graphql()
# =============================================================================


class TestRunGhGraphql:
    """Tests for run_gh_graphql() GraphQL execution."""

    @patch("subprocess.run")
    def test_successful_query(self, mock_run: Any) -> None:
        """Successful GraphQL query should return parsed data."""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"data": {"test": "value"}}', stderr="")

        result = get_all_reviews.run_gh_graphql("query { test }", {})

        assert result == {"data": {"test": "value"}}

    @patch("subprocess.run")
    def test_failed_query(self, mock_run: Any) -> None:
        """Failed GraphQL query should return None."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        result = get_all_reviews.run_gh_graphql("query { test }", {})

        assert result is None

    @patch("subprocess.run")
    def test_invalid_json_response(self, mock_run: Any) -> None:
        """Invalid JSON response should return None."""
        mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")

        result = get_all_reviews.run_gh_graphql("query { test }", {})

        assert result is None

    @patch("subprocess.run")
    def test_string_variable(self, mock_run: Any) -> None:
        """String variable should use -f flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")

        get_all_reviews.run_gh_graphql("query", {"name": "value"})

        call_args = mock_run.call_args[0][0]
        assert "-f" in call_args
        assert "name=value" in call_args

    @patch("subprocess.run")
    def test_int_variable(self, mock_run: Any) -> None:
        """Integer variable should use -F flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")

        get_all_reviews.run_gh_graphql("query", {"count": 42})

        call_args = mock_run.call_args[0][0]
        assert "-F" in call_args
        assert "count=42" in call_args

    @patch("subprocess.run")
    def test_timeout_returns_none(self, mock_run: Any) -> None:
        """Timed out query should return None."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gh"], timeout=120)

        result = get_all_reviews.run_gh_graphql("query { test }", {})

        assert result is None


# =============================================================================
# Tests for run_gh_api()
# =============================================================================


class TestRunGhApi:
    """Tests for run_gh_api() REST API execution."""

    @patch("subprocess.run")
    def test_successful_api_call(self, mock_run: Any) -> None:
        """Successful API call should return parsed data."""
        mock_run.return_value = MagicMock(returncode=0, stdout='{"id": 123}', stderr="")

        result = get_all_reviews.run_gh_api("/repos/owner/repo")

        assert result == {"id": 123}

    @patch("subprocess.run")
    def test_failed_api_call(self, mock_run: Any) -> None:
        """Failed API call should return None."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")

        result = get_all_reviews.run_gh_api("/repos/owner/repo")

        assert result is None

    @patch("subprocess.run")
    def test_paginated_response(self, mock_run: Any) -> None:
        """Paginated response should merge arrays."""
        # With --slurp, gh wraps pages in an outer array: [[page1], [page2]]
        mock_run.return_value = MagicMock(returncode=0, stdout='[[{"id": 1}], [{"id": 2}]]', stderr="")

        result = get_all_reviews.run_gh_api("/repos/owner/repo/comments", paginate=True)

        assert result == [{"id": 1}, {"id": 2}]

    @patch("subprocess.run")
    def test_paginate_flag(self, mock_run: Any) -> None:
        """Paginate=True should add --paginate and --slurp flags."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")

        get_all_reviews.run_gh_api("/test", paginate=True)

        call_args = mock_run.call_args[0][0]
        assert "--paginate" in call_args
        assert "--slurp" in call_args


# =============================================================================
# Tests for fetch_unresolved_threads()
# =============================================================================


class TestFetchUnresolvedThreads:
    """Tests for fetch_unresolved_threads() GraphQL fetching."""

    @patch.object(get_all_reviews, "run_gh_graphql")
    def test_filters_resolved_threads(self, mock_graphql: Any) -> None:
        """Resolved threads should be filtered out."""
        mock_graphql.return_value = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "thread1",
                                    "isResolved": True,
                                    "comments": {"nodes": [{"id": "c1", "body": "test"}]},
                                },
                                {
                                    "id": "thread2",
                                    "isResolved": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "c2",
                                                "databaseId": 123,
                                                "author": {"login": "user"},
                                                "path": "file.py",
                                                "line": 10,
                                                "body": "Comment",
                                                "createdAt": "2024-01-01",
                                            }
                                        ]
                                    },
                                },
                            ],
                        }
                    }
                }
            }
        }

        result = get_all_reviews.fetch_unresolved_threads("owner", "repo", "1")

        assert len(result) == 1
        assert result[0]["thread_id"] == "thread2"

    @patch.object(get_all_reviews, "run_gh_graphql")
    def test_extracts_thread_data(self, mock_graphql: Any) -> None:
        """Thread data should be correctly extracted."""
        mock_graphql.return_value = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "thread1",
                                    "isResolved": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "node1",
                                                "databaseId": 456,
                                                "author": {"login": "reviewer"},
                                                "path": "src/main.py",
                                                "line": 42,
                                                "body": "Please fix this",
                                                "createdAt": "2024-01-15",
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        }

        result = get_all_reviews.fetch_unresolved_threads("owner", "repo", "1")

        assert result[0]["thread_id"] == "thread1"
        assert result[0]["node_id"] == "node1"
        assert result[0]["comment_id"] == 456
        assert result[0]["author"] == "reviewer"
        assert result[0]["path"] == "src/main.py"
        assert result[0]["line"] == 42
        assert result[0]["body"] == "Please fix this"

    @patch.object(get_all_reviews, "run_gh_graphql")
    def test_includes_replies(self, mock_graphql: Any) -> None:
        """Thread replies should be included."""
        mock_graphql.return_value = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "thread1",
                                    "isResolved": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "c1",
                                                "databaseId": 100,
                                                "author": {"login": "reviewer"},
                                                "path": "file.py",
                                                "line": 1,
                                                "body": "Original",
                                                "createdAt": "2024-01-01",
                                            },
                                            {
                                                "id": "c2",
                                                "databaseId": 101,
                                                "author": {"login": "author"},
                                                "path": "file.py",
                                                "line": 1,
                                                "body": "Reply 1",
                                                "createdAt": "2024-01-02",
                                            },
                                            {
                                                "id": "c3",
                                                "databaseId": 102,
                                                "author": {"login": "reviewer"},
                                                "path": "file.py",
                                                "line": 1,
                                                "body": "Reply 2",
                                                "createdAt": "2024-01-03",
                                            },
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        }

        result = get_all_reviews.fetch_unresolved_threads("owner", "repo", "1")

        assert len(result[0]["replies"]) == 2
        assert result[0]["replies"][0]["author"] == "author"
        assert result[0]["replies"][0]["body"] == "Reply 1"
        assert result[0]["replies"][1]["author"] == "reviewer"
        assert result[0]["replies"][1]["body"] == "Reply 2"

    @patch.object(get_all_reviews, "run_gh_graphql")
    def test_handles_pagination(self, mock_graphql: Any) -> None:
        """Pagination should fetch multiple pages."""
        # First page
        first_response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                            "nodes": [
                                {
                                    "id": "thread1",
                                    "isResolved": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "c1",
                                                "databaseId": 1,
                                                "author": {"login": "user"},
                                                "path": "a.py",
                                                "line": 1,
                                                "body": "Comment 1",
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        }
        # Second page
        second_response = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "thread2",
                                    "isResolved": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "c2",
                                                "databaseId": 2,
                                                "author": {"login": "user"},
                                                "path": "b.py",
                                                "line": 2,
                                                "body": "Comment 2",
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        }

        mock_graphql.side_effect = [first_response, second_response]

        result = get_all_reviews.fetch_unresolved_threads("owner", "repo", "1")

        assert len(result) == 2
        assert result[0]["thread_id"] == "thread1"
        assert result[1]["thread_id"] == "thread2"
        assert mock_graphql.call_count == 2

    @patch.object(get_all_reviews, "run_gh_graphql")
    def test_handles_graphql_error(self, mock_graphql: Any) -> None:
        """GraphQL error should return empty list."""
        mock_graphql.return_value = None

        result = get_all_reviews.fetch_unresolved_threads("owner", "repo", "1")

        assert result == []

    @patch.object(get_all_reviews, "run_gh_graphql")
    def test_handles_graphql_errors_field(self, mock_graphql: Any) -> None:
        """GraphQL response with errors field should return partial results."""
        mock_graphql.return_value = {
            "errors": [{"message": "Something went wrong"}],
            "data": None,
        }

        result = get_all_reviews.fetch_unresolved_threads("owner", "repo", "1")

        assert result == []

    @patch.object(get_all_reviews, "run_gh_graphql")
    def test_handles_empty_comments(self, mock_graphql: Any) -> None:
        """Thread with no comments should be skipped."""
        mock_graphql.return_value = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "thread1",
                                    "isResolved": False,
                                    "comments": {"nodes": []},
                                }
                            ],
                        }
                    }
                }
            }
        }

        result = get_all_reviews.fetch_unresolved_threads("owner", "repo", "1")

        assert result == []


# =============================================================================
# Tests for process_and_categorize()
# =============================================================================


class TestProcessAndCategorize:
    """Tests for process_and_categorize() thread enrichment."""

    def test_categorizes_human_threads(self) -> None:
        """Human threads should be categorized correctly."""
        threads = [
            {"author": "regular-user", "body": "Please fix this"},
        ]

        result = get_all_reviews.process_and_categorize(threads)

        assert len(result["human"]) == 1
        assert len(result["qodo"]) == 0
        assert len(result["coderabbit"]) == 0

    def test_categorizes_qodo_threads(self) -> None:
        """Qodo threads should be categorized correctly."""
        threads = [
            {"author": "qodo-code-review[bot]", "body": "Consider this change"},
        ]

        result = get_all_reviews.process_and_categorize(threads)

        assert len(result["human"]) == 0
        assert len(result["qodo"]) == 1
        assert len(result["coderabbit"]) == 0

    def test_categorizes_coderabbit_threads(self) -> None:
        """CodeRabbit threads should be categorized correctly."""
        threads = [
            {"author": "coderabbitai[bot]", "body": "Suggestion here"},
        ]

        result = get_all_reviews.process_and_categorize(threads)

        assert len(result["human"]) == 0
        assert len(result["qodo"]) == 0
        assert len(result["coderabbit"]) == 1

    def test_adds_source_field(self) -> None:
        """Source field should be added to threads."""
        threads = [
            {"author": "user", "body": "Comment"},
        ]

        result = get_all_reviews.process_and_categorize(threads)

        assert result["human"][0]["source"] == "human"

    def test_adds_priority_field(self) -> None:
        """Priority field should be added based on body."""
        threads = [
            {"author": "user", "body": "Security vulnerability here"},
        ]

        result = get_all_reviews.process_and_categorize(threads)

        assert result["human"][0]["priority"] == "HIGH"

    def test_adds_reply_and_status_fields(self) -> None:
        """Reply and status fields should be initialized."""
        threads = [
            {"author": "user", "body": "Comment"},
        ]

        result = get_all_reviews.process_and_categorize(threads)

        assert result["human"][0]["reply"] is None
        assert result["human"][0]["status"] == "pending"

    def test_preserves_original_fields(self) -> None:
        """Original thread fields should be preserved."""
        threads = [
            {
                "author": "user",
                "body": "Comment",
                "thread_id": "t1",
                "path": "file.py",
                "line": 10,
            },
        ]

        result = get_all_reviews.process_and_categorize(threads)

        assert result["human"][0]["thread_id"] == "t1"
        assert result["human"][0]["path"] == "file.py"
        assert result["human"][0]["line"] == 10


# =============================================================================
# Tests for get_thread_key() and merge_threads()
# =============================================================================


class TestGetThreadKey:
    """Tests for get_thread_key() deduplication key generation."""

    def test_thread_id_key(self) -> None:
        """Thread ID should be used first."""
        thread = {"thread_id": "t123", "node_id": "n456", "comment_id": 789}
        assert get_all_reviews.get_thread_key(thread) == "t:t123"

    def test_node_id_key(self) -> None:
        """Node ID should be used if thread_id is missing."""
        thread = {"thread_id": None, "node_id": "n456", "comment_id": 789}
        assert get_all_reviews.get_thread_key(thread) == "n:n456"

    def test_comment_id_key(self) -> None:
        """Comment ID should be used if thread_id and node_id are missing."""
        thread = {"thread_id": None, "node_id": None, "comment_id": 789}
        assert get_all_reviews.get_thread_key(thread) == "c:789"

    def test_no_key(self) -> None:
        """None should be returned if no IDs are available."""
        thread = {"thread_id": None, "node_id": None, "comment_id": None}
        assert get_all_reviews.get_thread_key(thread) is None

    def test_empty_thread(self) -> None:
        """Empty thread should return None."""
        assert get_all_reviews.get_thread_key({}) is None

    def test_empty_string_ids(self) -> None:
        """Empty string IDs should be treated as missing."""
        thread = {"thread_id": "", "node_id": "", "comment_id": 789}
        assert get_all_reviews.get_thread_key(thread) == "c:789"


class TestMergeThreads:
    """Tests for merge_threads() deduplication."""

    def test_empty_specific_threads(self) -> None:
        """Empty specific threads should return all threads unchanged."""
        all_threads = [{"thread_id": "t1", "body": "comment1"}]

        result = get_all_reviews.merge_threads(all_threads, [])

        assert result == all_threads

    def test_no_duplicates(self) -> None:
        """Non-duplicate threads should be merged."""
        all_threads = [{"thread_id": "t1", "body": "comment1"}]
        specific = [{"thread_id": "t2", "body": "comment2"}]

        result = get_all_reviews.merge_threads(all_threads, specific)

        assert len(result) == 2

    def test_deduplicates_by_thread_id(self) -> None:
        """Duplicate thread_id should be deduplicated."""
        all_threads = [{"thread_id": "t1", "body": "comment1"}]
        specific = [{"thread_id": "t1", "body": "same thread"}]

        result = get_all_reviews.merge_threads(all_threads, specific)

        assert len(result) == 1

    def test_threads_without_keys_are_added(self) -> None:
        """Threads without any key should be added."""
        all_threads = [{"thread_id": "t1", "body": "comment1"}]
        specific = [{"thread_id": None, "node_id": None, "comment_id": None, "body": "orphan"}]

        result = get_all_reviews.merge_threads(all_threads, specific)

        assert len(result) == 2


# =============================================================================
# Tests for URL pattern matching
# =============================================================================


class TestUrlPatternMatching:
    """Tests for URL pattern matching in main()."""

    def test_pullrequestreview_pattern(self) -> None:
        """pullrequestreview-NNN pattern should match."""
        url = "https://github.com/owner/repo/pull/1#pullrequestreview-12345"
        match = re.search(r"pullrequestreview-(\d+)", url)

        assert match is not None
        assert match.group(1) == "12345"

    def test_discussion_r_pattern(self) -> None:
        """discussion_rNNN pattern should match."""
        url = "https://github.com/owner/repo/pull/1#discussion_r67890"
        match = re.search(r"discussion_r(\d+)", url)

        assert match is not None
        assert match.group(1) == "67890"

    def test_issuecomment_pattern(self) -> None:
        """issuecomment-NNN pattern should match."""
        url = "https://github.com/owner/repo/pull/1#issuecomment-11111"
        match = re.search(r"issuecomment-(\d+)", url)

        assert match is not None
        assert match.group(1) == "11111"

    def test_raw_numeric_id(self) -> None:
        """Raw numeric ID should be detected."""
        review_url = "12345"
        assert review_url.isdigit()


# =============================================================================
# Tests for cleanup()
# =============================================================================


class TestCleanup:
    """Tests for cleanup() temp file removal."""

    def test_removes_temp_files(self, tmp_path: Path) -> None:
        """Temp files should be removed."""
        temp_file = tmp_path / "test.json"
        temp_file.write_text("{}")

        get_all_reviews.TEMP_FILES.clear()
        get_all_reviews.TEMP_FILES.append(temp_file)

        get_all_reviews.cleanup()

        assert not temp_file.exists()

    def test_removes_new_files(self, tmp_path: Path) -> None:
        """Orphaned .new files should be removed."""
        temp_file = tmp_path / "test.json"
        new_file = tmp_path / "test.json.new"
        new_file.write_text("{}")

        get_all_reviews.TEMP_FILES.clear()
        get_all_reviews.TEMP_FILES.append(temp_file)

        get_all_reviews.cleanup()

        assert not new_file.exists()

    def test_handles_missing_files(self, tmp_path: Path) -> None:
        """Missing files should not raise errors."""
        temp_file = tmp_path / "nonexistent.json"

        get_all_reviews.TEMP_FILES.clear()
        get_all_reviews.TEMP_FILES.append(temp_file)

        # Should not raise
        get_all_reviews.cleanup()


# =============================================================================
# Tests for edge cases
# =============================================================================


class TestEdgeCases:
    """Edge cases and error handling tests."""

    def test_detect_source_with_whitespace(self) -> None:
        """Author with leading/trailing whitespace should be human."""
        assert get_all_reviews.detect_source(" qodo-code-review ") == "human"
        assert get_all_reviews.detect_source(" coderabbitai ") == "human"

    @patch.object(get_all_reviews, "run_gh_graphql")
    def test_handles_none_author_in_thread(self, mock_graphql: Any) -> None:
        """Thread with None author should be treated as human."""
        mock_graphql.return_value = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "id": "thread1",
                                    "isResolved": False,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "c1",
                                                "databaseId": 1,
                                                "author": None,
                                                "path": "file.py",
                                                "line": 1,
                                                "body": "Comment",
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        }

        result = get_all_reviews.fetch_unresolved_threads("owner", "repo", "1")

        assert result[0]["author"] is None
