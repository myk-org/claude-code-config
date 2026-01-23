#!/usr/bin/env bash
set -euo pipefail

# Restrict temp file permissions
umask 077

# Global temp file tracking for cleanup
TEMP_FILES=()
cleanup() {
  for f in "${TEMP_FILES[@]}"; do
    rm -f "$f" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

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

  # Validate JSON response before parsing
  if ! echo "$result" | jq -e . >/dev/null 2>&1; then
    echo "GraphQL returned non-JSON response: $result" >&2
    return 1
  fi

  # Check for GraphQL errors
  if echo "$result" | jq -e '.errors? | length > 0' >/dev/null 2>&1; then
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

  # Validate JSON response before parsing
  if ! echo "$result" | jq -e . >/dev/null 2>&1; then
    echo "GraphQL returned non-JSON response: $result" >&2
    return 1
  fi

  # Check for GraphQL errors
  if echo "$result" | jq -e '.errors? | length > 0' >/dev/null 2>&1; then
    local error_msg
    error_msg=$(echo "$result" | jq -r '.errors[0].message // "Unknown error"')
    echo "GraphQL error: $error_msg" >&2
    return 1
  fi

  return 0
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

echo "Processing $TOTAL_THREAD_COUNT threads sequentially..." >&2

# Counters for summary
addressed_count=0
skipped_count=0
pending_count=0
failed_count=0
no_thread_id_count=0
replied_not_resolved_count=0
already_posted_count=0

# Track updates to apply to JSON
declare -a updates=()

# Process each category
for category in "${CATEGORIES[@]}"; do
  THREAD_COUNT=$(jq --arg cat "$category" '.[$cat] | length' "$JSON_PATH")

  if [ "$THREAD_COUNT" -eq 0 ]; then
    continue
  fi

  echo "Processing $THREAD_COUNT threads in $category..." >&2

  for ((i = 0; i < THREAD_COUNT; i++)); do
    # Read thread data
    thread_data=$(jq -c --arg cat "$category" '.[$cat]['"$i"']' "$JSON_PATH")

    thread_id=$(echo "$thread_data" | jq -r '.thread_id // empty')
    node_id=$(echo "$thread_data" | jq -r '.node_id // empty')
    status=$(echo "$thread_data" | jq -r '.status // "pending"')
    reply=$(echo "$thread_data" | jq -r '.reply // empty')
    skip_reason=$(echo "$thread_data" | jq -r '.skip_reason // empty')
    posted_at=$(echo "$thread_data" | jq -r '.posted_at // empty')
    resolved_at=$(echo "$thread_data" | jq -r '.resolved_at // empty')
    path=$(echo "$thread_data" | jq -r '.path // "unknown"')

    # Determine if we should resolve this thread (MUST be before resolve_only_retry check)
    should_resolve=true
    if [ "$category" = "human" ] && [ "$status" != "addressed" ]; then
      should_resolve=false
    fi

    # Determine if this is a resolve-only retry (posted but not resolved)
    resolve_only_retry=false
    if [ -n "$posted_at" ] && [ -z "$resolved_at" ]; then
      if [ "$should_resolve" = true ]; then
        resolve_only_retry=true
        echo "Retrying resolve for ${category}[${i}] ($path): posted at $posted_at but not resolved" >&2
      else
        already_posted_count=$((already_posted_count + 1))
        echo "Skipping ${category}[${i}] ($path): reply already posted at $posted_at (not resolving by policy)" >&2
        continue
      fi
    elif [ -n "$posted_at" ]; then
      # Already fully processed (posted and resolved)
      already_posted_count=$((already_posted_count + 1))
      echo "Skipping ${category}[${i}] ($path): already posted at $posted_at" >&2
      continue
    fi

    # Skip pending threads
    if [ "$status" = "pending" ]; then
      pending_count=$((pending_count + 1))
      echo "Skipping ${category}[${i}] ($path): status is pending" >&2
      continue
    fi

    # Determine which ID to use for GraphQL
    effective_thread_id=""
    if [ -n "$thread_id" ] && [ "$thread_id" != "null" ]; then
      effective_thread_id="$thread_id"
    elif [ -n "$node_id" ] && [ "$node_id" != "null" ]; then
      # Try to derive thread_id from the review comment node id
      if ! thread_lookup_result=$(
        gh api graphql -f query='
          query($nodeId: ID!) {
            node(id: $nodeId) {
              ... on PullRequestReviewComment {
                pullRequestReviewThread {
                  id
                }
              }
            }
          }
        ' -f nodeId="$node_id" 2>&1
      ); then
        thread_lookup_result=""
      fi

      if [ -n "$thread_lookup_result" ] \
        && echo "$thread_lookup_result" | jq -e . >/dev/null 2>&1 \
        && ! echo "$thread_lookup_result" | jq -e '.errors? | length > 0' >/dev/null 2>&1; then
        effective_thread_id=$(echo "$thread_lookup_result" | jq -r '.data.node.pullRequestReviewThread.id // empty')
      fi
    fi

    # Check if we have a usable thread ID
    if [ -z "$effective_thread_id" ]; then
      no_thread_id_count=$((no_thread_id_count + 1))
      echo "Warning: No resolvable thread_id for ${category}[${i}] ($path) - cannot post reply" >&2
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
        if [ -n "$reply" ]; then
          reply_message="$reply"
        else
          reply_message="Not addressed - see reply for details."
        fi
        ;;
      failed)
        if [ -n "$reply" ]; then
          reply_message="$reply"
        else
          reply_message="Addressed."
        fi
        ;;
      *)
        echo "Warning: Unknown status for ${category}[${i}] ($path): $status" >&2
        continue
        ;;
    esac

    # Post reply only if not already posted
    if [ "$resolve_only_retry" = false ]; then
      if ! post_thread_reply "$effective_thread_id" "$reply_message"; then
        failed_count=$((failed_count + 1))
        echo "Failed to post reply for ${category}[${i}] ($path)" >&2
        continue
      fi
    fi

    # Resolve thread only if appropriate
    if [ "$should_resolve" = true ]; then
      if ! resolve_thread "$effective_thread_id"; then
        # Record posted_at if we just posted (so next run can retry resolve only)
        if [ "$resolve_only_retry" = false ]; then
          posted_at_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
          updates+=("$category|$i|posted_at|$posted_at_timestamp")
        fi
        failed_count=$((failed_count + 1))
        echo "Failed to resolve ${category}[${i}] ($path) - reply was posted but thread not resolved" >&2
        continue
      fi
      # Record both timestamps after successful resolve
      if [ "$resolve_only_retry" = false ]; then
        posted_at_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        updates+=("$category|$i|posted_at|$posted_at_timestamp")
      fi
      resolved_at_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
      updates+=("$category|$i|resolved_at|$resolved_at_timestamp")
      case "$status" in
        addressed|not_addressed|failed)
          addressed_count=$((addressed_count + 1))
          ;;
        skipped)
          skipped_count=$((skipped_count + 1))
          ;;
      esac
      echo "Resolved ${category}[${i}] ($path)" >&2
    else
      # For threads we don't resolve, record posted_at after successful reply
      if [ "$resolve_only_retry" = false ]; then
        posted_at_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        updates+=("$category|$i|posted_at|$posted_at_timestamp")
      fi
      replied_not_resolved_count=$((replied_not_resolved_count + 1))
      echo "Replied to ${category}[${i}] ($path) (not resolved)" >&2
    fi
  done
