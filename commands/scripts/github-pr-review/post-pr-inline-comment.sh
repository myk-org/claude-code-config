#!/usr/bin/env bash
set -euo pipefail

# Script to post an inline comment on a PR at a specific file and line
#
# Requirements:
#   - gh CLI tool installed and authenticated
#   - Write access to the target repository
#
# Usage:
#   post-pr-inline-comment.sh <owner/repo> <pr_number> <file_path> <line> <body> <commit_sha>
#
# Arguments:
#   owner/repo  - Repository in format "owner/repo"
#   pr_number   - Pull request number (numeric)
#   file_path   - Path to the file (relative to repo root)
#   line        - Line number in the new version of the file (numeric)
#   body        - Comment body (markdown supported)
#   commit_sha  - The SHA of the commit to comment on (HEAD of PR)
#
# Examples:
#   # Post an inline comment on a specific line
#   $0 myorg/myrepo 123 'src/main.py' 42 'This needs refactoring' abc123def456
#
#   # Post a multi-line comment
#   $0 myorg/myrepo 123 'README.md' 10 'Please update this section' abc123def456

# Check for correct number of arguments
if [ $# -ne 6 ]; then
  echo "Usage: $0 <owner/repo> <pr_number> <file_path> <line> <body> <commit_sha>" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  # Post an inline comment on a specific line" >&2
  echo "  $0 myorg/myrepo 123 'src/main.py' 42 'This needs refactoring' abc123def456" >&2
  echo "" >&2
  echo "  # Post a multi-line comment" >&2
  echo "  $0 myorg/myrepo 123 'README.md' 10 'Please update this section' abc123def456" >&2
  exit 1
fi

REPO_FULL_NAME="$1"
PR_NUMBER="$2"
FILE_PATH="$3"
LINE="$4"
BODY="$5"
COMMIT_SHA="$6"

# Validate required arguments
if [ -z "$REPO_FULL_NAME" ] || [ -z "$PR_NUMBER" ] || [ -z "$FILE_PATH" ] || \
   [ -z "$LINE" ] || [ -z "$BODY" ] || [ -z "$COMMIT_SHA" ]; then
  echo "❌ Error: All arguments are required" >&2
  exit 1
fi

# Validate repo format (owner/repo)
if ! [[ "$REPO_FULL_NAME" =~ ^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$ ]]; then
  echo "❌ Error: Invalid repo format. Expected 'owner/repo', got: $REPO_FULL_NAME" >&2
  exit 1
fi

# Validate PR number is numeric
if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
  echo "❌ Error: PR number must be numeric, got: $PR_NUMBER" >&2
  exit 1
fi

# Validate line number is numeric
if ! [[ "$LINE" =~ ^[0-9]+$ ]]; then
  echo "❌ Error: Line number must be numeric, got: $LINE" >&2
  exit 1
fi

# Post inline comment
echo "ℹ️  Posting inline comment on $FILE_PATH:$LINE in PR #$PR_NUMBER"

if gh api "/repos/$REPO_FULL_NAME/pulls/$PR_NUMBER/comments" \
     -X POST \
     -f body="$BODY" \
     -f path="$FILE_PATH" \
     -F line="$LINE" \
     -f commit_id="$COMMIT_SHA" \
     -f side="RIGHT" > /dev/null; then
  echo "✅ Comment posted successfully on $FILE_PATH:$LINE"
else
  echo "❌ Failed to post inline comment" >&2
  echo "" >&2
  echo "Common issues:" >&2
  echo "  - Line $LINE might not be part of the diff in this PR" >&2
  echo "  - File path '$FILE_PATH' might not exist in commit $COMMIT_SHA" >&2
  echo "  - Commit SHA might not be the HEAD of the PR" >&2
  echo "" >&2
  echo "Tip: Only lines that were modified or added in the PR can receive inline comments" >&2
  exit 1
fi
