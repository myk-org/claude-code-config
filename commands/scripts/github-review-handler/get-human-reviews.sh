#!/bin/bash
set -euo pipefail

# Script to extract human reviewer comments for processing
# Usage: get-human-reviews.sh <owner/repo> <pr_number>
#        get-human-reviews.sh https://github.com/owner/repo/pull/123
#        get-human-reviews.sh <pr_number>

show_usage() {
    cat <<EOF
Usage:
  $0 <owner/repo> <pr_number>
  $0 https://github.com/owner/repo/pull/123
  $0 <pr_number>

Examples:
  $0 myakove/my-repo 123
  $0 https://github.com/myakove/my-repo/pull/123
  $0 194

Description:
  Fetches human review comments on a PR (excludes CodeRabbit bot).

  Output: JSON with metadata, summary, and comments array

  When using just PR number, repo is determined from current git context.

Options:
  -h, --help    Show this help message

EOF
}

# Check for help flag
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    show_usage
    exit 0
fi

# Parse arguments
if [[ $# -eq 2 ]]; then
    # Two args: owner/repo and pr_number
    REPO_FULL_NAME="$1"
    PR_NUMBER="$2"

elif [[ $# -eq 1 ]]; then
    INPUT="$1"

    # Check if it's a GitHub URL
    if [[ "$INPUT" =~ github\.com/([^/]+)/([^/]+)/pull/([0-9]+) ]]; then
        REPO_FULL_NAME="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
        PR_NUMBER="${BASH_REMATCH[3]}"

    # Check if it's just a number (PR number only - get repo from current git context)
    elif [[ "$INPUT" =~ ^[0-9]+$ ]]; then
        PR_NUMBER="$INPUT"
        REPO_FULL_NAME=$(gh repo view --json owner,name -q '.owner.login + "/" + .name' 2>/dev/null)
        if [[ -z "$REPO_FULL_NAME" ]]; then
            echo "❌ Error: Could not determine repository. Run from a git repo or provide full URL." >&2
            exit 1
        fi

    else
        echo "❌ Error: Invalid input format: $INPUT" >&2
        show_usage >&2
        exit 1
    fi

else
    show_usage >&2
    exit 1
fi

# Validate repository format (owner/repo)
if [[ ! "$REPO_FULL_NAME" =~ ^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$ ]]; then
    echo "❌ Error: Invalid repository format. Expected 'owner/repo', got: $REPO_FULL_NAME" >&2
    exit 1
fi

# Validate PR number is numeric
if [[ ! "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "❌ Error: PR number must be numeric, got: $PR_NUMBER" >&2
    exit 1
fi

OWNER="${REPO_FULL_NAME%%/*}"
REPO="${REPO_FULL_NAME##*/}"

# Step 1: Get the latest commit SHA and timestamp
LATEST_COMMIT_SHA=$(gh api "/repos/$OWNER/$REPO/pulls/$PR_NUMBER" --jq '.head.sha')

if [ -z "$LATEST_COMMIT_SHA" ]; then
  echo "❌ Error: Could not retrieve latest commit SHA" >&2
  exit 1
fi

# Get the latest commit timestamp
LATEST_COMMIT_DATE=$(gh api "/repos/$OWNER/$REPO/commits/$LATEST_COMMIT_SHA" --jq '.commit.committer.date')

if [ -z "$LATEST_COMMIT_DATE" ]; then
  echo "❌ Error: Could not retrieve latest commit date" >&2
  exit 1
fi

# Step 2: Get all reviews submitted after the latest commit, excluding CodeRabbit
HUMAN_REVIEWS=$(gh api "/repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" |
  jq --arg bot_user "coderabbitai[bot]" --arg latest_date "$LATEST_COMMIT_DATE" \
    '[.[] | select(.user.login != $bot_user and (.body | length) > 10 and .submitted_at > $latest_date)] | sort_by(.submitted_at)')

# Step 3: Get all review comments from human reviewers
ALL_COMMENTS='[]'

for review_id in $(echo "$HUMAN_REVIEWS" | jq -r '.[].id'); do
  REVIEWER=$(echo "$HUMAN_REVIEWS" | jq -r --arg id "$review_id" '.[] | select(.id == ($id | tonumber)) | .user.login')

  # Get inline comments for this review
  REVIEW_COMMENTS=$(gh api "/repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews/$review_id/comments" |
    jq --arg reviewer "$REVIEWER" '[.[] |
      {
        comment_id: .id,
        reviewer: $reviewer,
        file: .path,
        line: (.line // .original_line // ""),
        body: .body
      }
    ]')

  # Merge with all comments
  ALL_COMMENTS=$(echo "$ALL_COMMENTS $REVIEW_COMMENTS" | jq -s 'add')
done

# Step 4: Get PR review comments (not inline review comments) created after the latest commit
PR_COMMENTS=$(gh api "/repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments" |
  jq --arg bot_user "coderabbitai[bot]" --arg latest_date "$LATEST_COMMIT_DATE" '[.[] |
    select(.user.login != $bot_user and (.body | length) > 10 and .created_at > $latest_date) |
    {
      comment_id: .id,
      reviewer: .user.login,
      file: .path,
      line: (.line // .original_line // ""),
      body: .body
    }
  ]')

# Merge PR review comments with review-specific comments
ALL_COMMENTS=$(echo "$ALL_COMMENTS $PR_COMMENTS" | jq -s 'add')

# Note: We only include review comments (with file/line info) submitted after the latest commit, not general PR conversation comments
# This ensures we only get human feedback that came after the latest changes

# Count comments
TOTAL_COUNT=$(echo "$ALL_COMMENTS" | jq '. | length')

# Build final JSON
JSON_OUTPUT="{"
JSON_OUTPUT="$JSON_OUTPUT\"metadata\": {"
JSON_OUTPUT="$JSON_OUTPUT\"owner\": \"$OWNER\","
JSON_OUTPUT="$JSON_OUTPUT\"repo\": \"$REPO\","
JSON_OUTPUT="$JSON_OUTPUT\"pr_number\": $PR_NUMBER"
JSON_OUTPUT="$JSON_OUTPUT},"
JSON_OUTPUT="$JSON_OUTPUT\"summary\": {"
JSON_OUTPUT="$JSON_OUTPUT\"total\": $TOTAL_COUNT"
JSON_OUTPUT="$JSON_OUTPUT},"
JSON_OUTPUT="$JSON_OUTPUT\"comments\": $ALL_COMMENTS"
JSON_OUTPUT="$JSON_OUTPUT}"

echo "$JSON_OUTPUT" | jq '.'
