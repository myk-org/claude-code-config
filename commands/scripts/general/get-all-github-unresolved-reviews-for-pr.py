#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Unified script to fetch ALL unresolved review threads from a PR
and categorize them by source (human, qodo, coderabbit).

Usage: uv run get-all-github-unresolved-reviews-for-pr.py [review_url]

Arguments:
    review_url  Optional: specific review URL for context
                (e.g., #pullrequestreview-XXX or #discussion_rXXX)

Output: JSON with metadata and categorized comments

Dependencies: gh CLI, get-pr-info.sh (in same directory)
"""

from __future__ import annotations

import argparse

# Import ReviewDB from same directory without mutating sys.path
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_REVIEW_DB_PATH = Path(__file__).with_name("review_db.py")

_REVIEW_DB_CACHE: tuple[type | None, Any | None] | None = None


def _load_review_db() -> tuple[type | None, Any | None]:
    """Lazily load ReviewDB and similarity function, returning (None, None) if unavailable."""
    global _REVIEW_DB_CACHE
    if _REVIEW_DB_CACHE is not None:
        return _REVIEW_DB_CACHE

    try:
        if not _REVIEW_DB_PATH.exists():
            _REVIEW_DB_CACHE = (None, None)
            return _REVIEW_DB_CACHE

        spec = importlib.util.spec_from_file_location("review_db", _REVIEW_DB_PATH)
        if spec is None or spec.loader is None:
            _REVIEW_DB_CACHE = (None, None)
            return _REVIEW_DB_CACHE

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _REVIEW_DB_CACHE = (getattr(module, "ReviewDB", None), getattr(module, "_body_similarity", None))
        return _REVIEW_DB_CACHE
    except Exception as e:
        print_stderr(f"Warning: review_db integration disabled: {e}")
        _REVIEW_DB_CACHE = (None, None)
        return _REVIEW_DB_CACHE


def _fallback_body_similarity(body1: str, body2: str) -> float:
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


# Known AI reviewer usernames
QODO_USERS = ["qodo-code-review", "qodo-code-review[bot]"]
CODERABBIT_USERS = ["coderabbitai", "coderabbitai[bot]"]

# Priority classification keywords
HIGH_PRIORITY_KEYWORDS = re.compile(
    r"(security|vulnerability|critical|bug|error|crash|must|required|breaking|urgent|injection|xss|csrf|auth)",
    re.IGNORECASE,
)
LOW_PRIORITY_KEYWORDS = re.compile(
    r"(style|formatting|typo|nitpick|nit:|minor|optional|cosmetic|whitespace|indentation)",
    re.IGNORECASE,
)

# Track temp files for cleanup
TEMP_FILES: list[Path] = []


def cleanup() -> None:
    """Remove tracked temp files and any orphaned .new files from atomic updates."""
    for f in TEMP_FILES:
        try:
            f.unlink(missing_ok=True)
            Path(str(f) + ".new").unlink(missing_ok=True)
        except OSError:
            pass


def print_stderr(msg: str) -> None:
    """Print message to stderr."""
    print(msg, file=sys.stderr)


def show_usage() -> None:
    """Show usage information and exit."""
    print_stderr("Usage: get-all-github-unresolved-reviews-for-pr.py [review_url]")
    print_stderr("")
    print_stderr("Fetches ALL unresolved review threads from the current PR")
    print_stderr("and categorizes them by source (human, qodo, coderabbit).")
    print_stderr("")
    print_stderr("Arguments:")
    print_stderr("  review_url  Optional: specific review URL for context")
    print_stderr("")
    print_stderr("Output:")
    print_stderr("  JSON with metadata and categorized comments")
    print_stderr("  Also saves to /tmp/claude/pr-<number>-reviews.json")
    print_stderr("")
    print_stderr("Examples:")
    print_stderr("  get-all-github-unresolved-reviews-for-pr.py")
    print_stderr(
        "  get-all-github-unresolved-reviews-for-pr.py https://github.com/org/repo/pull/123#pullrequestreview-456"
    )
    sys.exit(1)


def check_dependencies() -> Path:
    """Check required dependencies and return path to PR info script."""
    # Check for gh using shutil.which (consistent with post-review-replies-from-json.py)
    if shutil.which("gh") is None:
        print_stderr("Error: 'gh' is required but not installed.")
        sys.exit(1)

    # Check for PR info script
    script_dir = Path(__file__).parent.resolve()
    pr_info_script = script_dir / "get-pr-info.sh"
    if not pr_info_script.exists():
        print_stderr(f"Error: PR info script not found: {pr_info_script}")
        sys.exit(1)

    return pr_info_script


def detect_source(author: str | None) -> str:
    """Detect source from author login. Returns 'qodo', 'coderabbit', or 'human'."""
    if author is None:
        return "human"

    if author in QODO_USERS:
        return "qodo"

    if author in CODERABBIT_USERS:
        return "coderabbit"

    return "human"


def classify_priority(body: str | None) -> str:
    """Classify priority from comment body. Returns 'HIGH', 'MEDIUM', or 'LOW'."""
    if body is None:
        return "MEDIUM"

    # HIGH: security, bugs, critical issues
    if HIGH_PRIORITY_KEYWORDS.search(body):
        return "HIGH"

    # LOW: style, formatting, minor
    if LOW_PRIORITY_KEYWORDS.search(body):
        return "LOW"

    # MEDIUM: improvements, suggestions (or default)
    return "MEDIUM"


def run_gh_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any] | None:
    """Run a GraphQL query via gh api graphql. Returns parsed JSON or None on error."""
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]

    for key, value in variables.items():
        if isinstance(value, int):
            cmd.extend(["-F", f"{key}={value}"])
        else:
            cmd.extend(["-f", f"{key}={value}"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print_stderr("Error: GraphQL query timed out after 120 seconds")
        return None

    if result.returncode != 0:
        if result.stderr:
            print_stderr(f"Warning: GraphQL query failed: {result.stderr.strip()}")
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    return data


def run_gh_api(endpoint: str, paginate: bool = False) -> Any | None:
    """Run a REST API call via gh api. Returns parsed JSON or None on error."""
    cmd = ["gh", "api"]
    if paginate:
        cmd.extend(["--paginate", "--slurp"])
    cmd.append(endpoint)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print_stderr(f"Error: API call to {endpoint} timed out after 120 seconds")
        return None

    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout)
        # With --slurp, paginated results are wrapped in an outer array
        # Flatten nested arrays for consistency
        if paginate and isinstance(data, list):
            merged = []
            for item in data:
                if isinstance(item, list):
                    merged.extend(item)
                else:
                    merged.append(item)
            return merged
        return data
    except json.JSONDecodeError as e:
        print_stderr(f"Error parsing JSON from gh api: {e}")
        return None


def fetch_unresolved_threads(owner: str, repo: str, pr_number: str) -> list[dict[str, Any]]:
    """Fetch all unresolved review threads using paginated GraphQL."""
    all_threads: list[dict[str, Any]] = []
    cursor: str | None = None
    has_next_page = True
    page_count = 0

    query_first = """
        query($owner: String!, $repo: String!, $pr: Int!) {
            repository(owner: $owner, name: $repo) {
                pullRequest(number: $pr) {
                    reviewThreads(first: 100) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            id
                            isResolved
                            comments(first: 100) {
                                nodes {
                                    id
                                    databaseId
                                    author { login }
                                    path
                                    line
                                    body
                                    createdAt
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    query_with_cursor = """
        query($owner: String!, $repo: String!, $pr: Int!, $cursor: String!) {
            repository(owner: $owner, name: $repo) {
                pullRequest(number: $pr) {
                    reviewThreads(first: 100, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            id
                            isResolved
                            comments(first: 100) {
                                nodes {
                                    id
                                    databaseId
                                    author { login }
                                    path
                                    line
                                    body
                                    createdAt
                                }
                            }
                        }
                    }
                }
            }
        }
    """

    while has_next_page:
        page_count += 1

        if cursor is None:
            variables = {"owner": owner, "repo": repo, "pr": int(pr_number)}
            raw_result = run_gh_graphql(query_first, variables)
        else:
            variables = {"owner": owner, "repo": repo, "pr": int(pr_number), "cursor": cursor}
            raw_result = run_gh_graphql(query_with_cursor, variables)

        if raw_result is None:
            print_stderr(f"Warning: Could not fetch unresolved threads (page {page_count})")
            break

        # Check for GraphQL errors
        if raw_result.get("errors"):
            error_msg = raw_result["errors"][0].get("message", "Unknown error")
            print_stderr(f"Warning: GraphQL errors while fetching review threads (page {page_count}): {error_msg}")
            break

        # Extract data
        try:
            review_threads = raw_result["data"]["repository"]["pullRequest"]["reviewThreads"]
            page_info = review_threads["pageInfo"]
            nodes = review_threads.get("nodes") or []
        except (KeyError, TypeError):
            print_stderr(f"Warning: Unexpected GraphQL response structure (page {page_count})")
            break

        has_next_page = page_info.get("hasNextPage", False)
        cursor = page_info.get("endCursor")

        all_threads.extend(nodes)

        if has_next_page:
            print_stderr(f"Fetching page {page_count + 1} of review threads...")

    if page_count > 1:
        print_stderr(f"Fetched {page_count} pages of review threads")

    # Filter unresolved threads and extract first comment details with replies
    result = []
    for thread in all_threads:
        if thread.get("isResolved", False):
            continue

        comments = thread.get("comments", {}).get("nodes") or []
        if not comments:
            continue

        first_comment = comments[0]
        rest_comments = comments[1:]

        thread_data = {
            "thread_id": thread.get("id"),
            "node_id": first_comment.get("id"),
            "comment_id": first_comment.get("databaseId"),
            "author": first_comment.get("author", {}).get("login") if first_comment.get("author") else None,
            "path": first_comment.get("path"),
            "line": first_comment.get("line"),
            "body": first_comment.get("body", ""),
            "replies": [
                {
                    "author": c.get("author", {}).get("login") if c.get("author") else None,
                    "body": c.get("body", ""),
                    "created_at": c.get("createdAt"),
                }
                for c in rest_comments
            ],
        }
        result.append(thread_data)

    return result


def fetch_specific_discussion(owner: str, repo: str, pr_number: str, discussion_id: str) -> list[dict[str, Any]]:
    """Fetch a specific review thread by discussion ID."""
    endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/comments/{discussion_id}"
    result = run_gh_api(endpoint)

    if result is None:
        print_stderr(f"Warning: Could not fetch discussion {discussion_id}")
        return []

    return [
        {
            "thread_id": None,
            "node_id": result.get("node_id"),
            "comment_id": result.get("id"),
            "author": result.get("user", {}).get("login") if result.get("user") else None,
            "path": result.get("path"),
            "line": result.get("line"),
            "body": result.get("body"),
        }
    ]


def fetch_review_comments(owner: str, repo: str, pr_number: str, review_id: str) -> list[dict[str, Any]]:
    """Fetch inline comments from a specific PR review."""
    endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews/{review_id}/comments"
    result = run_gh_api(endpoint, paginate=True)

    if result is None:
        print_stderr(f"Warning: Could not fetch review {review_id} comments")
        return []

    return [
        {
            "thread_id": None,
            "node_id": item.get("node_id"),
            "comment_id": item.get("id"),
            "author": item.get("user", {}).get("login") if item.get("user") else None,
            "path": item.get("path"),
            "line": item.get("line"),
            "body": item.get("body"),
        }
        for item in result
    ]


def process_and_categorize(threads: list[dict[str, Any]], owner: str, repo: str) -> dict[str, list[dict[str, Any]]]:
    """Process threads: add source and priority, categorize, and auto-skip previously dismissed."""
    human: list[dict[str, Any]] = []
    qodo: list[dict[str, Any]] = []
    coderabbit: list[dict[str, Any]] = []

    # Lazily load ReviewDB and instantiate once outside the loop for performance
    ReviewDB, sim_fn = _load_review_db()
    similarity = sim_fn or _fallback_body_similarity  # Use imported or fallback
    db = None
    if ReviewDB:
        try:
            db = ReviewDB(db_path=None)  # Auto-detect path
        except Exception as e:
            print_stderr(f"Warning: Failed to initialize ReviewDB: {e}")

    # Preload and index dismissed comments once per run for performance
    dismissed_by_path: dict[str, list[dict[str, Any]]] = {}
    if db:
        try:
            for c in db.get_dismissed_comments(owner, repo):
                p = (c.get("path") or "").strip()
                b = (c.get("body") or "").strip()
                if p and b:
                    dismissed_by_path.setdefault(p, []).append(c)
        except Exception as e:
            print_stderr(f"Warning: Failed to preload dismissed comments: {e}")
            dismissed_by_path = {}

    for thread in threads:
        author = thread.get("author")
        body = thread.get("body")

        source = detect_source(author)
        priority = classify_priority(body)

        enriched = {
            **thread,
            "source": source,
            "priority": priority,
            "reply": None,
            "status": "pending",
        }

        # Check for previously dismissed similar comment
        if dismissed_by_path:
            path = (thread.get("path") or "").strip()
            thread_body = (thread.get("body") or "").strip()
            if path and thread_body:
                try:
                    # Find best matching dismissed comment
                    best = None
                    best_score = 0.0
                    for prev in dismissed_by_path.get(path, []):
                        prev_body = (prev.get("body") or "").strip()
                        if not prev_body:
                            continue
                        score = similarity(thread_body, prev_body)
                        if score >= 0.6 and score > best_score:
                            best = prev
                            best_score = score

                    if best:
                        reason = (best.get("reply") or "").strip()
                        if reason:
                            enriched["status"] = "skipped"
                            enriched["skip_reason"] = reason
                            enriched["reply"] = f"Auto-skipped: Previously dismissed - {reason}"
                            enriched["is_auto_skipped"] = True
                except Exception as e:
                    print_stderr(f"Warning: Failed to match dismissed comment: {e}")

        if source == "human":
            human.append(enriched)
        elif source == "qodo":
            qodo.append(enriched)
        else:
            coderabbit.append(enriched)

    return {"human": human, "qodo": qodo, "coderabbit": coderabbit}


def get_thread_key(thread: dict[str, Any]) -> str | None:
    """Generate a unique key for deduplication."""
    thread_id = thread.get("thread_id")
    if thread_id:
        return f"t:{thread_id}"

    node_id = thread.get("node_id")
    if node_id:
        return f"n:{node_id}"

    comment_id = thread.get("comment_id")
    if comment_id is not None:
        return f"c:{comment_id}"

    return None


def merge_threads(all_threads: list[dict[str, Any]], specific_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge specific threads with all threads, deduplicating by prioritized keys."""
    if not specific_threads:
        return all_threads

    existing_keys = set()
    for thread in all_threads:
        key = get_thread_key(thread)
        if key:
            existing_keys.add(key)

    merged = list(all_threads)
    for thread in specific_threads:
        key = get_thread_key(thread)
        if key is None:
            print_stderr("Warning: Thread has no identifiers for deduplication")
            merged.append(thread)
        elif key not in existing_keys:
            merged.append(thread)

    return merged


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch all unresolved review threads from a PR",
        add_help=True,
    )
    parser.add_argument(
        "review_url",
        nargs="?",
        default="",
        help="Optional: specific review URL for context",
    )
    args = parser.parse_args()

    try:
        pr_info_script = check_dependencies()

        review_url = args.review_url

        # Get PR info
        print_stderr("Getting PR information...")
        try:
            result = subprocess.run(
                [str(pr_info_script)],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            print_stderr("Error: PR info script timed out after 120 seconds")
            return 1

        if result.returncode != 0:
            print_stderr(f"Error: Failed to get PR information: {result.stderr.strip()}")
            return 1

        pr_info = result.stdout.strip()
        parts = pr_info.split()

        if len(parts) < 2:
            print_stderr(f"Error: Invalid PR info output: '{pr_info}'")
            print_stderr("Expected format: 'owner/repo pr_number'")
            return 1

        repo_full_name = parts[0]
        pr_number = parts[1]

        if not pr_number.isdigit():
            print_stderr(f"Error: PR number must be numeric, got: '{pr_number}'")
            return 1

        owner_repo = repo_full_name.split("/")
        if len(owner_repo) != 2:
            print_stderr(f"Error: Could not parse owner/repo from: '{repo_full_name}'")
            return 1

        owner, repo = owner_repo

        if not owner or not repo:
            print_stderr(f"Error: Could not parse owner/repo from: '{repo_full_name}'")
            return 1

        print_stderr(f"Repository: {owner}/{repo}, PR: {pr_number}")

        # Ensure output directory exists
        tmp_base = os.environ.get("TMPDIR", "/tmp")
        out_dir = Path(tmp_base.rstrip("/")) / "claude"
        if not out_dir.exists():
            out_dir.mkdir(parents=True, mode=0o700)
        else:
            try:
                out_dir.chmod(0o700)
            except OSError:
                pass

        json_path = out_dir / f"pr-{pr_number}-reviews.json"

        # Fetch all unresolved threads
        print_stderr("Fetching unresolved review threads...")
        all_threads = fetch_unresolved_threads(owner, repo, pr_number)
        print_stderr(f"Found {len(all_threads)} unresolved thread(s)")

        # If review URL provided, also fetch specific thread(s)
        specific_threads: list[dict[str, Any]] = []
        if review_url:
            # Match pullrequestreview-NNN
            match = re.search(r"pullrequestreview-(\d+)", review_url)
            if match:
                review_id = match.group(1)
                print_stderr(f"Fetching comments from PR review {review_id}...")
                specific_threads = fetch_review_comments(owner, repo, pr_number, review_id)
                print_stderr(f"Found {len(specific_threads)} comment(s) from review {review_id}")

            # Match discussion_rNNN
            elif match := re.search(r"discussion_r(\d+)", review_url):
                discussion_id = match.group(1)
                print_stderr(f"Fetching discussion {discussion_id}...")
                specific_threads = fetch_specific_discussion(owner, repo, pr_number, discussion_id)
                print_stderr(f"Found {len(specific_threads)} comment(s) from discussion {discussion_id}")

            # Match issuecomment-NNN
            elif re.search(r"issuecomment-(\d+)", review_url):
                print_stderr("Note: Issue comments (#issuecomment-*) are not review threads, skipping specific fetch")

            # Match raw numeric review ID
            elif review_url.isdigit():
                review_id = review_url
                print_stderr(f"Fetching comments from PR review {review_id} (raw ID)...")
                specific_threads = fetch_review_comments(owner, repo, pr_number, review_id)
                print_stderr(f"Found {len(specific_threads)} comment(s) from review {review_id}")

            else:
                print_stderr(f"Warning: Unrecognized URL fragment in: {review_url}")

        # Merge specific threads with all threads, deduplicating
        if specific_threads:
            all_threads = merge_threads(all_threads, specific_threads)

        # Process and categorize threads
        print_stderr("Categorizing threads by source...")
        categorized = process_and_categorize(all_threads, owner, repo)

        # Build final output
        final_output = {
            "metadata": {
                "owner": owner,
                "repo": repo,
                "pr_number": int(pr_number),
                "json_path": str(json_path),
            },
            "human": categorized["human"],
            "qodo": categorized["qodo"],
            "coderabbit": categorized["coderabbit"],
        }

        # Save to file atomically
        fd, tmp_json_path = tempfile.mkstemp(
            prefix=f"pr-{pr_number}-reviews.json.",
            dir=str(out_dir),
        )
        tmp_path = Path(tmp_json_path)
        TEMP_FILES.append(tmp_path)

        try:
            with os.fdopen(fd, "w") as f:
                json.dump(final_output, f, indent=2)
            os.replace(tmp_path, json_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        print_stderr(f"Saved to: {json_path}")

        # Count by category
        human_count = len(final_output["human"])
        qodo_count = len(final_output["qodo"])
        coderabbit_count = len(final_output["coderabbit"])
        print_stderr(f"Categories: human={human_count}, qodo={qodo_count}, coderabbit={coderabbit_count}")

        # Count auto-skipped comments
        auto_skipped = sum(1 for cat in categorized.values() for c in cat if c.get("is_auto_skipped"))
        if auto_skipped:
            print_stderr(f"Auto-skipped {auto_skipped} previously dismissed comment(s)")

        # Output to stdout
        print(json.dumps(final_output, indent=2))

        return 0

    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
