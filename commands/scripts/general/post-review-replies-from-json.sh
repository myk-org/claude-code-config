#!/usr/bin/env bash
set -euo pipefail

# Post replies and resolve review threads from a JSON file
#
# Usage: post-review-replies-from-json.sh <json_path>
#
# Input:
#   $1 - Path to JSON file with review data (created by get-all-github-unresolved-reviews-for-pr.sh
#        and processed by an AI handler to add status/reply fields)
#
# Expected JSON structure:
#   {
#     "metadata": { "owner": "...", "repo": "...", "pr_number": "..." },
#     "human": [ ... ],      # Human review threads
#     "qodo": [ ... ],       # Qodo AI review threads
#     "coderabbit": [ ... ]  # CodeRabbit AI review threads
#   }
#
# Each thread in human/qodo/coderabbit arrays has:
#   {
#     "thread_id": "...",      # GraphQL thread ID (preferred)
#     "node_id": "...",        # REST API node ID (fallback)
#     "comment_id": 123,       # REST API comment ID
#     "status": "addressed|skipped|pending|failed",
#     "reply": "...",          # Reply message to post
#     "skip_reason": "..."     # Reason for skipping (optional)
#   }
#
# Status handling:
#   - addressed: Post reply and resolve thread
#   - not_addressed: Post reply and resolve thread (similar to addressed)
#   - skipped: Post reply (with skip reason) and resolve thread
#   - pending: Skip (not processed yet)
#   - failed: Retry posting
#
# Resolution behavior by source:
#   - qodo/coderabbit: Always resolve threads after replying
#   - human: Only resolve if status is "addressed"; skipped/not_addressed
#           threads are not resolved to allow reviewer follow-up
#
# Output:
#   - Updates JSON file with posted_at timestamp for each successful post
#   - Summary to stderr

# Check required dependencies
for cmd in gh jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' is required but not installed." >&2; exit 1; }
done

show_usage() {
  echo "Usage: $0 <json_path>" >&2
  echo "" >&2
  echo "Reads review JSON and posts replies/resolves threads." >&2
  echo "" >&2
  echo "Arguments:" >&2
  echo "  json_path  Path to JSON file with review data" >&2
  echo "" >&2
  echo "Example:" >&2
  echo "  $0 /tmp/claude/reviews.json" >&2
  exit 1
}

# Post a reply to a review thread using GraphQL
# Returns 0 on success, 1 on failure
post_thread_reply() {
  local thread_id="$1"
  local body="$2"

  local result
  if ! result=$(gh api graphql -f query='
    mutation($threadId: ID!, $body: String!) {
      addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $threadId, body: $body}) {
        comment {
          id
        }
      }
    }
  ' -f threadId="$thread_id" -f body="$body" 2>&1); then
    echo "Error posting reply: $result" >&2
    return 1
  fi

  # Check for GraphQL errors
  if echo "$result" | jq -e '.errors' >/dev/null 2>&1; then
    local error_msg
    error_msg=$(echo "$result" | jq -r '.errors[0].message // "Unknown error"')
    echo "GraphQL error: $error_msg" >&2
    return 1
  fi

  return 0
}

# Resolve a review thread using GraphQL
# Returns 0 on success, 1 on failure
resolve_thread() {
  local thread_id="$1"

  local result
  if ! result=$(gh api graphql -f query='
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) {
        thread {
          id
          isResolved
        }
      }
    }
  ' -f threadId="$thread_id" 2>&1); then
    echo "Error resolving thread: $result" >&2
    return 1
  fi

  # Check for GraphQL errors
  if echo "$result" | jq -e '.errors' >/dev/null 2>&1; then
    local error_msg
    error_msg=$(echo "$result" | jq -r '.errors[0].message // "Unknown error"')
    echo "GraphQL error: $error_msg" >&2
    return 1
  fi

  return 0
}

# Update JSON file to add posted_at timestamp to a thread
# Args: json_path, category (human|qodo|coderabbit), index, timestamp
update_json_with_timestamp() {
  local json_path="$1"
  local category="$2"
  local index="$3"
  local timestamp="$4"

  local tmp_file="${json_path}.tmp"
  if ! jq --arg cat "$category" --arg idx "$index" --arg ts "$timestamp" \
    '.[$cat][($idx | tonumber)].posted_at = $ts' "$json_path" > "$tmp_file"; then
    echo "Error updating JSON file" >&2
    return 1
  fi
  mv "$tmp_file" "$json_path"
}

