#!/usr/bin/env bash
set -euo pipefail

# Script to reply to specific PR review comments in their thread and/or resolve threads
#
# Requirements:
#   - gh CLI tool installed and authenticated
#   - Write access to the target repository
#
# Usage:
#   reply-to-pr-review.sh <owner/repo> <pr_number> <reply_body> --comment-id <id> [--resolve]
#
# Arguments:
#   owner/repo   - Repository in format "owner/repo"
#   pr_number    - Pull request number (numeric)
#   reply_body   - Markdown-formatted reply message (can be empty "" when only resolving)
#   --comment-id - ID of the comment to reply to (required)
#   --resolve    - Resolve the review thread (optional)
#
# Examples:
#   # Post a threaded reply
#   $0 myorg/myrepo 123 'Fixed this issue' --comment-id 1234567890
#
#   # Resolve a thread without posting a reply
#   $0 myorg/myrepo 123 '' --comment-id 1234567890 --resolve
#
#   # Post a reply AND resolve the thread
#   $0 myorg/myrepo 123 'Fixed this issue' --comment-id 1234567890 --resolve

REPO_FULL=""
PR_NUMBER=""
REPLY_BODY=""
COMMENT_ID=""
RESOLVE="false"

# Parse positional arguments
if [ $# -lt 4 ]; then
  echo "Usage: $0 <owner/repo> <pr_number> <reply_body> --comment-id <id> [--resolve]" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  # Post a threaded reply" >&2
  echo "  $0 myorg/myrepo 123 'Fixed this issue' --comment-id 1234567890" >&2
  echo "" >&2
  echo "  # Resolve a thread without posting a reply" >&2
  echo "  $0 myorg/myrepo 123 '' --comment-id 1234567890 --resolve" >&2
  echo "" >&2
  echo "  # Post a reply AND resolve the thread" >&2
  echo "  $0 myorg/myrepo 123 'Fixed this issue' --comment-id 1234567890 --resolve" >&2
  exit 1
fi

REPO_FULL="$1"
PR_NUMBER="$2"
REPLY_BODY="$3"
shift 3

# Parse --comment-id and --resolve arguments
while [ $# -gt 0 ]; do
  case "$1" in
    --comment-id)
      if [ $# -lt 2 ]; then
        echo "❌ Error: --comment-id requires a value" >&2
        exit 1
      fi
      COMMENT_ID="$2"
      shift 2
      ;;
    --resolve)
      RESOLVE="true"
      shift
      ;;
    *)
      echo "❌ Error: Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# Validate required arguments (reply_body can be empty if only resolving)
if [ -z "$REPO_FULL" ] || [ -z "$PR_NUMBER" ]; then
  echo "❌ Error: Missing required arguments" >&2
  exit 1
fi

# Validate that either reply_body is provided or --resolve is set
if [ -z "$REPLY_BODY" ] && [ "$RESOLVE" = "false" ]; then
  echo "❌ Error: Must provide a reply message or use --resolve flag" >&2
  exit 1
fi

# Validate --comment-id is provided
if [ -z "$COMMENT_ID" ]; then
  echo "❌ Error: --comment-id is required" >&2
  echo "" >&2
  echo "Usage: $0 <owner/repo> <pr_number> <reply_body> --comment-id <id> [--resolve]" >&2
  exit 1
fi

# Validate repo format (owner/repo)
if ! [[ "$REPO_FULL" =~ ^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$ ]]; then
  echo "❌ Error: Invalid repo format. Expected 'owner/repo', got: $REPO_FULL" >&2
  exit 1
fi

# Validate PR number is numeric
if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  echo "❌ Error: PR number must be numeric, got: $PR_NUMBER" >&2
  exit 1
fi

# Validate comment ID is numeric
if ! [[ "$COMMENT_ID" =~ ^[0-9]+$ ]]; then
  echo "❌ Error: Comment ID must be numeric, got: $COMMENT_ID" >&2
  exit 1
fi

# Extract owner and repo from REPO_FULL
OWNER="${REPO_FULL%/*}"
REPO="${REPO_FULL#*/}"

# Post threaded reply to specific comment (if reply body provided)
if [ -n "$REPLY_BODY" ]; then
  echo "ℹ️  Posting threaded reply to comment #$COMMENT_ID in PR #$PR_NUMBER"

  if gh api "/repos/$REPO_FULL/pulls/$PR_NUMBER/comments/$COMMENT_ID/replies" \
       -X POST \
       -f body="$REPLY_BODY" > /dev/null; then
    echo "✅ Threaded reply posted successfully to comment #$COMMENT_ID in PR #$PR_NUMBER"
  else
    echo "❌ Failed to post threaded reply" >&2
    exit 1
  fi
fi

# Resolve the thread if --resolve flag is set
if [ "$RESOLVE" = "true" ]; then
  echo "ℹ️  Resolving thread for comment #$COMMENT_ID"

  # Get the thread ID by querying the PR with pagination support
  # We need to handle PRs with >100 review threads
  THREAD_ID=""
  CURSOR="null"
  HAS_NEXT_PAGE="true"

  while [ "$HAS_NEXT_PAGE" = "true" ] && [ -z "$THREAD_ID" ]; do
    RESULT=$(gh api graphql -f query='
      query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
        repository(owner: $owner, name: $repo) {
          pullRequest(number: $pr) {
            reviewThreads(first: 100, after: $cursor) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                id
                comments(first: 100) {
                  nodes {
                    databaseId
                  }
                }
              }
            }
          }
        }
      }
    ' -f owner="$OWNER" -f repo="$REPO" -F pr="$PR_NUMBER" -f cursor="$CURSOR")

    # Extract thread ID if found in this batch
    THREAD_ID=$(echo "$RESULT" | jq -r ".data.repository.pullRequest.reviewThreads.nodes[] | select(any(.comments.nodes[]; .databaseId == $COMMENT_ID)) | .id")

    # Update pagination variables
    HAS_NEXT_PAGE=$(echo "$RESULT" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage')
    CURSOR=$(echo "$RESULT" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor')
  done

  if [ -z "$THREAD_ID" ]; then
    echo "❌ Error: Could not find thread for comment #$COMMENT_ID" >&2
    exit 1
  fi

  echo "  Found thread: $THREAD_ID"

  # Resolve the thread using GraphQL mutation
  if gh api graphql -f query='
    mutation($threadId: ID!) {
      resolveReviewThread(input: {threadId: $threadId}) {
        thread {
          isResolved
        }
      }
    }
  ' -f threadId="$THREAD_ID" > /dev/null; then
    echo "✅ Thread resolved for comment #$COMMENT_ID"
  else
    echo "❌ Failed to resolve thread" >&2
    exit 1
  fi
fi
