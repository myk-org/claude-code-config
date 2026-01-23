#!/bin/bash
set -euo pipefail

# NOTE: This script requires GNU grep (grep -oP). On macOS, install via: brew install grep
# and ensure /usr/local/opt/grep/libexec/gnubin is in PATH, or use ggrep.

# Script to extract Qodo AI review comments for processing
# Usage: get-qodo-comments.sh <pr-info-script-path> <comment_id|comment_url>
#   OR:  get-qodo-comments.sh <owner/repo> <pr_number> <comment_id|comment_url>

show_usage() {
  echo "Usage: $0 <pr-info-script-path> <comment_id|comment_url>" >&2
  echo "   OR: $0 <owner/repo> <pr_number> <comment_id|comment_url>" >&2
  echo "" >&2
  echo "The comment ID or URL is REQUIRED. You can find it from:" >&2
  echo "  - GitHub PR page: click on a Qodo review comment, copy the URL" >&2
  echo "  - The URL will look like: https://github.com/owner/repo/pull/123#issuecomment-1234567890" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  $0 /path/to/get-pr-info.sh 1234567890" >&2
  echo "  $0 /path/to/get-pr-info.sh https://github.com/owner/repo/pull/123#issuecomment-1234567890" >&2
  echo "  $0 owner/repo 123 1234567890" >&2
  echo "  $0 owner/repo 123 https://github.com/owner/repo/pull/123#issuecomment-1234567890" >&2
  exit 1
}

