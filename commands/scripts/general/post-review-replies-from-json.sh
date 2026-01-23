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

# Process a single thread (called as background job)
# Args: category, index, thread_data_json, results_dir
# Writes result to results_dir/<category>_<index>.json
process_thread() {
  local category="$1"
  local index="$2"
  local thread_data="$3"
  local results_dir="$4"

  local result_file="${results_dir}/${category}_${index}.json"

  local thread_id node_id status reply skip_reason posted_at comment_id path
  thread_id=$(echo "$thread_data" | jq -r '.thread_id // empty')
  node_id=$(echo "$thread_data" | jq -r '.node_id // empty')
  status=$(echo "$thread_data" | jq -r '.status // "pending"')
  reply=$(echo "$thread_data" | jq -r '.reply // empty')
  skip_reason=$(echo "$thread_data" | jq -r '.skip_reason // empty')
  posted_at=$(echo "$thread_data" | jq -r '.posted_at // empty')
  comment_id=$(echo "$thread_data" | jq -r '.comment_id // empty')
  path=$(echo "$thread_data" | jq -r '.path // "unknown"')

  # Helper to write result
  write_result() {
    local result_type="$1"
    local message="$2"
    local timestamp="${3:-}"
    local resolved="${4:-false}"
    jq -n \
      --arg cat "$category" \
      --arg idx "$index" \
      --arg type "$result_type" \
      --arg msg "$message" \
      --arg ts "$timestamp" \
      --arg path "$path" \
      --arg status "$status" \
      --argjson resolved "$resolved" \
      '{category: $cat, index: ($idx | tonumber), result: $type, message: $msg, timestamp: $ts, path: $path, status: $status, resolved: $resolved}' \
      > "$result_file"
  }

  # Skip if already posted
  if [ -n "$posted_at" ]; then
    write_result "already_posted" "already posted at $posted_at"
    return 0
  fi

  # Skip pending threads
  if [ "$status" = "pending" ]; then
    write_result "pending" "status is pending"
    return 0
  fi

  # Determine which ID to use for GraphQL
  local effective_thread_id=""
  if [ -n "$thread_id" ] && [ "$thread_id" != "null" ]; then
    effective_thread_id="$thread_id"
  fi

  # Check if we have a usable thread ID
  if [ -z "$effective_thread_id" ]; then
    if [ -n "$node_id" ] && [ "$node_id" != "null" ]; then
      write_result "no_thread_id" "has node_id but no thread_id - node_id is not valid for GraphQL mutations"
    else
      write_result "no_thread_id" "no thread_id - cannot post reply (comment_id=$comment_id)"
    fi
    return 0
  fi

  # Build reply message based on status
  local reply_message=""
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
      write_result "unknown_status" "unknown status: $status"
      return 0
      ;;
  esac

  # Post reply
  if ! post_thread_reply "$effective_thread_id" "$reply_message" 2>/dev/null; then
    write_result "failed" "failed to post reply"
    return 0
  fi

  # Determine if we should resolve this thread
  local should_resolve=true
  if [ "$category" = "human" ] && [ "$status" != "addressed" ]; then
    should_resolve=false
  fi

  local timestamp
  timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  # Resolve thread only if appropriate
  if [ "$should_resolve" = true ]; then
    if ! resolve_thread "$effective_thread_id" 2>/dev/null; then
      write_result "resolve_failed" "reply posted but thread not resolved" "$timestamp" false
      return 0
    fi
    write_result "success" "resolved" "$timestamp" true
  else
    write_result "success" "replied only (human review - not resolved)" "$timestamp" false
  fi

  return 0
}

# Export functions for subshells
export -f post_thread_reply resolve_thread process_thread

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

# Create temp directory for results
RESULTS_DIR=$(mktemp -d)
trap 'rm -rf "$RESULTS_DIR"' EXIT

# Maximum parallel jobs (don't overwhelm GitHub API)
MAX_PARALLEL=5
job_count=0

echo "Processing $TOTAL_THREAD_COUNT threads with up to $MAX_PARALLEL parallel requests..." >&2

# Collect all threads to process
declare -a all_threads=()

for category in "${CATEGORIES[@]}"; do
  THREAD_COUNT=$(jq --arg cat "$category" '.[$cat] | length' "$JSON_PATH")

  if [ "$THREAD_COUNT" -eq 0 ]; then
    continue
  fi

  for ((i = 0; i < THREAD_COUNT; i++)); do
    thread_data=$(jq -c --arg cat "$category" '.[$cat]['"$i"']' "$JSON_PATH")
    all_threads+=("$category|$i|$thread_data")
  done
