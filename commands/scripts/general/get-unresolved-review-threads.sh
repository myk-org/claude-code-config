#!/usr/bin/env bash
set -euo pipefail

# Generic script to fetch ALL unresolved review threads from a PR
# Returns raw thread data for handlers to filter and parse
#
# Usage: get-unresolved-review-threads.sh <pr-info-script-path> [review_url]
#
# Input:
#   $1 - Path to PR info script (required) - must output "owner/repo pr_number"
#   $2 - Optional: specific review URL (e.g., #pullrequestreview-XXX or #discussion_rXXX)
#
# Output: JSON to stdout with metadata and unresolved threads

# Check required dependencies
for cmd in gh jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Error: '$cmd' is required but not installed." >&2; exit 1; }
done

show_usage() {
  echo "Usage: $0 <pr-info-script-path> [review_url]" >&2
  echo "" >&2
  echo "Fetches ALL unresolved review threads from a PR." >&2
  echo "" >&2
  echo "Arguments:" >&2
  echo "  pr-info-script-path  Path to script that outputs 'owner/repo pr_number'" >&2
  echo "  review_url           Optional: specific review URL fragment" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  $0 /path/to/get-pr-info.sh" >&2
  echo "  $0 /path/to/get-pr-info.sh https://github.com/org/repo/pull/123#pullrequestreview-456" >&2
  echo "  $0 /path/to/get-pr-info.sh https://github.com/org/repo/pull/123#discussion_r789" >&2
  exit 1
}

