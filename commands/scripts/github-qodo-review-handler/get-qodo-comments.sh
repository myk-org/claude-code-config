#!/bin/bash
set -euo pipefail

# NOTE: This script requires GNU grep (grep -oP). On macOS, install via: brew install grep
# and ensure /usr/local/opt/grep/libexec/gnubin is in PATH, or use ggrep.

# Script to extract Qodo AI review comments for processing
# Usage: get-qodo-comments.sh <pr-info-script-path> [comment_id|comment_url]
#   OR:  get-qodo-comments.sh <owner/repo> <pr_number> [comment_id|comment_url]
#
# Modes:
#   1. No comment ID/URL: Fetch ALL unresolved inline review comments from qodo-code-review[bot]
#   2. Issue comment URL (#issuecomment-XXX): Fetch that comment + all unresolved inline review comments
#   3. Pull request review URL (#pullrequestreview-XXX): Fetch inline comments from that specific review

show_usage() {
  echo "Usage: $0 <pr-info-script-path> [comment_id|comment_url]" >&2
  echo "   OR: $0 <owner/repo> <pr_number> [comment_id|comment_url]" >&2
  echo "" >&2
  echo "The comment ID or URL is OPTIONAL. Behavior:" >&2
  echo "  - No ID/URL: Fetch all unresolved Qodo inline review comments" >&2
  echo "  - Issue comment URL: Fetch that comment + unresolved inline comments" >&2
  echo "  - PR review URL: Fetch inline comments from that specific review" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  $0 /path/to/get-pr-info.sh                                    # All unresolved" >&2
  echo "  $0 /path/to/get-pr-info.sh 1234567890                         # Issue comment + unresolved" >&2
  echo "  $0 /path/to/get-pr-info.sh https://github.com/o/r/pull/1#issuecomment-123" >&2
  echo "  $0 /path/to/get-pr-info.sh https://github.com/o/r/pull/1#pullrequestreview-456" >&2
  echo "  $0 owner/repo 123                                             # All unresolved" >&2
  echo "  $0 owner/repo 123 1234567890                                  # Issue comment + unresolved" >&2
  exit 1
}