done

# Apply all JSON updates atomically
if [ ${#updates[@]} -gt 0 ]; then
  echo "" >&2
  echo "Updating JSON file with ${#updates[@]} timestamps..." >&2

  # Use mktemp for secure temp file creation
  tmp_json=$(mktemp)
  tmp_json_new=$(mktemp)
  TEMP_FILES+=("$tmp_json" "$tmp_json_new")

  cp "$JSON_PATH" "$tmp_json"

  for update in "${updates[@]}"; do
    IFS='|' read -r cat idx field ts <<< "$update"
    if ! jq --arg cat "$cat" --arg idx "$idx" --arg field "$field" --arg ts "$ts" \
      '.[$cat][($idx | tonumber)][$field] = $ts' "$tmp_json" > "$tmp_json_new"; then
      echo "Warning: Failed to update JSON for ${cat}[${idx}].${field}" >&2
      continue
    fi
    mv -f "$tmp_json_new" "$tmp_json"
  done

  mv -f "$tmp_json" "$JSON_PATH"
fi

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

if [ "$already_posted_count" -gt 0 ]; then
  echo "  Already posted: $already_posted_count threads" >&2
fi

if [ "$failed_count" -gt 0 ]; then
  echo "Failed: $failed_count threads" >&2
  exit 1
fi

exit 0