# Fetch all unresolved review threads using paginated GraphQL
# Returns JSON array of unresolved threads with first comment details
fetch_unresolved_threads() {
  local owner="$1"
  local repo="$2"
  local pr_number="$3"

  local all_threads='[]'
  local cursor=""
  local has_next_page="true"
  local page_count=0

  while [ "$has_next_page" = "true" ]; do
    page_count=$((page_count + 1))
    local raw_result

    if [ -z "$cursor" ]; then
      # First query - no cursor
      if ! raw_result=$(gh api graphql -f query='
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
                  comments(first: 1) {
                    nodes {
                      databaseId
                      author { login }
                      path
                      line
                      body
                    }
                  }
                }
              }
            }
          }
        }
      ' -f owner="$owner" -f repo="$repo" -F pr="$pr_number" 2>&1); then
        echo "Warning: Could not fetch unresolved threads: $raw_result" >&2
        echo "[]"
        return 0
      fi
    else
      # Subsequent queries - with cursor
      if ! raw_result=$(gh api graphql -f query='
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
                  comments(first: 1) {
                    nodes {
                      databaseId
                      author { login }
                      path
                      line
                      body
                    }
                  }
                }
              }
            }
          }
        }
      ' -f owner="$owner" -f repo="$repo" -F pr="$pr_number" -f cursor="$cursor" 2>&1); then
        echo "Warning: Could not fetch unresolved threads (page $page_count): $raw_result" >&2
        break
      fi
    fi

    # Extract pagination info
    has_next_page=$(echo "$raw_result" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage // false')
    cursor=$(echo "$raw_result" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // ""')

    # Extract threads from this page and accumulate
    local page_threads
    page_threads=$(echo "$raw_result" | jq '.data.repository.pullRequest.reviewThreads.nodes // []')
    all_threads=$(jq -n --argjson existing "$all_threads" --argjson new "$page_threads" '$existing + $new')

    if [ "$has_next_page" = "true" ]; then
      echo "Fetching page $((page_count + 1)) of review threads..." >&2
    fi
  done

  if [ "$page_count" -gt 1 ]; then
    echo "Fetched $page_count pages of review threads" >&2
  fi

  # Filter unresolved threads and extract first comment details
  local result
  result=$(echo "$all_threads" | jq '
    [.[] |
     select(.isResolved == false) |
     . as $thread |
     .comments.nodes[0] as $comment |
     {
       thread_id: $thread.id,
       comment_id: ($comment.databaseId // null),
       author: ($comment.author.login // null),
       path: ($comment.path // null),
       line: ($comment.line // null),
       body: ($comment.body // "")
     }]
  ')
  echo "$result"
}

# Fetch a specific review thread by discussion ID
fetch_specific_discussion() {
  local owner="$1"
  local repo="$2"
  local pr_number="$3"
  local discussion_id="$4"

  # Discussion IDs map to review thread comments
  # We need to fetch the thread containing this comment
  local result
  if ! result=$(gh api "/repos/$owner/$repo/pulls/$pr_number/comments/$discussion_id" 2>&1); then
    echo "Warning: Could not fetch discussion $discussion_id: $result" >&2
    echo "[]"
    return 0
  fi

  # Transform to thread format
  echo "$result" | jq '[{
    thread_id: null,
    node_id: .node_id,
    comment_id: .id,
    author: .user.login,
    path: .path,
    line: .line,
    body: .body
  }]'
}

# Fetch inline comments from a specific PR review
fetch_review_comments() {
  local owner="$1"
  local repo="$2"
  local pr_number="$3"
  local review_id="$4"

  local result
  if ! result=$(gh api "/repos/$owner/$repo/pulls/$pr_number/reviews/$review_id/comments?per_page=100" 2>&1); then
    echo "Warning: Could not fetch review $review_id comments: $result" >&2
    echo "[]"
    return 0
  fi

  # Transform to thread format
  # NOTE: REST API returns user.login with [bot] suffix for bot accounts
  echo "$result" | jq '[.[] | {
    thread_id: null,
    node_id: .node_id,
    comment_id: .id,
    author: .user.login,
    path: .path,
    line: .line,
    body: .body
  }]'
}

# Validate arguments
if [ $# -eq 0 ]; then
  show_usage
fi

PR_INFO_SCRIPT="$1"
REVIEW_URL="${2:-}"

# Validate PR info script exists
if [ ! -f "$PR_INFO_SCRIPT" ]; then
  echo "Error: PR info script not found: $PR_INFO_SCRIPT" >&2
  exit 1
fi

# Execute PR info script to get repo and PR number
if ! PR_INFO=$("$PR_INFO_SCRIPT" 2>&1); then
  echo "Error: Failed to get PR information: $PR_INFO" >&2
  exit 1
fi

# Parse PR info output
read -r REPO_FULL_NAME PR_NUMBER _rest <<<"$PR_INFO"

if [ -z "${REPO_FULL_NAME:-}" ] || [ -z "${PR_NUMBER:-}" ]; then
  echo "Error: Invalid PR info output: '$PR_INFO'" >&2
  echo "Expected format: 'owner/repo pr_number'" >&2
  exit 1
fi

if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  echo "Error: PR number must be numeric, got: '$PR_NUMBER'" >&2
  exit 1
fi

# Parse owner and repo from full name
OWNER=$(echo "$REPO_FULL_NAME" | cut -d'/' -f1)
REPO=$(echo "$REPO_FULL_NAME" | cut -d'/' -f2)

if [ -z "$OWNER" ] || [ -z "$REPO" ]; then
  echo "Error: Could not parse owner/repo from: '$REPO_FULL_NAME'" >&2
  exit 1
fi

echo "Repository: $OWNER/$REPO, PR: $PR_NUMBER" >&2

# Initialize threads array
ALL_THREADS='[]'
SPECIFIC_THREADS='[]'

# Fetch all unresolved threads
echo "Fetching unresolved review threads..." >&2
ALL_THREADS=$(fetch_unresolved_threads "$OWNER" "$REPO" "$PR_NUMBER")
THREAD_COUNT=$(echo "$ALL_THREADS" | jq '. | length')
echo "Found $THREAD_COUNT unresolved thread(s)" >&2

# If review URL provided, also fetch specific thread(s)
if [ -n "$REVIEW_URL" ]; then
  if [[ "$REVIEW_URL" =~ pullrequestreview-([0-9]+) ]]; then
    REVIEW_ID="${BASH_REMATCH[1]}"
    echo "Fetching comments from PR review $REVIEW_ID..." >&2
    SPECIFIC_THREADS=$(fetch_review_comments "$OWNER" "$REPO" "$PR_NUMBER" "$REVIEW_ID")
    SPECIFIC_COUNT=$(echo "$SPECIFIC_THREADS" | jq '. | length')
    echo "Found $SPECIFIC_COUNT comment(s) from review $REVIEW_ID" >&2

  elif [[ "$REVIEW_URL" =~ discussion_r([0-9]+) ]]; then
    DISCUSSION_ID="${BASH_REMATCH[1]}"
    echo "Fetching discussion $DISCUSSION_ID..." >&2
    SPECIFIC_THREADS=$(fetch_specific_discussion "$OWNER" "$REPO" "$PR_NUMBER" "$DISCUSSION_ID")
    SPECIFIC_COUNT=$(echo "$SPECIFIC_THREADS" | jq '. | length')
    echo "Found $SPECIFIC_COUNT comment(s) from discussion $DISCUSSION_ID" >&2

  elif [[ "$REVIEW_URL" =~ issuecomment-([0-9]+) ]]; then
    # Issue comments are not review threads, skip silently
    echo "Note: Issue comments (#issuecomment-*) are not review threads, skipping specific fetch" >&2

  else
    echo "Warning: Unrecognized URL fragment in: $REVIEW_URL" >&2
  fi
fi

# Merge specific threads with all threads, deduplicating by comment_id
if [ "$(echo "$SPECIFIC_THREADS" | jq '. | length')" -gt 0 ]; then
  # Merge and deduplicate: keep all from ALL_THREADS, add from SPECIFIC_THREADS if not already present
  MERGED_THREADS=$(jq -n \
    --argjson all "$ALL_THREADS" \
    --argjson specific "$SPECIFIC_THREADS" '
    ($all | map(.comment_id) | map(select(. != null))) as $existing_ids |
    $all + [$specific[] | select(.comment_id as $id | ($existing_ids | index($id)) == null)]
  ')
  ALL_THREADS="$MERGED_THREADS"
fi

# Build final JSON output
jq -n \
  --arg owner "$OWNER" \
  --arg repo "$REPO" \
  --arg pr_number "$PR_NUMBER" \
  --argjson threads "$ALL_THREADS" '
{
  "metadata": {
    "owner": $owner,
    "repo": $repo,
    "pr_number": $pr_number
  },
  "threads": $threads
}
'
