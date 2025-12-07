#!/usr/bin/env bash
set -euo pipefail

# Script to post inline comments on a PR as a single GitHub review with summary
#
# This script posts a GitHub review with:
#   1. A summary body that categorizes findings by severity (CRITICAL, WARNING, SUGGESTION)
#   2. Inline comments on specific lines of code
#
# The review body is auto-generated from the comment bodies by parsing severity markers.
#
# Requirements:
#   - gh CLI tool installed and authenticated
#   - jq for JSON processing
#   - Write access to the target repository
#
# Usage:
#   # New format: Post multiple comments as a single review
#   post-pr-inline-comment.sh <owner/repo> <pr_number> <commit_sha> <json_file>
#   post-pr-inline-comment.sh <owner/repo> <pr_number> <commit_sha> -  # Read from stdin
#
#   # Legacy format: Post a single comment (backward compatibility)
#   post-pr-inline-comment.sh <owner/repo> <pr_number> <file_path> <line> <body> <commit_sha>
#
# Arguments:
#   owner/repo  - Repository in format "owner/repo"
#   pr_number   - Pull request number (numeric)
#   commit_sha  - The SHA of the commit to comment on (HEAD of PR)
#   json_file   - Path to JSON file with comments array, or "-" for stdin
#
# JSON Input Format (array of comments):
#   [
#     {
#       "path": "src/main.py",
#       "line": 42,
#       "body": "### [CRITICAL] SQL Injection\n\nDescription here..."
#     },
#     {
#       "path": "src/utils.py",
#       "line": 15,
#       "body": "### [WARNING] Missing error handling\n\nDescription here..."
#     }
#   ]
#
# Severity Markers:
#   Comment bodies can start with severity markers to categorize findings:
#   - ### [CRITICAL] Title - For critical security/functionality issues
#   - ### [WARNING] Title  - For important but non-critical issues
#   - ### [SUGGESTION] Title - For code improvements and suggestions
#   If no severity marker is present, the comment is categorized as SUGGESTION.
#
# Examples:
#   # Post multiple comments from a JSON file
#   $0 myorg/myrepo 123 abc123def456 comments.json
#
#   # Post multiple comments from stdin
#   echo '[{"path":"src/main.py","line":42,"body":"Fix this"}]' | $0 myorg/myrepo 123 abc123def456 -
#
#   # Legacy: Post a single inline comment
#   $0 myorg/myrepo 123 'src/main.py' 42 'This needs refactoring' abc123def456

# Check for jq
if ! command -v jq &>/dev/null; then
  echo "❌ Error: jq is required but not installed" >&2
  exit 1
fi