# Get unresolved Qodo inline review comments using GraphQL
# Returns JSON array of unresolved comments from qodo-code-review[bot]
# NOTE: GraphQL API returns author.login as "qodo-code-review" (without [bot] suffix),
# while REST API returns user.login as "qodo-code-review[bot]" (with suffix).
# The filter below uses the GraphQL format intentionally.
get_unresolved_qodo_comments() {
  local owner="$1"
  local repo="$2"
  local pr_number="$3"

  local result
  if ! result=$(gh api graphql -f query='
    query($owner: String!, $repo: String!, $pr: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr) {
          reviewThreads(first: 100) {
            nodes {
              id
              isResolved
              comments(first: 10) {
                nodes {
                  id
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
  ' -f owner="$owner" -f repo="$repo" -F pr="$pr_number" --jq '
    [.data.repository.pullRequest.reviewThreads.nodes[] |
     select(.isResolved == false) |
     . as $thread |
     .comments.nodes[] |
     select(.author.login == "qodo-code-review") |
     {
       thread_id: $thread.id,
       comment_id: .databaseId,
       node_id: .id,
       path: .path,
       line: .line,
       body: .body
     }]
  ' 2>&1); then
    echo "Warning: Could not fetch unresolved comments: $result" >&2
    echo "[]"
    return 0
  fi
  echo "$result"
}

# Get inline comments from a specific PR review
get_review_inline_comments() {
  local owner="$1"
  local repo="$2"
  local pr_number="$3"
  local review_id="$4"

  gh api "/repos/$owner/$repo/pulls/$pr_number/reviews/$review_id/comments?per_page=100" --jq '.'
}

# Parse inline review comments into suggestion format
parse_inline_comments_to_suggestions() {
  local comments_json="$1"
  local start_id="$2"

  echo "$comments_json" | jq --argjson start_id "$start_id" '
    def get_priority:
      if (.body | test("bug|error|security|critical"; "i")) then "HIGH"
      elif (.body | test("warning|issue|problem"; "i")) then "MEDIUM"
      else "LOW"
      end;

    def get_category:
      if (.body | test("security"; "i")) then "Security"
      elif (.body | test("bug|error"; "i")) then "Possible bug"
      elif (.body | test("performance"; "i")) then "Performance"
      elif (.body | test("style|format"; "i")) then "Code style"
      else "Suggestion"
      end;

    def extract_suggestion_from_body:
      # Try to extract code suggestion from markdown code block
      if (.body | test("```suggestion")) then
        (.body | capture("```suggestion\\n(?<code>[\\s\\S]*?)\\n```") | .code // "")
      elif (.body | test("```diff")) then
        (.body | capture("```diff\\n(?<code>[\\s\\S]*?)\\n```") | .code // "")
      else
        ""
      end;

    def extract_title_from_body:
      # Extract first line or first sentence as title
      (.body | split("\n")[0] | gsub("^#+\\s*"; "") | gsub("\\*\\*"; "") | .[0:100]);

    [to_entries | .[] | .value as $comment | .key as $idx |
    {
      id: ($start_id + $idx),
      source: "inline_review",
      thread_id: ($comment.thread_id // null),
      comment_id: ($comment.comment_id // $comment.databaseId // $comment.id),
      priority: ($comment | get_priority),
      category: ($comment | get_category),
      title: ($comment | extract_title_from_body),
      file: ($comment.path // ""),
      line_range: (if $comment.line then ($comment.line | tostring) else "" end),
      file_url: "",
      importance: (if ($comment | get_priority) == "HIGH" then 10 elif ($comment | get_priority) == "MEDIUM" then 5 else 3 end),
      description: $comment.body,
      suggested_diff: ($comment | extract_suggestion_from_body),
      body: $comment.body
    }]
  '
}

# Function to map priority based on category and impact
get_priority() {
  local category="$1"
  local impact="${2:-}"

  # Security or High impact = HIGH priority
  if [[ "$category" =~ [Ss]ecurity ]] || [[ "$impact" =~ [Hh]igh ]]; then
    echo "HIGH"
  # Possible bug or Medium impact = MEDIUM priority
  elif [[ "$category" =~ [Pp]ossible[[:space:]]?[Bb]ug ]] || [[ "$impact" =~ [Mm]edium ]]; then
    echo "MEDIUM"
  # Possible issue or Low impact = LOW priority
  elif [[ "$category" =~ [Pp]ossible[[:space:]]?[Ii]ssue ]] || [[ "$impact" =~ [Ll]ow ]]; then
    echo "LOW"
  else
    echo "MEDIUM"
  fi
}

# Parse /review issue comments
parse_review_issue_comment() {
  local comment_body="$1"
  local suggestions='[]'
  local id=1

  # Parse Security concerns from HTML table cell
  local security_concern
  security_concern=$(echo "$comment_body" | awk '
    BEGIN { in_security = 0; content = "" }
    /<strong>Security concerns<\/strong>/ {
      in_security = 1
      sub(/.*<strong>Security concerns<\/strong>/, "")
      sub(/<br><br>/, "")
      if (length($0) > 0) content = $0
      next
    }
    in_security {
      if (/<\/td><\/tr>/ || /<\/td>/) {
        sub(/<\/td>.*/, "")
        content = content " " $0
        in_security = 0
      } else {
        content = content " " $0
      }
    }
    END {
      gsub(/<br>/, " ", content)
      gsub(/<[^>]+>/, "", content)
      gsub(/[[:space:]]+/, " ", content)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", content)
      if (length(content) > 0 && content !~ /^None$/) {
        print content
      }
    }
  ')

  if [ -n "$security_concern" ] && [ "$security_concern" != "None" ]; then
    suggestions=$(echo "$suggestions" | jq --argjson id "$id" --arg body "$security_concern" '
      . + [{
        "id": $id,
        "source": "issue_comment",
        "priority": "HIGH",
        "category": "Security",
        "title": "Security concern",
        "file": "",
        "line_range": "",
        "file_url": "",
        "importance": 10,
        "description": $body,
        "suggested_diff": "",
        "body": $body
      }]
    ')
    id=$((id + 1))
  fi

  # Parse Recommended focus areas from <details> sections
  local block=""

  while IFS= read -r line; do
    if [[ "$line" == "---BLOCK_END---" ]]; then
      if [ -n "$block" ]; then
        # Skip Tool usage guide block
        if echo "$block" | grep -q "Tool usage guide"; then
          block=""
          continue
        fi

        # Extract title
        local title
        title=$(echo "$block" | grep -oP '(?<=<strong>)[^<]+(?=</strong>)' | head -1 || echo "")

        # Extract file URL
        local file_url
        file_url=$(echo "$block" | grep -oP "(?<=<summary><a href=')[^']+(?=')" | head -1 || echo "")

        # Extract line range from URL
        local line_range=""
        if [ -n "$file_url" ]; then
          line_range=$(echo "$file_url" | grep -oP 'R\d+-R\d+' | sed 's/R//g; s/-R/-/' || echo "")
        fi

        # Extract description
        local description
        description=$(echo "$block" | awk '
          BEGIN { capture = 0 }
          /<\/a>/ { capture = 1; sub(/.*<\/a>/, ""); }
          capture && /<\/summary>/ { sub(/<\/summary>.*/, ""); capture = 0 }
          capture { print }
        ' | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g; s/^[[:space:]]*//; s/[[:space:]]*$//')

        # Extract code snippet
        local code_snippet=""
        if echo "$block" | grep -q '```'; then
          code_snippet=$(echo "$block" | awk '
            BEGIN { capture = 0 }
            /^```[a-z]*$/ { if (!capture) { capture = 1; next } else { exit } }
            /^```$/ { if (capture) exit }
            capture { print }
          ' | head -30)
        fi

        if [ -n "$title" ]; then
          suggestions=$(echo "$suggestions" | jq \
            --argjson id "$id" \
            --arg title "$title" \
            --arg line_range "$line_range" \
            --arg file_url "$file_url" \
            --arg description "$description" \
            --arg code_snippet "$code_snippet" \
            --arg body "$block" '
            . + [{
              "id": $id,
              "source": "issue_comment",
              "priority": "MEDIUM",
              "category": "Focus area",
              "title": $title,
              "file": "",
              "line_range": $line_range,
              "file_url": $file_url,
              "importance": 5,
              "description": $description,
              "suggested_diff": $code_snippet,
              "body": $body
            }]
          ')
          id=$((id + 1))
        fi
      fi
      block=""
    else
      if [ -z "$block" ]; then
        block="$line"
      else
        block="$block"$'\n'"$line"
      fi
    fi
  done < <(
    echo "$comment_body" | awk '
      BEGIN { in_details = 0; block = "" }
      /<details>/ { in_details = 1; block = $0; next }
      /<\/details>/ {
        if (in_details) {
          block = block "\n" $0
          print block
          print "---BLOCK_END---"
        }
        in_details = 0
        block = ""
        next
      }
      in_details { block = block "\n" $0 }
    '
  )

  echo "$suggestions"
}

# Parse /improve issue comments
parse_improve_issue_comment() {
  local comment_body="$1"
  local suggestions='[]'
  local id=1

  # Save comment body to temp file for awk processing
  local tmpfile
  tmpfile=$(mktemp /tmp/qodo-improve-XXXXXX.txt)
  echo "$comment_body" > "$tmpfile"

  while IFS=$'\t' read -r category title impact file line_range file_url importance description diff_block; do
    [ -z "$title" ] && continue

    # Determine priority
    local priority
    priority=$(get_priority "$category" "$impact")

    # Add to suggestions array
    suggestions=$(echo "$suggestions" | jq \
      --argjson id "$id" \
      --arg priority "$priority" \
      --arg category "${category:-}" \
      --arg title "$title" \
      --arg file "${file:-}" \
      --arg line_range "${line_range:-}" \
      --arg file_url "${file_url:-}" \
      --argjson importance "${importance:-5}" \
      --arg description "${description:-}" \
      --arg suggested_diff "${diff_block:-}" \
      --arg body "$title: $description" '
      . + [{
        "id": $id,
        "source": "issue_comment",
        "priority": $priority,
        "category": $category,
        "title": $title,
        "file": $file,
        "line_range": $line_range,
        "file_url": $file_url,
        "importance": $importance,
        "description": $description,
        "suggested_diff": $suggested_diff,
        "body": $body
      }]
    ')
    id=$((id + 1))
  done < <(gawk '
    BEGIN {
      RS = "<tr>"
      FS = ""
      last_category = ""
    }

    /<details><summary>/ && !/- \[ \] More/ && !/<strong>Category<\/strong>/ {

      has_real_title = 0
      tmp = $0
      while (match(tmp, /<details><summary>[^<]+<\/summary>/) > 0) {
        block = substr(tmp, RSTART, RLENGTH)
        gsub(/<details><summary>/, "", block)
        gsub(/<\/summary>/, "", block)
        if (block !~ /^Suggestion importance/ && block !~ /^✅/) {
          has_real_title = 1
          break
        }
        tmp = substr(tmp, RSTART + RLENGTH)
      }
      if (!has_real_title) next

      category = ""
      if (match($0, /<td[^>]*>[^<]*<\/td>/)) {
        block = substr($0, RSTART, RLENGTH)
        gsub(/<td[^>]*>/, "", block)
        gsub(/<\/td>/, "", block)
        gsub(/rowspan=[0-9]+/, "", block)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", block)
        if (block !~ /^(High|Medium|Low)$/ && block != "") {
          category = block
          last_category = category
        }
      }
      if (category == "") {
        category = last_category
      }

      title = ""
      tmp = $0
      while (match(tmp, /<details><summary>[^<]+<\/summary>/) > 0) {
        block = substr(tmp, RSTART, RLENGTH)
        gsub(/<details><summary>/, "", block)
        gsub(/<\/summary>/, "", block)
        if (block !~ /^Suggestion importance/ && block !~ /^✅/) {
          title = block
          break
        }
        tmp = substr(tmp, RSTART + RLENGTH)
      }
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", title)

      if (title == "") next

      impact = ""
      if (match($0, /<td[^>]*>(High|Medium|Low)[[:space:]]*\n?<\/td>/)) {
        tmp = substr($0, RSTART, RLENGTH)
        gsub(/<[^>]+>/, "", tmp)
        gsub(/[[:space:]]+/, "", tmp)
        impact = tmp
      }

      file = ""
      line_range = ""
      file_url = ""
      if (match($0, /\[[^\]]+\s+\[[0-9]+-[0-9]+\]\]\([^)]+\)/)) {
        link = substr($0, RSTART, RLENGTH)
        if (match(link, /\[[^\]]+\s+\[/)) {
          file = substr(link, RSTART + 1, RLENGTH - 3)
        }
        if (match(link, /\[[0-9]+-[0-9]+\]/)) {
          line_range = substr(link, RSTART + 1, RLENGTH - 2)
        }
        if (match(link, /\(https?:[^)]+\)/)) {
          file_url = substr(link, RSTART + 1, RLENGTH - 2)
        }
      }

      importance = 5
      if (match($0, /importance\[1-10\]:[[:space:]]*[0-9]+/)) {
        tmp = substr($0, RSTART, RLENGTH)
        if (match(tmp, /[0-9]+$/)) {
          importance = substr(tmp, RSTART, RLENGTH) + 0
        }
      }

      description = ""
      pos = index($0, "___")
      if (pos > 0) {
        rest = substr($0, pos + 3)
        if (match(rest, /\*\*[^*]+\*\*/)) {
          description = substr(rest, RSTART + 2, RLENGTH - 4)
          gsub(/<br>/, " ", description)
          gsub(/<[^>]+>/, "", description)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", description)
          gsub(/\n/, " ", description)
        }
      }

      diff_block = ""
      if (match($0, /```diff/)) {
        start = RSTART + 7
        rest = substr($0, start)
        if (match(rest, /```/)) {
          diff_block = substr(rest, 1, RSTART - 1)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", diff_block)
          gsub(/\t/, "    ", diff_block)
        }
      }

      gsub(/\n/, "%%NEWLINE%%", diff_block)
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%s\n", \
        category, title, impact, file, line_range, file_url, importance, description, diff_block
    }
  ' "$tmpfile")

  rm -f "$tmpfile"
  echo "$suggestions"
}

# Initialize variables
REPO_FULL_NAME=""
PR_NUMBER=""
TARGET_PARAM=""
HAS_TARGET=false

# Parse arguments and validate
if [ $# -eq 0 ]; then
  show_usage

elif [ $# -eq 1 ]; then
  # One argument: pr-info script only (no target comment - fetch all unresolved)
  if [ -f "$1" ]; then
    PR_INFO_SCRIPT="$1"
    if ! PR_INFO=$("$PR_INFO_SCRIPT"); then
      echo "Error: Failed to get PR information" >&2
      exit 1
    fi
    REPO_FULL_NAME=$(echo "$PR_INFO" | cut -d' ' -f1)
    PR_NUMBER=$(echo "$PR_INFO" | cut -d' ' -f2)
    HAS_TARGET=false
  else
    echo "Error: '$1' is not a valid script file path." >&2
    show_usage
  fi

elif [ $# -eq 2 ]; then
  # Two arguments: could be (pr-info-script + target) OR (owner/repo + pr_number)
  if [ -f "$1" ]; then
    # First argument is pr-info script path, second is comment ID/URL
    PR_INFO_SCRIPT="$1"
    TARGET_PARAM="$2"
    HAS_TARGET=true

    if ! PR_INFO=$("$PR_INFO_SCRIPT"); then
      echo "Error: Failed to get PR information" >&2
      exit 1
    fi
    REPO_FULL_NAME=$(echo "$PR_INFO" | cut -d' ' -f1)
    PR_NUMBER=$(echo "$PR_INFO" | cut -d' ' -f2)
  elif [[ "$1" =~ / ]]; then
    # First argument looks like owner/repo, second is PR number
    REPO_FULL_NAME="$1"
    PR_NUMBER="$2"
    HAS_TARGET=false
  else
    echo "Error: '$1' is not a valid script file path or owner/repo format." >&2
    show_usage
  fi

elif [ $# -eq 3 ]; then
  # Three arguments: owner/repo, PR number, and comment ID/URL
  REPO_FULL_NAME="$1"
  PR_NUMBER="$2"
  TARGET_PARAM="$3"
  HAS_TARGET=true

else
  show_usage
fi

OWNER=$(echo "$REPO_FULL_NAME" | cut -d'/' -f1)
REPO=$(echo "$REPO_FULL_NAME" | cut -d'/' -f2)

echo "Repository: $OWNER/$REPO, PR: $PR_NUMBER" >&2

# Determine target type and fetch comments accordingly
ISSUE_COMMENT_SUGGESTIONS='[]'
INLINE_REVIEW_SUGGESTIONS='[]'
ISSUE_COMMENT_ID=""
ISSUE_COMMENT_TYPE=""

if [ "$HAS_TARGET" = true ]; then
  # Parse the target parameter
  if [[ "$TARGET_PARAM" =~ issuecomment-([0-9]+) ]]; then
    # Issue comment URL
    ISSUE_COMMENT_ID="${BASH_REMATCH[1]}"
    echo "Extracting issue comment ID from URL: $ISSUE_COMMENT_ID" >&2

  elif [[ "$TARGET_PARAM" =~ pullrequestreview-([0-9]+) ]]; then
    # PR review URL - fetch inline comments from that review
    REVIEW_ID="${BASH_REMATCH[1]}"
    echo "Extracting PR review ID from URL: $REVIEW_ID" >&2

    echo "Fetching inline comments from review $REVIEW_ID..." >&2
    REVIEW_COMMENTS=$(get_review_inline_comments "$OWNER" "$REPO" "$PR_NUMBER" "$REVIEW_ID")

    if [ "$(echo "$REVIEW_COMMENTS" | jq '. | length')" -gt 0 ]; then
      # Transform REST API response to expected format, then parse
      # NOTE: thread_id is null because REST API doesn't provide thread IDs.
      # This means these comments cannot be resolved via GraphQL (limitation of REST API).
      # Only comments fetched via get_unresolved_qodo_comments (GraphQL) have thread_id.
      TRANSFORMED=$(echo "$REVIEW_COMMENTS" | jq '[.[] | {
        thread_id: null,
        comment_id: .id,
        path: .path,
        line: .line,
        body: .body
      }]')
      INLINE_REVIEW_SUGGESTIONS=$(parse_inline_comments_to_suggestions "$TRANSFORMED" 1)
    else
      INLINE_REVIEW_SUGGESTIONS="[]"
    fi

  elif [[ "$TARGET_PARAM" =~ ^[0-9]+$ ]]; then
    # Numeric ID - assume issue comment
    ISSUE_COMMENT_ID="$TARGET_PARAM"
    echo "Using provided comment ID: $ISSUE_COMMENT_ID" >&2

  else
    echo "Error: Invalid comment parameter. Must be a comment ID or URL." >&2
    echo "   Issue comment: https://github.com/owner/repo/pull/123#issuecomment-1234567890" >&2
    echo "   PR review: https://github.com/owner/repo/pull/123#pullrequestreview-1234567890" >&2
    exit 1
  fi
fi

# Fetch issue comment if ID was provided
if [ -n "$ISSUE_COMMENT_ID" ]; then
  echo "Fetching issue comment $ISSUE_COMMENT_ID..." >&2

  # Validate the comment exists and is from Qodo
  COMMENT_USER=$(gh api "/repos/$OWNER/$REPO/issues/comments/$ISSUE_COMMENT_ID" --jq '.user.login' 2>&1) || {
    echo "Error: Could not fetch comment $ISSUE_COMMENT_ID. It may not exist or you may not have access." >&2
    echo "   API response: $COMMENT_USER" >&2
    exit 1
  }

  # NOTE: REST API returns user.login as "qodo-code-review[bot]" (with [bot] suffix),
  # while GraphQL API returns author.login as "qodo-code-review" (without suffix).
  if [ "$COMMENT_USER" != "qodo-code-review[bot]" ]; then
    echo "Error: Comment $ISSUE_COMMENT_ID is from '$COMMENT_USER', not Qodo (qodo-code-review[bot])." >&2
    exit 1
  fi
  echo "Comment from qodo-code-review[bot]" >&2

  # Get comment body
  COMMENT_BODY=$(gh api "/repos/$OWNER/$REPO/issues/comments/$ISSUE_COMMENT_ID" --jq '.body' 2>/dev/null)

  # Determine comment type
  if echo "$COMMENT_BODY" | grep -q "PR Reviewer Guide"; then
    ISSUE_COMMENT_TYPE="review"
    echo "Detected /review comment" >&2
  elif echo "$COMMENT_BODY" | grep -q "PR Code Suggestions"; then
    ISSUE_COMMENT_TYPE="improve"
    echo "Detected /improve comment" >&2
  else
    echo "Error: Comment does not contain 'PR Reviewer Guide' or 'PR Code Suggestions'." >&2
    echo "   This does not appear to be a Qodo /review or /improve comment." >&2
    exit 1
  fi

  echo "Parsing Qodo $ISSUE_COMMENT_TYPE comment..." >&2

  # Parse issue comment based on type
  if [ "$ISSUE_COMMENT_TYPE" = "review" ]; then
    ISSUE_COMMENT_SUGGESTIONS=$(parse_review_issue_comment "$COMMENT_BODY")
  else
    ISSUE_COMMENT_SUGGESTIONS=$(parse_improve_issue_comment "$COMMENT_BODY")
  fi
fi

# Always fetch unresolved inline review comments (unless we only have a PR review URL)
if [ -z "${REVIEW_ID:-}" ]; then
  echo "Fetching unresolved inline review comments..." >&2
  UNRESOLVED_COMMENTS=$(get_unresolved_qodo_comments "$OWNER" "$REPO" "$PR_NUMBER")
  UNRESOLVED_COUNT=$(echo "$UNRESOLVED_COMMENTS" | jq '. | length')

  if [ "$UNRESOLVED_COUNT" -gt 0 ]; then
    echo "Found $UNRESOLVED_COUNT unresolved inline comments" >&2
    # Calculate start ID for inline suggestions (after issue comment suggestions)
    ISSUE_SUGGESTION_COUNT=$(echo "$ISSUE_COMMENT_SUGGESTIONS" | jq '. | length')
    START_ID=$((ISSUE_SUGGESTION_COUNT + 1))
    INLINE_REVIEW_SUGGESTIONS=$(parse_inline_comments_to_suggestions "$UNRESOLVED_COMMENTS" "$START_ID")
  else
    echo "No unresolved inline comments found" >&2
  fi
fi

# Merge suggestions from issue comment and inline reviews
ALL_SUGGESTIONS=$(jq -n \
  --argjson issue "$ISSUE_COMMENT_SUGGESTIONS" \
  --argjson inline "$INLINE_REVIEW_SUGGESTIONS" \
  '$issue + $inline'
)

# Sort suggestions by priority (HIGH > MEDIUM > LOW) then by importance (descending)
ALL_SUGGESTIONS=$(echo "$ALL_SUGGESTIONS" | jq '
  def priority_order: if . == "HIGH" then 0 elif . == "MEDIUM" then 1 else 2 end;
  sort_by((.priority | priority_order), (-.importance))
')

# Re-assign sequential IDs after merging and sorting
ALL_SUGGESTIONS=$(echo "$ALL_SUGGESTIONS" | jq '
  [to_entries | .[] | .value + {id: (.key + 1)}]
')

# Calculate counts
HIGH_COUNT=$(echo "$ALL_SUGGESTIONS" | jq '[.[] | select(.priority == "HIGH")] | length')
MEDIUM_COUNT=$(echo "$ALL_SUGGESTIONS" | jq '[.[] | select(.priority == "MEDIUM")] | length')
LOW_COUNT=$(echo "$ALL_SUGGESTIONS" | jq '[.[] | select(.priority == "LOW")] | length')
TOTAL_COUNT=$((HIGH_COUNT + MEDIUM_COUNT + LOW_COUNT))

ISSUE_COMMENT_COUNT=$(echo "$ALL_SUGGESTIONS" | jq '[.[] | select(.source == "issue_comment")] | length')
INLINE_REVIEW_COUNT=$(echo "$ALL_SUGGESTIONS" | jq '[.[] | select(.source == "inline_review")] | length')

# Build final JSON output
jq -n \
  --arg comment_id "${ISSUE_COMMENT_ID:-}" \
  --arg comment_type "${ISSUE_COMMENT_TYPE:-}" \
  --arg owner "$OWNER" \
  --arg repo "$REPO" \
  --arg pr_number "$PR_NUMBER" \
  --argjson high "$HIGH_COUNT" \
  --argjson medium "$MEDIUM_COUNT" \
  --argjson low "$LOW_COUNT" \
  --argjson total "$TOTAL_COUNT" \
  --argjson issue_comment_count "$ISSUE_COMMENT_COUNT" \
  --argjson inline_review_count "$INLINE_REVIEW_COUNT" \
  --argjson suggestions "$ALL_SUGGESTIONS" '
{
  "metadata": {
    "comment_id": (if $comment_id == "" then null else $comment_id end),
    "comment_type": (if $comment_type == "" then null else $comment_type end),
    "owner": $owner,
    "repo": $repo,
    "pr_number": $pr_number
  },
  "summary": {
    "high": $high,
    "medium": $medium,
    "low": $low,
    "total": $total,
    "by_source": {
      "issue_comment": $issue_comment_count,
      "inline_review": $inline_review_count
    }
  },
  "suggestions": $suggestions
}
'