done

# Process threads in parallel with controlled concurrency
for thread_info in "${all_threads[@]}"; do
  IFS='|' read -r category index thread_data <<< "$thread_info"

  # Run process_thread in background
  process_thread "$category" "$index" "$thread_data" "$RESULTS_DIR" &
  job_count=$((job_count + 1))

  # Wait if we hit max parallel jobs
  if [ "$job_count" -ge "$MAX_PARALLEL" ]; then
    wait -n 2>/dev/null || true  # Wait for any one job to finish
    job_count=$((job_count - 1))
  fi
done

# Wait for all remaining jobs
wait

# Collect results and update JSON
echo "" >&2
echo "Collecting results..." >&2

# Counters for summary
addressed_count=0
skipped_count=0
pending_count=0
failed_count=0
no_thread_id_count=0
replied_not_resolved_count=0
already_posted_count=0

# Build list of updates (category, index, timestamp)
declare -a updates=()

# Process all result files
for result_file in "$RESULTS_DIR"/*.json; do
  [ -f "$result_file" ] || continue

  result_data=$(cat "$result_file")
  result_type=$(echo "$result_data" | jq -r '.result')
  category=$(echo "$result_data" | jq -r '.category')
  index=$(echo "$result_data" | jq -r '.index')
  message=$(echo "$result_data" | jq -r '.message')
  path=$(echo "$result_data" | jq -r '.path')
  status=$(echo "$result_data" | jq -r '.status')
  timestamp=$(echo "$result_data" | jq -r '.timestamp')
  resolved=$(echo "$result_data" | jq -r '.resolved')

  case "$result_type" in
    success)
      if [ "$resolved" = "true" ]; then
        case "$status" in
          addressed|not_addressed|failed)
            addressed_count=$((addressed_count + 1))
            ;;
          skipped)
            skipped_count=$((skipped_count + 1))
            ;;
        esac
        echo "Resolved ${category}[${index}] ($path)" >&2
      else
        replied_not_resolved_count=$((replied_not_resolved_count + 1))
        echo "Replied to ${category}[${index}] ($path) (not resolved)" >&2
      fi
      # Queue update for JSON
      updates+=("$category|$index|$timestamp")
      ;;
    resolve_failed)
      failed_count=$((failed_count + 1))
      echo "Failed to resolve ${category}[${index}] ($path) - reply was posted but thread not resolved" >&2
      # Still update timestamp since reply was posted
      updates+=("$category|$index|$timestamp")
      ;;
    failed)
      failed_count=$((failed_count + 1))
      echo "Failed to post reply for ${category}[${index}] ($path)" >&2
      ;;
    pending)
      pending_count=$((pending_count + 1))
      echo "Skipping ${category}[${index}] ($path): status is pending" >&2
      ;;
    no_thread_id)
      no_thread_id_count=$((no_thread_id_count + 1))
      echo "Warning: No thread_id for ${category}[${index}] ($path) - $message" >&2
      ;;
    already_posted)
      already_posted_count=$((already_posted_count + 1))
      echo "Skipping ${category}[${index}] ($path): $message" >&2
      ;;
    unknown_status)
      echo "Warning: Unknown status for ${category}[${index}] ($path): $message" >&2
      ;;
  esac
done

# Apply all JSON updates atomically
if [ ${#updates[@]} -gt 0 ]; then
  echo "" >&2
  echo "Updating JSON file with ${#updates[@]} timestamps..." >&2

  # Use mktemp for secure temp file creation
  tmp_json=$(mktemp)
  tmp_json_new=$(mktemp)
  # Add temp files to cleanup on exit/failure
  trap 'rm -rf "$RESULTS_DIR" "$tmp_json" "$tmp_json_new" 2>/dev/null || true' EXIT

  cp "$JSON_PATH" "$tmp_json"

  for update in "${updates[@]}"; do
    IFS='|' read -r category index timestamp <<< "$update"
    if ! jq --arg cat "$category" --arg idx "$index" --arg ts "$timestamp" \
      '.[$cat][($idx | tonumber)].posted_at = $ts' "$tmp_json" > "$tmp_json_new"; then
      echo "Warning: Failed to update JSON for ${category}[${index}]" >&2
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