# Determine format based on argument count
if [ $# -eq 4 ]; then
  # New format: <owner/repo> <pr_number> <commit_sha> <json_file>
  REPO_FULL_NAME="$1"
  PR_NUMBER="$2"
  COMMIT_SHA="$3"
  JSON_SOURCE="$4"
  LEGACY_MODE=false
elif [ $# -eq 6 ]; then
  # Legacy format: <owner/repo> <pr_number> <file_path> <line> <body> <commit_sha>
  REPO_FULL_NAME="$1"
  PR_NUMBER="$2"
  FILE_PATH="$3"
  LINE="$4"
  BODY="$5"
  COMMIT_SHA="$6"
  LEGACY_MODE=true
else
  echo "Usage:" >&2
  echo "  # Post multiple comments as a single review" >&2
  echo "  $0 <owner/repo> <pr_number> <commit_sha> <json_file>" >&2
  echo "  $0 <owner/repo> <pr_number> <commit_sha> -  # Read from stdin" >&2
  echo "" >&2
  echo "  # Legacy: Post a single comment" >&2
  echo "  $0 <owner/repo> <pr_number> <file_path> <line> <body> <commit_sha>" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  # Post multiple comments from JSON file" >&2
  echo "  $0 myorg/myrepo 123 abc123def456 comments.json" >&2
  echo "" >&2
  echo "  # Post multiple comments from stdin" >&2
  echo "  echo '[{\"path\":\"src/main.py\",\"line\":42,\"body\":\"Fix this\"}]' | $0 myorg/myrepo 123 abc123def456 -" >&2
  exit 1
fi

# Validate required arguments
if [ -z "$REPO_FULL_NAME" ] || [ -z "$PR_NUMBER" ] || [ -z "$COMMIT_SHA" ]; then
  echo "❌ Error: owner/repo, pr_number, and commit_sha are required" >&2
  exit 1
fi

# Additional validation for legacy mode
if [ "$LEGACY_MODE" = true ]; then
  if [ -z "$FILE_PATH" ] || [ -z "$LINE" ] || [ -z "$BODY" ]; then
    echo "❌ Error: In legacy mode, file_path, line, and body are required" >&2
    exit 1
  fi
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

# Handle legacy mode (single comment)
if [ "$LEGACY_MODE" = true ]; then
  # Validate line number is numeric
  if ! [[ "$LINE" =~ ^[0-9]+$ ]]; then
    echo "❌ Error: Line number must be numeric, got: $LINE" >&2
    exit 1
  fi

  echo "ℹ️  Converting legacy single comment to review format"

  # Create JSON array with single comment
  COMMENTS_JSON=$(jq -n \
    --arg path "$FILE_PATH" \
    --argjson line "$LINE" \
    --arg body "$BODY" \
    '[{path: $path, line: $line, body: $body}]')
else
  # New mode: Read JSON from file or stdin
  if [ "$JSON_SOURCE" = "-" ]; then
    echo "ℹ️  Reading comments from stdin"
    COMMENTS_JSON=$(cat)
  else
    if [ ! -f "$JSON_SOURCE" ]; then
      echo "❌ Error: JSON file not found: $JSON_SOURCE" >&2
      exit 1
    fi
    echo "ℹ️  Reading comments from file: $JSON_SOURCE"
    COMMENTS_JSON=$(cat "$JSON_SOURCE")
  fi

  # Sanitize JSON - remove any lines before the JSON array starts
  # This handles cases where "STDIN" or other text gets prepended by hooks/shell
  COMMENTS_JSON=$(echo "$COMMENTS_JSON" | sed -n '/^\[/,$p')

  # Validate JSON format
  if ! echo "$COMMENTS_JSON" | jq -e 'if type == "array" then true else false end' &>/dev/null; then
    echo "❌ Error: JSON input must be an array of comments" >&2
    exit 1
  fi

  # Validate required fields in each comment
  if ! echo "$COMMENTS_JSON" | jq -e 'all(.[]; has("path") and has("line") and has("body"))' &>/dev/null; then
    echo "❌ Error: Each comment must have 'path', 'line', and 'body' fields" >&2
    exit 1
  fi
fi

# Count comments
COMMENT_COUNT=$(echo "$COMMENTS_JSON" | jq 'length')
echo "ℹ️  Posting review with $COMMENT_COUNT comment(s) on PR #$PR_NUMBER"

# Function to extract severity from comment body
# Looks for pattern: ### [SEVERITY] Title
extract_severity() {
  local body="$1"
  if echo "$body" | grep -qE '^### \[(CRITICAL|WARNING|SUGGESTION)\]'; then
    echo "$body" | grep -oE '^### \[(CRITICAL|WARNING|SUGGESTION)\]' | grep -oE '(CRITICAL|WARNING|SUGGESTION)'
  else
    echo "SUGGESTION"  # Default severity
  fi
}

# Function to extract title from comment body
# Gets text after ### [SEVERITY]
extract_title() {
  local body="$1"
  # Get first line and extract title
  local first_line=$(echo "$body" | head -n1)
  if echo "$first_line" | grep -qE '^### \[(CRITICAL|WARNING|SUGGESTION)\]'; then
    # Use sed with extended regex to remove severity marker
    echo "$first_line" | sed -E 's/^### \[(CRITICAL|WARNING|SUGGESTION)\] *//'
  else
    # No severity marker, use first line as title
    echo "$first_line" | sed 's/^### *//' | cut -c1-80
  fi
}

# Generate review body with summary
echo "ℹ️  Generating review summary..."

# Initialize severity counters
CRITICAL_COUNT=0
WARNING_COUNT=0
SUGGESTION_COUNT=0

# Arrays to store comments by severity
CRITICAL_ITEMS=""
WARNING_ITEMS=""
SUGGESTION_ITEMS=""

# Process each comment
while IFS= read -r comment; do
  path=$(echo "$comment" | jq -r '.path')
  line=$(echo "$comment" | jq -r '.line')
  body=$(echo "$comment" | jq -r '.body')

  severity=$(extract_severity "$body")
  title=$(extract_title "$body")

  # Build table row
  row="| \`$path\` | $line | $title |"

  case "$severity" in
    CRITICAL)
      CRITICAL_COUNT=$((CRITICAL_COUNT + 1))
      CRITICAL_ITEMS="${CRITICAL_ITEMS}${row}\n"
      ;;
    WARNING)
      WARNING_COUNT=$((WARNING_COUNT + 1))
      WARNING_ITEMS="${WARNING_ITEMS}${row}\n"
      ;;
    SUGGESTION)
      SUGGESTION_COUNT=$((SUGGESTION_COUNT + 1))
      SUGGESTION_ITEMS="${SUGGESTION_ITEMS}${row}\n"
      ;;
  esac