# Validate arguments
if [ $# -eq 0 ]; then
  show_usage
fi

JSON_PATH="$1"

# Validate JSON file exists
if [ ! -f "$JSON_PATH" ]; then
  echo "Error: JSON file not found: $JSON_PATH" >&2
  exit 1
fi

# Validate JSON is readable and well-formed
if ! jq empty "$JSON_PATH" 2>/dev/null; then
  echo "Error: Invalid JSON file: $JSON_PATH" >&2
  exit 1
fi

# Extract metadata
OWNER=$(jq -r '.metadata.owner // empty' "$JSON_PATH")
REPO=$(jq -r '.metadata.repo // empty' "$JSON_PATH")
PR_NUMBER=$(jq -r '.metadata.pr_number // empty' "$JSON_PATH")

if [ -z "$OWNER" ] || [ -z "$REPO" ] || [ -z "$PR_NUMBER" ]; then
  echo "Error: Missing metadata in JSON file (owner, repo, or pr_number)" >&2
  exit 1
fi

echo "Processing reviews for $OWNER/$REPO#$PR_NUMBER" >&2

# Categories to process
CATEGORIES=("human" "qodo" "coderabbit")

# Get total thread count across all categories
TOTAL_THREAD_COUNT=$(jq '(.human | length) + (.qodo | length) + (.coderabbit | length)' "$JSON_PATH")

if [ "$TOTAL_THREAD_COUNT" -eq 0 ]; then
  echo "No threads to process" >&2
  exit 0
fi

# Counters for summary
addressed_count=0
skipped_count=0
pending_count=0
failed_count=0
no_thread_id_count=0
replied_not_resolved_count=0

# Process threads from each category
for category in "${CATEGORIES[@]}"; do
  THREAD_COUNT=$(jq --arg cat "$category" '.[$cat] | length' "$JSON_PATH")

  if [ "$THREAD_COUNT" -eq 0 ]; then
    continue
  fi

  echo "Processing $THREAD_COUNT thread(s) from category: $category" >&2

  for ((i = 0; i < THREAD_COUNT; i++)); do
    # Read thread data from the specific category
    thread_data=$(jq -c --arg cat "$category" '.[$cat]['"$i"']' "$JSON_PATH")

    thread_id=$(echo "$thread_data" | jq -r '.thread_id // empty')
    node_id=$(echo "$thread_data" | jq -r '.node_id // empty')
    status=$(echo "$thread_data" | jq -r '.status // "pending"')
    reply=$(echo "$thread_data" | jq -r '.reply // empty')
    skip_reason=$(echo "$thread_data" | jq -r '.skip_reason // empty')
    posted_at=$(echo "$thread_data" | jq -r '.posted_at // empty')
    comment_id=$(echo "$thread_data" | jq -r '.comment_id // empty')
    path=$(echo "$thread_data" | jq -r '.path // "unknown"')

    # Skip if already posted
    if [ -n "$posted_at" ]; then
      echo "Skipping ${category}[${i}] ($path): already posted at $posted_at" >&2
      continue
    fi

    # Skip pending threads
    if [ "$status" = "pending" ]; then
      echo "Skipping ${category}[${i}] ($path): status is pending" >&2
      pending_count=$((pending_count + 1))
      continue
    fi

    # Determine which ID to use for GraphQL
    # NOTE: Only thread_id (from GraphQL) is valid for mutations.
    # node_id from REST API is NOT a valid thread ID and will cause GraphQL errors.
    effective_thread_id=""
    if [ -n "$thread_id" ] && [ "$thread_id" != "null" ]; then
      effective_thread_id="$thread_id"
    fi

    # Check if we have a usable thread ID
    if [ -z "$effective_thread_id" ]; then
      # node_id is NOT usable - it's a comment ID, not a thread ID
      if [ -n "$node_id" ] && [ "$node_id" != "null" ]; then
        echo "Warning: ${category}[${i}] ($path, comment_id=$comment_id) has node_id but no thread_id - node_id is not valid for GraphQL mutations, cannot post reply" >&2
      else
        echo "Warning: No thread_id for ${category}[${i}] ($path, comment_id=$comment_id) - cannot post reply" >&2
      fi
      no_thread_id_count=$((no_thread_id_count + 1))
      continue
    fi

    # Build reply message based on status
    reply_message=""
    case "$status" in
      addressed)
        if [ -n "$reply" ]; then
          reply_message="$reply"
        else
          reply_message="Addressed."
        fi
        ;;
      skipped)
        if [ -n "$skip_reason" ]; then
          reply_message="Skipped: $skip_reason"
        elif [ -n "$reply" ]; then
          reply_message="$reply"
        else
          reply_message="Skipped."
        fi
        ;;
      not_addressed)
        # Handle not_addressed status - post reply and resolve (similar to addressed)
        if [ -n "$reply" ]; then
          reply_message="$reply"
        else
          reply_message="Not addressed - see reply for details."
        fi
        ;;
      failed)
        # Retry with the same reply
        if [ -n "$reply" ]; then
          reply_message="$reply"
        else
          reply_message="Addressed."
        fi
        ;;
      *)
        echo "Warning: Unknown status '$status' for ${category}[${i}] ($path), skipping" >&2
        continue
        ;;
    esac

    echo "Processing ${category}[${i}] ($path): status=$status" >&2

    # Post reply
    if ! post_thread_reply "$effective_thread_id" "$reply_message"; then
      echo "Failed to post reply for ${category}[${i}] ($path)" >&2
      failed_count=$((failed_count + 1))
      continue
    fi

    # Determine if we should resolve this thread
    # - For qodo/coderabbit: always resolve
    # - For human: only resolve if status is "addressed"
    should_resolve=true
    if [ "$category" = "human" ] && [ "$status" != "addressed" ]; then
      should_resolve=false
      echo "Skipping resolution for human review ${category}[${i}] (status: $status) - allows reviewer to follow up" >&2
    fi

    # Resolve thread only if appropriate
    if [ "$should_resolve" = true ]; then
      if ! resolve_thread "$effective_thread_id"; then
        echo "Failed to resolve ${category}[${i}] ($path) - reply was posted but thread not resolved" >&2
        failed_count=$((failed_count + 1))
        continue
      fi
    fi

    # Update JSON with timestamp (now includes category)
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    if ! update_json_with_timestamp "$JSON_PATH" "$category" "$i" "$timestamp"; then
      echo "Warning: Failed to update JSON with timestamp for ${category}[${i}]" >&2
    fi

    # Update counters
    if [ "$should_resolve" = true ]; then
      case "$status" in
        addressed)
          addressed_count=$((addressed_count + 1))
          ;;
        skipped)
          skipped_count=$((skipped_count + 1))
          ;;
        not_addressed)
          # Count as addressed since we resolved the thread
          addressed_count=$((addressed_count + 1))
          ;;
        failed)
          # Successfully retried a previously failed thread
          addressed_count=$((addressed_count + 1))
          ;;
      esac
      echo "Resolved ${category}[${i}] ($path)" >&2
    else
      replied_not_resolved_count=$((replied_not_resolved_count + 1))
      echo "Replied to ${category}[${i}] ($path) (not resolved)" >&2
    fi
  done
done

# Print summary
total_resolved=$((addressed_count + skipped_count))
total_processed=$((total_resolved + replied_not_resolved_count))
echo "" >&2
echo "=== Summary ===" >&2
echo "Processed $total_processed threads" >&2
echo "  Resolved: $total_resolved ($addressed_count addressed, $skipped_count skipped)" >&2

if [ "$replied_not_resolved_count" -gt 0 ]; then
  echo "  Replied only: $replied_not_resolved_count (human reviews - awaiting reviewer follow-up)" >&2
fi

if [ "$pending_count" -gt 0 ]; then
  echo "  Pending: $pending_count threads (not processed yet)" >&2
fi

if [ "$no_thread_id_count" -gt 0 ]; then
  echo "  Skipped: $no_thread_id_count threads (no thread_id - likely fetched via REST API without GraphQL thread ID)" >&2
fi

if [ "$failed_count" -gt 0 ]; then
  echo "Failed: $failed_count threads" >&2
  exit 1
fi

exit 0
