#!/usr/bin/env bash
set -euo pipefail

# Script to extract human reviewer comments for processing
# Uses the generic unresolved threads fetcher and filters out AI reviewers
#
# Usage: get-human-reviews.sh <owner/repo> <pr_number>
#        get-human-reviews.sh https://github.com/owner/repo/pull/123
#        get-human-reviews.sh <pr_number>

# Path to the generic fetcher script
GENERIC_FETCHER_SCRIPT="$(dirname "$0")/../general/get-unresolved-review-threads.sh"

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
  Fetches human review comments on a PR (excludes AI bots like CodeRabbit and Qodo).

  Output: JSON with metadata, summary, and comments array

  When using just PR number, repo is determined from current git context.

Options:
  -h, --help    Show this help message

EOF
}

# Function to get unresolved human comments using the generic fetcher
get_unresolved_human_comments() {
  local pr_info_script="$1"
  local url="${2:-}"

  # Call generic fetcher
  local all_threads
  if [ -n "$url" ]; then
    all_threads=$("$GENERIC_FETCHER_SCRIPT" "$pr_info_script" "$url")
  else
    all_threads=$("$GENERIC_FETCHER_SCRIPT" "$pr_info_script")
  fi

  # Build jq filter to exclude AI reviewers
  # Filter: author != "qodo-code-review" and author != "coderabbitai"
  local jq_filter='[.threads[] | select(.author != "qodo-code-review" and .author != "coderabbitai" and .author != "qodo-code-review[bot]" and .author != "coderabbitai[bot]")]'

  echo "$all_threads" | jq "$jq_filter"
}

# Check for help flag
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    show_usage
    exit 0
fi

# Validate generic fetcher script exists
if [ ! -f "$GENERIC_FETCHER_SCRIPT" ]; then
  echo "Error: Generic fetcher script not found: $GENERIC_FETCHER_SCRIPT" >&2
  exit 1
fi

# Parse arguments
if [[ $# -eq 2 ]]; then
    # Two args: owner/repo and pr_number
    REPO_FULL_NAME="$1"
    PR_NUMBER="$2"
    REVIEW_URL=""

elif [[ $# -eq 1 ]]; then
    INPUT="$1"
    REVIEW_URL=""

    # Check if it's a GitHub URL
    if [[ "$INPUT" =~ github\.com/([^/]+)/([^/]+)/pull/([0-9]+) ]]; then
        REPO_FULL_NAME="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
        PR_NUMBER="${BASH_REMATCH[3]}"
        # Preserve the full URL for passing to the fetcher (may contain review fragment)
        REVIEW_URL="$INPUT"

    # Check if it's just a number (PR number only - get repo from current git context)
    elif [[ "$INPUT" =~ ^[0-9]+$ ]]; then
        PR_NUMBER="$INPUT"
        REPO_FULL_NAME=$(gh repo view --json owner,name -q '.owner.login + "/" + .name' 2>/dev/null)
        if [[ -z "$REPO_FULL_NAME" ]]; then
            echo "Error: Could not determine repository. Run from a git repo or provide full URL." >&2
            exit 1
        fi

    else
        echo "Error: Invalid input format: $INPUT" >&2
        show_usage >&2
        exit 1
    fi

else
    show_usage >&2
    exit 1
fi

# Validate repository format (owner/repo)
if [[ ! "$REPO_FULL_NAME" =~ ^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$ ]]; then
    echo "Error: Invalid repository format. Expected 'owner/repo', got: $REPO_FULL_NAME" >&2
    exit 1
fi

# Validate PR number is numeric
if [[ ! "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "Error: PR number must be numeric, got: $PR_NUMBER" >&2
    exit 1
fi

OWNER="${REPO_FULL_NAME%%/*}"
REPO="${REPO_FULL_NAME##*/}"

# Create a temporary PR info script for the generic fetcher
# The generic fetcher expects a script that outputs "owner/repo pr_number"
mkdir -p /tmp/claude
TEMP_PR_INFO_SCRIPT=$(mktemp /tmp/claude/pr-info-XXXXXX.sh)
trap 'rm -f "$TEMP_PR_INFO_SCRIPT"' EXIT

cat > "$TEMP_PR_INFO_SCRIPT" <<EOF
#!/bin/bash
echo "$REPO_FULL_NAME $PR_NUMBER"
EOF
chmod +x "$TEMP_PR_INFO_SCRIPT"

# Fetch human comments using the generic fetcher
HUMAN_COMMENTS=$(get_unresolved_human_comments "$TEMP_PR_INFO_SCRIPT" "$REVIEW_URL")

# Count comments
TOTAL_COUNT=$(echo "$HUMAN_COMMENTS" | jq '. | length')

# Transform to expected output format
# Input format from fetcher: {thread_id, comment_id, author, path, line, body}
# Output format: {thread_id, comment_id, reviewer, file, line, body}
FORMATTED_COMMENTS=$(echo "$HUMAN_COMMENTS" | jq '[.[] | {
  thread_id: .thread_id,
  comment_id: .comment_id,
  reviewer: .author,
  file: .path,
  line: .line,
  body: .body
}]')

# Build final JSON output using jq for proper escaping
jq -n \
  --arg owner "$OWNER" \
  --arg repo "$REPO" \
  --argjson pr_number "$PR_NUMBER" \
  --argjson total "$TOTAL_COUNT" \
  --argjson comments "$FORMATTED_COMMENTS" '
{
  "metadata": {
    "owner": $owner,
    "repo": $repo,
    "pr_number": $pr_number
  },
  "summary": {
    "total": $total
  },
  "comments": $comments
}
'