done < <(echo "$COMMENTS_JSON" | jq -c '.[]')

# Build review body
REVIEW_BODY="## Code Review\n\n"
REVIEW_BODY="${REVIEW_BODY}Found **$COMMENT_COUNT** issue(s) in this PR:\n\n"

# Add critical section if there are critical issues
if [ $CRITICAL_COUNT -gt 0 ]; then
  REVIEW_BODY="${REVIEW_BODY}### :red_circle: Critical Issues ($CRITICAL_COUNT)\n\n"
  REVIEW_BODY="${REVIEW_BODY}| File | Line | Issue |\n"
  REVIEW_BODY="${REVIEW_BODY}|------|------|-------|\n"
  REVIEW_BODY="${REVIEW_BODY}${CRITICAL_ITEMS}\n"
fi

# Add warning section if there are warnings
if [ $WARNING_COUNT -gt 0 ]; then
  REVIEW_BODY="${REVIEW_BODY}### :warning: Warnings ($WARNING_COUNT)\n\n"
  REVIEW_BODY="${REVIEW_BODY}| File | Line | Issue |\n"
  REVIEW_BODY="${REVIEW_BODY}|------|------|-------|\n"
  REVIEW_BODY="${REVIEW_BODY}${WARNING_ITEMS}\n"
fi

# Add suggestion section if there are suggestions
if [ $SUGGESTION_COUNT -gt 0 ]; then
  REVIEW_BODY="${REVIEW_BODY}### :bulb: Suggestions ($SUGGESTION_COUNT)\n\n"
  REVIEW_BODY="${REVIEW_BODY}| File | Line | Issue |\n"
  REVIEW_BODY="${REVIEW_BODY}|------|------|-------|\n"
  REVIEW_BODY="${REVIEW_BODY}${SUGGESTION_ITEMS}\n"
fi

REVIEW_BODY="${REVIEW_BODY}---\n"
REVIEW_BODY="${REVIEW_BODY}*Review generated by Claude Code*"

# Transform input JSON to GitHub review format
# Add "side": "RIGHT" to each comment and wrap in review payload with body
REVIEW_PAYLOAD=$(echo "$COMMENTS_JSON" | jq --arg sha "$COMMIT_SHA" --arg body "$(echo -e "$REVIEW_BODY")" '{
  commit_id: $sha,
  body: $body,
  event: "COMMENT",
  comments: [.[] | {
    path: .path,
    line: .line,
    body: .body,
    side: "RIGHT"
  }]
}')

# Post the review
if echo "$REVIEW_PAYLOAD" | gh api "/repos/$REPO_FULL_NAME/pulls/$PR_NUMBER/reviews" \
     -X POST \
     --input - > /dev/null; then
  echo "✅ Review posted successfully with $COMMENT_COUNT comment(s)"

  # Show summary of comments
  echo ""
  echo "Comments posted:"
  echo "$COMMENTS_JSON" | jq -r '.[] | "  - \(.path):\(.line)"'
else
  echo "❌ Failed to post review" >&2
  echo "" >&2
  echo "Common issues:" >&2
  echo "  - Line numbers might not be part of the diff in this PR" >&2
  echo "  - File paths might not exist in commit $COMMIT_SHA" >&2
  echo "  - Commit SHA might not be the HEAD of the PR" >&2
  echo "" >&2
  echo "Tip: Only lines that were modified or added in the PR can receive inline comments" >&2
  exit 1
fi
