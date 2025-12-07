#!/usr/bin/env bash
set -euo pipefail

# Check dependencies
for cmd in gh jq; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "❌ Error: Required command '$cmd' is not installed" >&2
        exit 1
    fi
done

# Script: get-pr-diff.sh
# Purpose: Fetch PR diff and metadata needed for code review
# Usage: get-pr-diff.sh <owner/repo> <pr_number>
#        get-pr-diff.sh https://github.com/owner/repo/pull/123
#        get-pr-diff.sh <pr_number>

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
  Fetches PR diff and metadata needed for code review.

  Output: JSON with metadata, diff, and files array

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
        # Get repo from current git context (same approach as get-pr-info.sh)
        REPO_FULL_NAME=$(gh repo view --json owner,name -q '.owner.login + "/" + .name' 2>/dev/null)
        if [[ -z "$REPO_FULL_NAME" ]]; then
            echo "❌ Error: Could not determine repository. Run from a git repo or provide full URL." >&2
            exit 1
        fi

    else
        echo "❌ Error: Invalid input format: $INPUT" >&2
        echo "" >&2
        echo "Expected formats:" >&2
        echo "  $0 <owner/repo> <pr_number>" >&2
        echo "  $0 https://github.com/owner/repo/pull/123" >&2
        echo "  $0 <pr_number>" >&2
        exit 1
    fi

else
    echo "Usage: $0 <owner/repo> <pr_number>" >&2
    echo "       $0 https://github.com/owner/repo/pull/123" >&2
    echo "       $0 <pr_number>" >&2
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

# Extract owner and repo
OWNER="${REPO_FULL_NAME%%/*}"
REPO="${REPO_FULL_NAME##*/}"

# Fetch PR metadata
PR_METADATA=$(gh api "/repos/$OWNER/$REPO/pulls/$PR_NUMBER" 2>&1) || {
    echo "❌ Error: Failed to fetch PR metadata for $REPO_FULL_NAME#$PR_NUMBER" >&2
    echo "$PR_METADATA" >&2
    exit 1
}

# Extract key metadata fields
HEAD_SHA=$(echo "$PR_METADATA" | jq -r '.head.sha')
BASE_REF=$(echo "$PR_METADATA" | jq -r '.base.ref')
PR_TITLE=$(echo "$PR_METADATA" | jq -r '.title')
PR_STATE=$(echo "$PR_METADATA" | jq -r '.state')

if [[ -z "$HEAD_SHA" ]] || [[ "$HEAD_SHA" == "null" ]]; then
    echo "❌ Error: Failed to extract head SHA from PR metadata" >&2
    exit 1
fi

if [[ -z "$BASE_REF" ]] || [[ "$BASE_REF" == "null" ]]; then
    echo "❌ Error: Failed to extract base ref from PR metadata" >&2
    exit 1
fi

# Fetch PR diff
PR_DIFF=$(gh pr diff "$PR_NUMBER" --repo "$REPO_FULL_NAME" 2>&1) || {
    echo "❌ Error: Failed to fetch PR diff for $REPO_FULL_NAME#$PR_NUMBER" >&2
    echo "$PR_DIFF" >&2
    exit 1
}

# Fetch changed files
FILES_DATA=$(gh api "/repos/$OWNER/$REPO/pulls/$PR_NUMBER/files" 2>&1) || {
    echo "❌ Error: Failed to fetch PR files for $REPO_FULL_NAME#$PR_NUMBER" >&2
    echo "$FILES_DATA" >&2
    exit 1
}

# Process files data to extract relevant fields
FILES_ARRAY=$(echo "$FILES_DATA" | jq '[.[] | {path: .filename, status: .status, additions: .additions, deletions: .deletions, patch: (.patch // "")}]')

# Escape diff content for JSON
DIFF_ESCAPED=$(echo "$PR_DIFF" | jq -Rs .)

# Build final JSON output
jq -n \
    --arg owner "$OWNER" \
    --arg repo "$REPO" \
    --arg pr_number "$PR_NUMBER" \
    --arg head_sha "$HEAD_SHA" \
    --arg base_ref "$BASE_REF" \
    --arg pr_title "$PR_TITLE" \
    --arg pr_state "$PR_STATE" \
    --argjson diff "$DIFF_ESCAPED" \
    --argjson files "$FILES_ARRAY" \
    '{
        metadata: {
            owner: $owner,
            repo: $repo,
            pr_number: $pr_number,
            head_sha: $head_sha,
            base_ref: $base_ref,
            title: $pr_title,
            state: $pr_state
        },
        diff: $diff,
        files: $files
    }'
