"""Post replies and resolve review threads from a JSON file.

This module posts replies and resolves review threads based on the JSON file
created by the fetch module and processed by an AI handler to add status/reply fields.

Expected JSON structure:
  {
    "metadata": { "owner": "...", "repo": "...", "pr_number": "..." },
    "human": [ ... ],      # Human review threads
    "qodo": [ ... ],       # Qodo AI review threads
    "coderabbit": [ ... ]  # CodeRabbit AI review threads
  }

Each thread in human/qodo/coderabbit arrays has:
  {
    "thread_id": "...",      # GraphQL thread ID (preferred)
    "node_id": "...",        # REST API node ID (fallback)
    "comment_id": 123,       # REST API comment ID
    "status": "addressed|skipped|pending|failed",
    "reply": "...",          # Reply message to post
    "skip_reason": "..."     # Reason for skipping (optional)
  }

Status handling:
  - addressed: Post reply and resolve thread
  - not_addressed: Post reply and resolve thread (similar to addressed)
  - skipped: Post reply (with skip reason) and resolve thread
  - pending: Skip (not processed yet)
  - failed: Retry posting

Resolution behavior by source:
  - qodo/coderabbit: Always resolve threads after replying
  - human: Only resolve if status is "addressed"; skipped/not_addressed
          threads are not resolved to allow reviewer follow-up
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def eprint(*args: Any, **kwargs: Any) -> None:
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)


def check_dependencies() -> None:
    """Check required dependencies are available."""
    for cmd in ["gh"]:
        if shutil.which(cmd) is None:
            eprint(f"Error: '{cmd}' is required but not installed.")
            sys.exit(1)


def run_graphql(query: str, variables: dict[str, str]) -> tuple[bool, dict[str, Any] | str]:
    """Run a GraphQL query via gh api graphql.

    Returns (success, result) where result is parsed JSON on success or error string on failure.
    """
    payload = {"query": query, "variables": variables}
    cmd = ["gh", "api", "graphql", "--input", "-"]

    try:
        result = subprocess.run(
            cmd,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "GraphQL query timed out after 120 seconds"

    # Use stdout for JSON parsing, combined output for error reporting
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    error_output = (stdout + ("\n" + stderr if stderr else "")).strip()

    if result.returncode != 0:
        return False, error_output

    # Validate JSON response - parse stdout only
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return False, error_output

    # Check for GraphQL errors
    if data.get("errors") and len(data["errors"]) > 0:
        error_msg = data["errors"][0].get("message", "Unknown error")
        return False, error_msg

    return True, data


def post_thread_reply(thread_id: str, body: str) -> bool:
    """Post a reply to a review thread using GraphQL.

    Returns True on success, False on failure.
    """
    # GitHub comment bodies have a size limit (~65KB); truncate to avoid failures
    max_len = 60000
    if len(body) > max_len:
        body = body[:max_len] + "\n...[truncated]"

    query = """
    mutation($threadId: ID!, $body: String!) {
      addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $threadId, body: $body}) {
        comment {
          id
        }
      }
    }
    """

    success, result = run_graphql(query, {"threadId": thread_id, "body": body})
    if not success:
        eprint(f"Error posting reply: {result}")
        return False

    return True


def resolve_thread(thread_id: str) -> bool:
    """Resolve a review thread using GraphQL.

    Returns True on success, False on failure.
    """
    query = """
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) {
        thread {
          id
          isResolved
        }
      }
    }
    """

    success, result = run_graphql(query, {"threadId": thread_id})
    if not success:
        eprint(f"Error resolving thread: {result}")
        return False

    return True


def post_issue_comment(owner: str, repo: str, pr_number: int | str, body: str) -> bool:
    """Post a new issue comment on a PR.

    Used for replying to Qodo issue comment suggestions, which cannot be
    replied to as review threads.

    Returns True on success, False on failure.
    """
    # Truncate body if too long
    max_len = 60000
    if len(body) > max_len:
        body = body[:max_len] + "\n...[truncated]"

    endpoint = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
    cmd = ["gh", "api", endpoint, "--method", "POST", "--input", "-"]
    payload = json.dumps({"body": body})

    try:
        result = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        eprint("Error: Issue comment post timed out after 120 seconds")
        return False

    if result.returncode != 0:
        stderr = result.stderr or ""
        eprint(f"Error posting issue comment: {stderr.strip()}")
        return False

    return True


def build_issue_comment_reply(
    suggestions: list[dict[str, Any]],
    original_comment_url: str,
) -> str:
    """Build a markdown reply summarizing decisions for Qodo issue comment suggestions.

    Groups all suggestions from one Qodo comment and formats them as a table
    with status and reply for each.

    Args:
        suggestions: List of thread dicts with status/reply populated.
        original_comment_url: URL to the original Qodo comment.

    Returns:
        Markdown-formatted reply body.
    """
    lines: list[str] = []
    lines.append(f"### Review of [Qodo suggestions]({original_comment_url})\n")
    lines.append("| # | Path | Status | Reply |")
    lines.append("|---|------|--------|-------|")

    for s in suggestions:
        i = s.get("suggestion_index", 0) + 1  # 1-indexed for display
        path = s.get("path") or "\u2014"
        path = path.replace("`", "'")
        status = s.get("status", "pending")
        reply = s.get("reply", "") or ""
        # Escape markdown-breaking characters in reply for table
        reply = reply.replace("|", "\\|").replace("\n", " ").replace("`", "'")
        # Truncate long replies in table (after escaping to avoid breaking escape sequences)
        if len(reply) > 100:
            reply = reply[:97] + "..."
        lines.append(f"| {i} | `{path}` | {status} | {reply} |")

    return "\n".join(lines)


def lookup_thread_id_from_node_id(node_id: str) -> str | None:
    """Look up thread_id from a review comment node_id via GraphQL.

    Returns thread_id on success, None on failure.
    """
    query = """
    query($nodeId: ID!) {
      node(id: $nodeId) {
        ... on PullRequestReviewComment {
          pullRequestReviewThread {
            id
          }
        }
      }
    }
    """

    success, result = run_graphql(query, {"nodeId": node_id})
    if not success:
        return None

    if not isinstance(result, dict):
        return None

    # Navigate the response structure
    try:
        thread_id = result["data"]["node"]["pullRequestReviewThread"]["id"]
        return thread_id if thread_id else None
    except (KeyError, TypeError):
        return None


def get_utc_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def apply_updates_to_json(json_path: Path, updates: list[dict[str, Any]]) -> None:
    """Apply updates to JSON file atomically."""
    if not updates:
        return

    eprint("")
    eprint(f"Updating JSON file with {len(updates)} timestamps...")

    # Read current JSON
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # Valid fields that can be updated
    valid_fields = {"posted_at", "resolved_at"}

    # Apply updates with validation
    for update in updates:
        cat = update["cat"]
        idx = update["idx"]
        field = update["field"]
        ts = update["ts"]

        # Validate category exists
        if cat not in data:
            eprint(f"Warning: category '{cat}' not found in JSON, skipping update")
            continue

        # Validate index is valid
        if not isinstance(data[cat], list) or idx < 0 or idx >= len(data[cat]):
            eprint(f"Warning: invalid index {idx} for category '{cat}', skipping update")
            continue

        # Validate field is valid
        if field not in valid_fields:
            eprint(f"Warning: invalid field '{field}', expected one of {valid_fields}, skipping update")
            continue

        # Validate timestamp is non-empty string
        if not isinstance(ts, str) or not ts:
            eprint(f"Warning: invalid timestamp '{ts}' for {cat}[{idx}].{field}, skipping update")
            continue

        data[cat][idx][field] = ts

    # Write atomically via temp file
    fd, tmp_path = tempfile.mkstemp(dir=json_path.parent, suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, json_path)
    except (json.JSONDecodeError, OSError, KeyError) as exc:
        # Clean up temp file on error
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        eprint(f"Error: Failed to apply JSON updates: {exc}")
        sys.exit(1)


def run(json_path: str) -> None:
    """Main entry point.

    Args:
        json_path: Path to JSON file with review data.
    """
    check_dependencies()

    json_path_obj = Path(json_path).resolve()

    # Validate JSON file exists
    if not json_path_obj.is_file():
        eprint(f"Error: JSON file not found: {json_path}")
        sys.exit(1)

    # Validate JSON is readable and well-formed
    try:
        with open(json_path_obj, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        eprint(f"Error: Invalid JSON file: {json_path}")
        sys.exit(1)

    # Extract metadata
    metadata = data.get("metadata", {})
    owner = metadata.get("owner", "")
    repo = metadata.get("repo", "")
    pr_number = metadata.get("pr_number", "")

    if not owner or not repo or not pr_number:
        eprint("Error: Missing metadata in JSON file (owner, repo, or pr_number)")
        sys.exit(1)

    eprint(f"Processing reviews for {owner}/{repo}#{pr_number}")

    # Categories to process
    categories = ["human", "qodo", "coderabbit"]

    # Get total thread count across all categories
    total_thread_count = sum(len(data.get(cat, [])) for cat in categories)

    if total_thread_count == 0:
        eprint("No threads to process")
        sys.exit(0)

    eprint(f"Processing {total_thread_count} threads sequentially...")

    # Counters for summary
    addressed_count = 0
    skipped_count = 0
    pending_count = 0
    failed_count = 0
    no_thread_id_count = 0
    replied_not_resolved_count = 0
    already_posted_count = 0

    # Track issue comment suggestions for batch posting
    issue_comment_groups: dict[int, list[tuple[str, int, dict[str, Any]]]] = {}

    # Track updates for atomic application
    updates: list[dict[str, Any]] = []

    # Process each category
    for category in categories:
        category_threads = data.get(category, [])
        thread_count = len(category_threads)

        if thread_count == 0:
            continue

        eprint(f"Processing {thread_count} threads in {category}...")

        for i, thread_data in enumerate(category_threads):
            # Extract fields
            thread_id = thread_data.get("thread_id", "") or ""
            node_id = thread_data.get("node_id", "") or ""
            status = thread_data.get("status", "pending") or "pending"
            reply = thread_data.get("reply", "") or ""
            skip_reason = thread_data.get("skip_reason", "") or ""
            posted_at = thread_data.get("posted_at", "") or ""
            resolved_at = thread_data.get("resolved_at", "") or ""
            path = thread_data.get("path", "unknown") or "unknown"

            # Issue comment suggestions are handled via batch posting, not thread resolution
            if thread_data.get("type") == "issue_comment_suggestion":
                # Skip if already posted
                if thread_data.get("posted_at"):
                    already_posted_count += 1
                    eprint(f"Skipping {category}[{i}] ({path}): issue comment suggestion already posted")
                    continue
                raw_ic_id = thread_data.get("issue_comment_id")
                if raw_ic_id is not None:
                    try:
                        ic_id = int(raw_ic_id)
                    except (TypeError, ValueError):
                        eprint(f"Warning: Skipping {category}[{i}] ({path}): invalid issue_comment_id: {raw_ic_id!r}")
                        continue
                    issue_comment_groups.setdefault(ic_id, []).append((category, i, thread_data))
                continue

            # Determine if we should resolve this thread (MUST be before resolve_only_retry check)
            should_resolve = True
            if category == "human" and status != "addressed":
                should_resolve = False

            # Determine if this is a resolve-only retry (posted but not resolved)
            resolve_only_retry = False
            if posted_at and not resolved_at:
                if should_resolve:
                    resolve_only_retry = True
                    eprint(f"Retrying resolve for {category}[{i}] ({path}): posted at {posted_at} but not resolved")
                else:
                    already_posted_count += 1
                    eprint(
                        f"Skipping {category}[{i}] ({path}): reply already posted at "
                        f"{posted_at} (not resolving by policy)"
                    )
                    continue
            elif posted_at:
                # Already fully processed (posted and resolved)
                already_posted_count += 1
                eprint(f"Skipping {category}[{i}] ({path}): already posted at {posted_at}")
                continue

            # Skip pending threads
            if status == "pending":
                pending_count += 1
                eprint(f"Skipping {category}[{i}] ({path}): status is pending")
                continue

            # Determine which ID to use for GraphQL
            effective_thread_id = ""
            if thread_id and thread_id != "null":
                effective_thread_id = thread_id
            elif node_id and node_id != "null":
                # Try to derive thread_id from the review comment node id
                looked_up_id = lookup_thread_id_from_node_id(node_id)
                if looked_up_id is None:
                    eprint(f"Warning: Failed to look up thread_id from node_id for {category}[{i}] ({path})")
                else:
                    effective_thread_id = looked_up_id

            # Check if we have a usable thread ID
            if not effective_thread_id:
                no_thread_id_count += 1
                eprint(f"Warning: No resolvable thread_id for {category}[{i}] ({path}) - cannot post reply")
                continue

            # Build reply message based on status
            reply_message = ""
            if status == "addressed":
                reply_message = reply if reply else "Addressed."
            elif status == "skipped":
                if skip_reason:
                    reply_message = f"Skipped: {skip_reason}"
                elif reply:
                    reply_message = reply
                else:
                    reply_message = "Skipped."
            elif status == "not_addressed":
                reply_message = reply if reply else "Not addressed - see reply for details."
            elif status == "failed":
                reply_message = reply if reply else "Addressed."
            else:
                eprint(f"Warning: Unknown status for {category}[{i}] ({path}): {status}")
                continue

            # Post reply only if not already posted
            if not resolve_only_retry:
                if not post_thread_reply(effective_thread_id, reply_message):
                    failed_count += 1
                    eprint(f"Failed to post reply for {category}[{i}] ({path})")
                    continue

            # Resolve thread only if appropriate
            if should_resolve:
                if not resolve_thread(effective_thread_id):
                    # Record posted_at if we just posted (so next run can retry resolve only)
                    if not resolve_only_retry:
                        posted_at_timestamp = get_utc_timestamp()
                        updates.append({"cat": category, "idx": i, "field": "posted_at", "ts": posted_at_timestamp})
                    failed_count += 1
                    eprint(f"Failed to resolve {category}[{i}] ({path}) - reply was posted but thread not resolved")
                    continue

                # Record both timestamps after successful resolve
                if not resolve_only_retry:
                    posted_at_timestamp = get_utc_timestamp()
                    updates.append({"cat": category, "idx": i, "field": "posted_at", "ts": posted_at_timestamp})
                resolved_at_timestamp = get_utc_timestamp()
                updates.append({"cat": category, "idx": i, "field": "resolved_at", "ts": resolved_at_timestamp})

                if status in ("addressed", "not_addressed", "failed"):
                    addressed_count += 1
                elif status == "skipped":
                    skipped_count += 1

                eprint(f"Resolved {category}[{i}] ({path})")
            else:
                # For threads we don't resolve, record posted_at after successful reply
                if not resolve_only_retry:
                    posted_at_timestamp = get_utc_timestamp()
                    updates.append({"cat": category, "idx": i, "field": "posted_at", "ts": posted_at_timestamp})
                replied_not_resolved_count += 1
                eprint(f"Replied to {category}[{i}] ({path}) (not resolved)")

    # Batch-post replies for issue comment suggestions
    ic_posted_count = 0
    ic_skipped_count = 0
    if issue_comment_groups:
        eprint(f"\nProcessing {len(issue_comment_groups)} Qodo issue comment(s) with suggestions...")
        for ic_id, entries in issue_comment_groups.items():
            # Check if any suggestions have actionable status
            actionable: list[tuple[str, int, dict[str, Any]]] = []
            for entry in entries:
                if entry[2].get("status") not in ("pending", None):
                    actionable.append(entry)
            if not actionable:
                ic_skipped_count += len(entries)
                continue

            # Build comment URL from metadata
            comment_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}#issuecomment-{ic_id}"

            reply_body = build_issue_comment_reply([entry[2] for entry in actionable], comment_url)
            if post_issue_comment(owner, repo, pr_number, reply_body):
                ic_posted_count += len(actionable)
                ts = get_utc_timestamp()
                for entry in actionable:
                    updates.append({"cat": entry[0], "idx": entry[1], "field": "posted_at", "ts": ts})
                eprint(f"Posted summary reply for issue comment {ic_id} ({len(actionable)} suggestions)")
            else:
                failed_count += len(actionable)
                eprint(f"Failed to post summary reply for issue comment {ic_id}")

    # Report issue comment stats in summary
    if ic_posted_count > 0 or ic_skipped_count > 0:
        eprint(f"  Issue comment suggestions: {ic_posted_count} replied, {ic_skipped_count} pending")

    # Apply all JSON updates atomically
    apply_updates_to_json(json_path_obj, updates)

    # Print summary
    total_resolved = addressed_count + skipped_count
    total_processed = total_resolved + replied_not_resolved_count
    eprint("")
    eprint("=== Summary ===")
    eprint(f"Processed {total_processed} threads")
    eprint(f"  Resolved: {total_resolved} ({addressed_count} addressed, {skipped_count} skipped)")

    if replied_not_resolved_count > 0:
        eprint(f"  Replied only: {replied_not_resolved_count} (human reviews - awaiting reviewer follow-up)")

    if pending_count > 0:
        eprint(f"  Pending: {pending_count} threads (not processed yet)")

    if no_thread_id_count > 0:
        eprint(
            f"  Skipped: {no_thread_id_count} threads "
            "(no thread_id - likely fetched via REST API without GraphQL thread ID)"
        )

    if already_posted_count > 0:
        eprint(f"  Already posted: {already_posted_count} threads")

    if failed_count > 0:
        eprint(f"Failed: {failed_count} threads")
        # Print actionable retry instruction to stdout for AI callers
        print(
            f"\nACTION REQUIRED: {failed_count} thread(s) failed to post."
            f" Re-run the command to retry failed entries:"
            f"\n  myk-claude-tools reviews post {shlex.quote(str(json_path_obj))}",
            flush=True,
        )
        sys.exit(1)

    sys.exit(0)