# Parse arguments and validate
if [ $# -eq 2 ]; then
  # Two arguments: check if first arg is a file (pr-info script)
  if [ -f "$1" ]; then
    # First argument is pr-info script path, second is comment ID/URL (REQUIRED)
    PR_INFO_SCRIPT="$1"
    TARGET_PARAM="$2"

    # Call the pr-info script and parse output
    if ! PR_INFO=$("$PR_INFO_SCRIPT"); then
      echo "Error: Failed to get PR information" >&2
      exit 1
    fi

    # Parse the output (space-separated: REPO_FULL_NAME PR_NUMBER)
    REPO_FULL_NAME=$(echo "$PR_INFO" | cut -d' ' -f1)
    PR_NUMBER=$(echo "$PR_INFO" | cut -d' ' -f2)
  else
    # First argument is not a file - could be owner/repo format but missing arguments
    echo "Error: '$1' is not a valid script file path." >&2
    echo "" >&2
    show_usage
  fi

elif [ $# -eq 3 ]; then
  # Three arguments: owner/repo, PR number, and comment ID/URL (REQUIRED)
  REPO_FULL_NAME="$1"
  PR_NUMBER="$2"
  TARGET_PARAM="$3"

else
  show_usage
fi

OWNER=$(echo "$REPO_FULL_NAME" | cut -d'/' -f1)
REPO=$(echo "$REPO_FULL_NAME" | cut -d'/' -f2)

# Step 1: Parse comment ID/URL and fetch comment data
# Extract comment ID from URL or use numeric ID directly
if [[ "$TARGET_PARAM" =~ issuecomment-([0-9]+) ]]; then
    PROVIDED_COMMENT_ID="${BASH_REMATCH[1]}"
    echo "📝 Extracting comment ID from URL: $PROVIDED_COMMENT_ID" >&2
elif [[ "$TARGET_PARAM" =~ ^[0-9]+$ ]]; then
    PROVIDED_COMMENT_ID="$TARGET_PARAM"
    echo "📝 Using provided comment ID: $PROVIDED_COMMENT_ID" >&2
else
    echo "❌ Error: Invalid comment parameter. Must be a comment ID (number) or comment URL." >&2
    echo "   Example URL: https://github.com/owner/repo/pull/123#issuecomment-1234567890" >&2
    exit 1
fi

# Fetch issue comment (Qodo uses issue comments, not PR review comments)
# NOTE: We use gh api --jq directly because some comment bodies contain control characters
# that cause jq parse errors when piped separately.
echo "📥 Fetching comment data..." >&2

# First, validate the comment exists and get the user
COMMENT_USER=$(gh api "/repos/$OWNER/$REPO/issues/comments/$PROVIDED_COMMENT_ID" --jq '.user.login' 2>&1) || {
  echo "❌ Error: Could not fetch comment $PROVIDED_COMMENT_ID. It may not exist or you may not have access." >&2
  echo "   API response: $COMMENT_USER" >&2
  exit 1
}

if [ "$COMMENT_USER" != "qodo-code-review[bot]" ]; then
  echo "❌ Error: Comment $PROVIDED_COMMENT_ID is from '$COMMENT_USER', not Qodo (qodo-code-review[bot])." >&2
  exit 1
fi
echo "✅ Comment from qodo-code-review[bot]" >&2

# Get comment body using --jq to avoid control character issues
COMMENT_BODY=$(gh api "/repos/$OWNER/$REPO/issues/comments/$PROVIDED_COMMENT_ID" --jq '.body' 2>/dev/null)

# Determine comment type (review or improve)
if echo "$COMMENT_BODY" | grep -q "PR Reviewer Guide"; then
  COMMENT_TYPE="review"
  echo "📋 Detected /review comment" >&2
elif echo "$COMMENT_BODY" | grep -q "PR Code Suggestions"; then
  COMMENT_TYPE="improve"
  echo "📋 Detected /improve comment" >&2
else
  echo "❌ Error: Comment does not contain 'PR Reviewer Guide' or 'PR Code Suggestions'." >&2
  echo "   This does not appear to be a Qodo /review or /improve comment." >&2
  exit 1
fi

echo "🔍 Parsing Qodo $COMMENT_TYPE comment..." >&2

# Initialize counters
HIGH_COUNT=0
MEDIUM_COUNT=0
LOW_COUNT=0

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

# Parse /review comments
parse_review_comments() {
  local suggestions='[]'
  local id=1

  # Parse Security concerns from HTML table cell
  # Format: <tr><td>🔒&nbsp;<strong>Security concerns</strong><br><br>...content...</td></tr>
  local security_concern
  security_concern=$(echo "$COMMENT_BODY" | awk '
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
    HIGH_COUNT=$((HIGH_COUNT + 1))
  fi

  # Parse Recommended focus areas from <details> sections
  # Format: <details><summary><a href='url'><strong>Title</strong></a>\nDescription\n</summary>\n```python\ncode\n```\n</details>
  # Skip the "Tool usage guide" block at the end

  # Extract all details blocks and process them
  local block=""
  local in_block=0

  while IFS= read -r line; do
    if [[ "$line" == "---BLOCK_END---" ]]; then
      # Process the accumulated block
      if [ -n "$block" ]; then
        # Skip Tool usage guide block
        if echo "$block" | grep -q "Tool usage guide"; then
          block=""
          continue
        fi

        # Extract title - may be inside <a><strong>Title</strong></a> or just <strong>Title</strong>
        local title
        title=$(echo "$block" | grep -oP '(?<=<strong>)[^<]+(?=</strong>)' | head -1 || echo "")

        # Extract file URL from the <a> tag in <summary>
        local file_url
        file_url=$(echo "$block" | grep -oP "(?<=<summary><a href=')[^']+(?=')" | head -1 || echo "")

        # Extract file path and line range from URL
        # URL format: https://github.com/.../pull/NNN/files#diff-HASH-RSTART-REND
        local file=""
        local line_range=""
        if [ -n "$file_url" ]; then
          # Try to extract line range from URL fragment (R462-R476)
          line_range=$(echo "$file_url" | grep -oP 'R\d+-R\d+' | sed 's/R//g; s/-R/-/' || echo "")
        fi

        # Extract description - text between </a> and </summary>
        # Format: <summary><a href='...'><strong>Title</strong></a>\n\nDescription\n</summary>
        local description
        description=$(echo "$block" | awk '
          BEGIN { capture = 0 }
          /<\/a>/ { capture = 1; sub(/.*<\/a>/, ""); }
          capture && /<\/summary>/ { sub(/<\/summary>.*/, ""); capture = 0 }
          capture { print }
        ' | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g; s/^[[:space:]]*//; s/[[:space:]]*$//')

        # Extract code snippet if present (between ``` markers)
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
            --arg file "$file" \
            --arg line_range "$line_range" \
            --arg file_url "$file_url" \
            --arg description "$description" \
            --arg code_snippet "$code_snippet" \
            --arg body "$block" '
            . + [{
              "id": $id,
              "priority": "MEDIUM",
              "category": "Focus area",
              "title": $title,
              "file": $file,
              "line_range": $line_range,
              "file_url": $file_url,
              "importance": 5,
              "description": $description,
              "suggested_diff": $code_snippet,
              "body": $body
            }]
          ')
          id=$((id + 1))
          MEDIUM_COUNT=$((MEDIUM_COUNT + 1))
        fi
      fi
      block=""
    else
      # Accumulate lines into block
      if [ -z "$block" ]; then
        block="$line"
      else
        block="$block"$'\n'"$line"
      fi
    fi
  done < <(
    # Extract details blocks, output each block followed by ---BLOCK_END--- marker
    echo "$COMMENT_BODY" | awk '
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

# Parse /improve comments
parse_improve_comments() {
  local suggestions='[]'
  local id=1

  # Qodo /improve uses HTML table format with nested structure:
  # <tr><td rowspan=1>Category</td>
  # <td>
  #   <details><summary>Title</summary>
  #   ___
  #   **Description text...**
  #   [file.py [line-range]](url)
  #   ```diff
  #   ...
  #   ```
  #   <details><summary>Suggestion importance[1-10]: N</summary>
  #   ...
  #   </details></details>
  # </td>
  # <td align=center>Impact</td></tr>
  #
  # Strategy: Use awk to split by table rows (<tr>) and extract fields

  # Save comment body to temp file for awk processing (handles multiline better)
  local tmpfile
  tmpfile=$(mktemp /tmp/qodo-improve-XXXXXX.txt)
  echo "$COMMENT_BODY" > "$tmpfile"

  # Extract suggestion rows using awk
  # Each suggestion is in a <tr> that contains:
  # 1. <td...>Category</td>
  # 2. <td> with <details><summary>Title</summary> and ```diff block
  # 3. <td...>Impact</td>
  while IFS=$'\t' read -r category title impact file line_range file_url importance description diff_block; do
    [ -z "$title" ] && continue

    # Determine priority based on category and impact
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
      # Track the last category for rows that share rowspan
      last_category = ""
    }

    # Only process rows that have <details><summary> (actual suggestions)
    # Skip rows with only "Suggestion importance" summaries (nested details only)
    # Skip "More" button rows and header rows
    /<details><summary>/ && !/- \[ \] More/ && !/<strong>Category<\/strong>/ {

      # Check if this row has a real title (not just importance summary)
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

      # Extract category from first <td> that contains a category name
      # Format: <td rowspan=1>Category</td> or <td>Category</td>
      # Note: Some rows share category via rowspan and dont have their own <td>Category</td>
      category = ""
      if (match($0, /<td[^>]*>[^<]*<\/td>/)) {
        block = substr($0, RSTART, RLENGTH)
        gsub(/<td[^>]*>/, "", block)
        gsub(/<\/td>/, "", block)
        gsub(/rowspan=[0-9]+/, "", block)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", block)
        # Check if this is a valid category (not High/Medium/Low which is impact)
        if (block !~ /^(High|Medium|Low)$/ && block != "") {
          category = block
          last_category = category
        }
      }
      # If no category found in this row, use the last one (rowspan continuation)
      if (category == "") {
        category = last_category
      }

      # Extract title from first non-importance <details><summary>
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

      # Skip if no valid title
      if (title == "") next

      # Extract impact from <td...>High|Medium|Low</td>
      impact = ""
      if (match($0, /<td[^>]*>(High|Medium|Low)[[:space:]]*\n?<\/td>/)) {
        tmp = substr($0, RSTART, RLENGTH)
        gsub(/<[^>]+>/, "", tmp)
        gsub(/[[:space:]]+/, "", tmp)
        impact = tmp
      }

      # Extract file and line range from file link
      # Format: [file.py [line-range]](url)
      file = ""
      line_range = ""
      file_url = ""
      if (match($0, /\[[^\]]+\s+\[[0-9]+-[0-9]+\]\]\([^)]+\)/)) {
        link = substr($0, RSTART, RLENGTH)
        # Extract file name
        if (match(link, /\[[^\]]+\s+\[/)) {
          file = substr(link, RSTART + 1, RLENGTH - 3)
        }
        # Extract line range
        if (match(link, /\[[0-9]+-[0-9]+\]/)) {
          line_range = substr(link, RSTART + 1, RLENGTH - 2)
        }
        # Extract URL
        if (match(link, /\(https?:[^)]+\)/)) {
          file_url = substr(link, RSTART + 1, RLENGTH - 2)
        }
      }

      # Extract importance score
      # Format: Suggestion importance[1-10]: N
      importance = 5
      if (match($0, /importance\[1-10\]:[[:space:]]*[0-9]+/)) {
        tmp = substr($0, RSTART, RLENGTH)
        if (match(tmp, /[0-9]+$/)) {
          importance = substr(tmp, RSTART, RLENGTH) + 0
        }
      }

      # Extract description - text between ___ and file link
      # Format: ___\n\n**Description...**\n\n[file
      description = ""
      pos = index($0, "___")
      if (pos > 0) {
        rest = substr($0, pos + 3)
        # Find the bolded description between ** ... **
        if (match(rest, /\*\*[^*]+\*\*/)) {
          description = substr(rest, RSTART + 2, RLENGTH - 4)
          # Clean up <br> and HTML tags
          gsub(/<br>/, " ", description)
          gsub(/<[^>]+>/, "", description)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", description)
          # Replace newlines with spaces
          gsub(/\n/, " ", description)
        }
      }

      # Extract diff block
      # Format: ```diff\n...\n```
      diff_block = ""
      if (match($0, /```diff/)) {
        start = RSTART + 7  # after ```diff
        rest = substr($0, start)
        if (match(rest, /```/)) {
          diff_block = substr(rest, 1, RSTART - 1)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", diff_block)
          # Escape tabs and newlines for safe transport
          gsub(/\t/, "    ", diff_block)
        }
      }

      # Output tab-separated fields (diff uses %%NEWLINE%% as placeholder)
      gsub(/\n/, "%%NEWLINE%%", diff_block)
      printf "%s\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%s\n", \
        category, title, impact, file, line_range, file_url, importance, description, diff_block
    }
  ' "$tmpfile")

  # Cleanup
  rm -f "$tmpfile"

  echo "$suggestions"
}

# Parse based on comment type
if [ "$COMMENT_TYPE" = "review" ]; then
  SUGGESTIONS=$(parse_review_comments)
else
  SUGGESTIONS=$(parse_improve_comments)
fi

# Sort suggestions by priority (HIGH > MEDIUM > LOW) then by importance (descending)
SUGGESTIONS=$(echo "$SUGGESTIONS" | jq '
  def priority_order: if . == "HIGH" then 0 elif . == "MEDIUM" then 1 else 2 end;
  sort_by((.priority | priority_order), (-.importance))
')

# Recalculate counts from JSON to handle subshell issues
# (counters inside parse_improve_comments are updated in a while loop subshell)
HIGH_COUNT=$(echo "$SUGGESTIONS" | jq '[.[] | select(.priority == "HIGH")] | length')
MEDIUM_COUNT=$(echo "$SUGGESTIONS" | jq '[.[] | select(.priority == "MEDIUM")] | length')
LOW_COUNT=$(echo "$SUGGESTIONS" | jq '[.[] | select(.priority == "LOW")] | length')
TOTAL_COUNT=$((HIGH_COUNT + MEDIUM_COUNT + LOW_COUNT))

# Build final JSON output
# NOTE: metadata.comment_id is the ONLY comment ID since Qodo posts a single issue comment.
# Individual suggestions do NOT have separate comment_ids (unlike CodeRabbit review comments).
jq -n \
  --arg comment_id "$PROVIDED_COMMENT_ID" \
  --arg comment_type "$COMMENT_TYPE" \
  --arg owner "$OWNER" \
  --arg repo "$REPO" \
  --arg pr_number "$PR_NUMBER" \
  --argjson high "$HIGH_COUNT" \
  --argjson medium "$MEDIUM_COUNT" \
  --argjson low "$LOW_COUNT" \
  --argjson total "$TOTAL_COUNT" \
  --argjson suggestions "$SUGGESTIONS" '
{
  "metadata": {
    "comment_id": $comment_id,
    "comment_type": $comment_type,
    "owner": $owner,
    "repo": $repo,
    "pr_number": $pr_number
  },
  "summary": {
    "high": $high,
    "medium": $medium,
    "low": $low,
    "total": $total
  },
  "suggestions": $suggestions
}
'
