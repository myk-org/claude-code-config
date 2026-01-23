#!/usr/bin/env bash
set -euo pipefail

# Secure temp file creation
umask 077

# Unified script to fetch ALL unresolved review threads from a PR
# and categorize them by source (human, qodo, coderabbit)
#
# Usage: get-all-github-unresolved-reviews-for-pr.sh [review_url]
#
# Arguments:
#   review_url  Optional: specific review URL for context
#               (e.g., #pullrequestreview-XXX or #discussion_rXXX)
#
# Output: JSON with metadata and categorized comments
#
# Dependencies: gh, jq, get-pr-info.sh (in same directory)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PR_INFO_SCRIPT="$SCRIPT_DIR/get-pr-info.sh"

# Track temp files for cleanup
declare -a TEMP_FILES=()

# Cleanup function for trap
# Removes tracked temp files and any orphaned .new files from atomic updates
cleanup() {
  for f in "${TEMP_FILES[@]:-}"; do
    rm -f "$f" "${f}.new" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

# Known AI reviewer usernames (keep in sync with get-reviewer-from-url.sh)
QODO_USERS=("qodo-code-review" "qodo-code-review[bot]")
CODERABBIT_USERS=("coderabbitai" "coderabbitai[bot]")

show_usage() {
    echo "Usage: $0 [review_url]" >&2
    echo "" >&2
    echo "Fetches ALL unresolved review threads from the current PR" >&2
    echo "and categorizes them by source (human, qodo, coderabbit)." >&2
    echo "" >&2
    echo "Arguments:" >&2
    echo "  review_url  Optional: specific review URL for context" >&2
    echo "" >&2
    echo "Output:" >&2
    echo "  JSON with metadata and categorized comments" >&2
    echo "  Also saves to /tmp/claude/pr-<number>-reviews.json" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  $0" >&2
    echo "  $0 https://github.com/org/repo/pull/123#pullrequestreview-456" >&2
    exit 1
}

# Check required dependencies
check_dependencies() {
    for cmd in gh jq; do
        if ! command -v "$cmd" &>/dev/null; then
            echo "Error: '$cmd' is required but not installed." >&2
            exit 1
        fi
    done

    if [ ! -f "$PR_INFO_SCRIPT" ]; then
        echo "Error: PR info script not found: $PR_INFO_SCRIPT" >&2
        exit 1
    fi
}

# Detect source from author login
# Returns: "qodo", "coderabbit", or "human"
detect_source() {
    local author="$1"

    # Check for Qodo
    for user in "${QODO_USERS[@]}"; do
        if [[ "$author" == "$user" ]]; then
            echo "qodo"
            return
        fi
    done

    # Check for CodeRabbit
    for user in "${CODERABBIT_USERS[@]}"; do
        if [[ "$author" == "$user" ]]; then
            echo "coderabbit"
            return
        fi
    done

    echo "human"
}

# Classify priority from comment body
# Returns: "HIGH", "MEDIUM", or "LOW"
# Uses bash native lowercase expansion and here-strings (no subshells)
classify_priority() {
    local body="$1"
    local body_lower="${body,,}"

    # HIGH: security, bugs, critical issues
    if grep -qE '(security|vulnerability|critical|bug|error|crash|must|required|breaking|urgent|injection|xss|csrf|auth)' <<< "$body_lower"; then
        echo "HIGH"
        return
    fi

    # LOW: style, formatting, minor
    if grep -qE '(style|formatting|typo|nitpick|nit:|minor|optional|cosmetic|whitespace|indentation)' <<< "$body_lower"; then
        echo "LOW"
        return
    fi

    # MEDIUM: improvements, suggestions (or default)
    echo "MEDIUM"
}

# Fetch all unresolved review threads using paginated GraphQL
# Returns JSON array of unresolved threads
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
                                    comments(first: 100) {
                                        nodes {
                                            id
                                            databaseId
                                            author { login }
                                            path
                                            line
                                            body
                                            createdAt
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
                                    comments(first: 100) {
                                        nodes {
                                            id
                                            databaseId
                                            author { login }
                                            path
                                            line
                                            body
                                            createdAt
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

        # Guard against GraphQL errors / non-JSON output (gh may exit 0 with .errors)
        if ! echo "$raw_result" | jq -e . >/dev/null 2>&1; then
            echo "Warning: GraphQL returned non-JSON response (page $page_count)" >&2
            break
        fi
        if echo "$raw_result" | jq -e '.errors? | length > 0' >/dev/null 2>&1; then
            echo "Warning: GraphQL errors while fetching review threads (page $page_count): $(echo "$raw_result" | jq -r '.errors[0].message // "Unknown error"')" >&2
            break
        fi

        # Extract pagination info
        has_next_page=$(echo "$raw_result" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage // false')
        cursor=$(echo "$raw_result" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // ""')

        # Extract threads from this page and accumulate
        # Use temp files to avoid "Argument list too long" error with large JSON
        local page_threads
        page_threads=$(echo "$raw_result" | jq '.data.repository.pullRequest.reviewThreads.nodes // []')

        local tmp_existing tmp_new
        tmp_existing=$(mktemp)
        tmp_new=$(mktemp)
        TEMP_FILES+=("$tmp_existing" "$tmp_new")
        printf '%s' "$all_threads" >"$tmp_existing"
        printf '%s' "$page_threads" >"$tmp_new"
        all_threads=$(jq -s '.[0] + .[1]' "$tmp_existing" "$tmp_new")
        rm -f "$tmp_existing" "$tmp_new"

        if [ "$has_next_page" = "true" ]; then
            echo "Fetching page $((page_count + 1)) of review threads..." >&2
        fi
    done

    if [ "$page_count" -gt 1 ]; then
        echo "Fetched $page_count pages of review threads" >&2
    fi

    # Filter unresolved threads and extract first comment details with replies
    echo "$all_threads" | jq '
        [.[] |
         select(.isResolved == false) |
         . as $thread |
         (.comments.nodes // []) as $all_comments |
         select(($all_comments | length) > 0) |
         ($all_comments[0]) as $first |
         ($all_comments[1:]) as $rest |
         {
             thread_id: $thread.id,
             node_id: ($first.id // null),
             comment_id: ($first.databaseId // null),
             author: ($first.author.login // null),
             path: ($first.path // null),
             line: ($first.line // null),
             body: ($first.body // ""),
             replies: [$rest[] | {
                 author: (.author.login // null),
                 body: (.body // ""),
                 created_at: (.createdAt // null)
             }]
         }]
    '
}

# Fetch a specific review thread by discussion ID
fetch_specific_discussion() {
    local owner="$1"
    local repo="$2"
    local pr_number="$3"
    local discussion_id="$4"

    local result
    if ! result=$(gh api "/repos/$owner/$repo/pulls/$pr_number/comments/$discussion_id" 2>&1); then
        echo "Warning: Could not fetch discussion $discussion_id: $result" >&2
        echo "[]"
        return 0
    fi

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
    if ! result=$(gh api --paginate "/repos/$owner/$repo/pulls/$pr_number/reviews/$review_id/comments" 2>&1); then
        echo "Warning: Could not fetch review $review_id comments: $result" >&2
        echo "[]"
        return 0
    fi

    # NOTE: gh api --paginate outputs multiple JSON arrays concatenated, so we use jq -s 'add' to merge them
    echo "$result" | jq -s 'add // [] | [.[] | {
        thread_id: null,
        node_id: .node_id,
        comment_id: .id,
        author: .user.login,
        path: .path,
        line: .line,
        body: .body
    }]'
}

# Process threads: add source and priority, categorize
# Single jq pass for all enrichment and categorization (no shell loops or temp files)
process_and_categorize() {
    local threads_json="$1"

    # Validate input JSON early to avoid jq hard-fail
    if ! jq -e . >/dev/null 2>&1 <<<"$threads_json"; then
        jq -n '{human: [], qodo: [], coderabbit: []}'
        return 0
    fi

    local threads_file
    threads_file="$(mktemp)"
    TEMP_FILES+=("$threads_file")
    printf '%s' "$threads_json" >"$threads_file"

    jq -n \
      --slurpfile threads "$threads_file" \
      --argjson qodo_users '["qodo-code-review","qodo-code-review[bot]"]' \
      --argjson coderabbit_users '["coderabbitai","coderabbitai[bot]"]' '
      def detect_source($a):
        if ($qodo_users | index($a)) != null then "qodo"
        elif ($coderabbit_users | index($a)) != null then "coderabbit"
        else "human" end;

      def classify_priority($b):
        ($b | ascii_downcase) as $t
        | if ($t | test("(security|vulnerability|critical|bug|error|crash|must|required|breaking|urgent|injection|xss|csrf|auth)")) then "HIGH"
          elif ($t | test("(style|formatting|typo|nitpick|nit:|minor|optional|cosmetic|whitespace|indentation)")) then "LOW"
          else "MEDIUM" end;

      ($threads[0]
       | map(
           . as $x
           | ($x.author // "") as $author
           | ($x.body // "") as $body
           | (detect_source($author)) as $source
           | (classify_priority($body)) as $priority
           | $x + {source: $source, priority: $priority, reply: null, status: "pending"}
         )
      ) as $enriched
      | {
          human: ($enriched | map(select(.source == "human"))),
          qodo: ($enriched | map(select(.source == "qodo"))),
          coderabbit: ($enriched | map(select(.source == "coderabbit")))
        }'
}

main() {
    # Handle help flag
    if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
        show_usage
    fi

    check_dependencies

    local review_url="${1:-}"

    # Get PR info
    echo "Getting PR information..." >&2
    local pr_info
    if ! pr_info=$("$PR_INFO_SCRIPT" 2>&1); then
        echo "Error: Failed to get PR information: $pr_info" >&2
        exit 1
    fi

    # Parse PR info output
    local repo_full_name pr_number
    read -r repo_full_name pr_number _rest <<<"$pr_info"

    if [ -z "${repo_full_name:-}" ] || [ -z "${pr_number:-}" ]; then
        echo "Error: Invalid PR info output: '$pr_info'" >&2
        echo "Expected format: 'owner/repo pr_number'" >&2
        exit 1
    fi

    if ! [[ "$pr_number" =~ ^[0-9]+$ ]]; then
        echo "Error: PR number must be numeric, got: '$pr_number'" >&2
        exit 1
    fi

    local owner repo
    owner=$(echo "$repo_full_name" | cut -d'/' -f1)
    repo=$(echo "$repo_full_name" | cut -d'/' -f2)

    if [ -z "$owner" ] || [ -z "$repo" ]; then
        echo "Error: Could not parse owner/repo from: '$repo_full_name'" >&2
        exit 1
    fi

    echo "Repository: $owner/$repo, PR: $pr_number" >&2

    # Ensure output directory exists
    local tmp_base="${TMPDIR:-/tmp}"
    local out_dir="${tmp_base%/}/claude"
    if [ ! -d "$out_dir" ]; then
      mkdir -p -m 700 "$out_dir"
    else
      chmod 700 "$out_dir" 2>/dev/null || true
    fi

    local json_path="${out_dir}/pr-${pr_number}-reviews.json"

    # Fetch all unresolved threads
    echo "Fetching unresolved review threads..." >&2
    local all_threads
    all_threads=$(fetch_unresolved_threads "$owner" "$repo" "$pr_number")
    local thread_count
    thread_count=$(printf '%s' "$all_threads" | jq -r 'length' 2>/dev/null || printf '0')
    echo "Found $thread_count unresolved thread(s)" >&2

    # If review URL provided, also fetch specific thread(s)
    local specific_threads='[]'
    if [ -n "$review_url" ]; then
        if [[ "$review_url" =~ pullrequestreview-([0-9]+) ]]; then
            local review_id="${BASH_REMATCH[1]}"
            echo "Fetching comments from PR review $review_id..." >&2
            specific_threads=$(fetch_review_comments "$owner" "$repo" "$pr_number" "$review_id")
            local specific_count
            specific_count=$(echo "$specific_threads" | jq 'length')
            echo "Found $specific_count comment(s) from review $review_id" >&2

        elif [[ "$review_url" =~ discussion_r([0-9]+) ]]; then
            local discussion_id="${BASH_REMATCH[1]}"
            echo "Fetching discussion $discussion_id..." >&2
            specific_threads=$(fetch_specific_discussion "$owner" "$repo" "$pr_number" "$discussion_id")
            local specific_count
            specific_count=$(echo "$specific_threads" | jq 'length')
            echo "Found $specific_count comment(s) from discussion $discussion_id" >&2

        elif [[ "$review_url" =~ issuecomment-([0-9]+) ]]; then
            echo "Note: Issue comments (#issuecomment-*) are not review threads, skipping specific fetch" >&2

        elif [[ "$review_url" =~ ^[0-9]+$ ]]; then
            # Raw numeric review ID (e.g., "12345")
            local review_id="$review_url"
            echo "Fetching comments from PR review $review_id (raw ID)..." >&2
            specific_threads=$(fetch_review_comments "$owner" "$repo" "$pr_number" "$review_id")
            local specific_count
            specific_count=$(echo "$specific_threads" | jq 'length')
            echo "Found $specific_count comment(s) from review $review_id" >&2

        else
            echo "Warning: Unrecognized URL fragment in: $review_url" >&2
        fi
    fi

    # Merge specific threads with all threads, deduplicating by prioritized keys
    # Uses temp files to avoid "Argument list too long" error with large JSON
    if [ "$(printf '%s' "$specific_threads" | jq -e 'length' 2>/dev/null || echo 0)" -gt 0 ]; then
        local tmp_all tmp_specific merged_threads
        tmp_all=$(mktemp)
        tmp_specific=$(mktemp)
        TEMP_FILES+=("$tmp_all" "$tmp_specific")
        printf '%s' "$all_threads" > "$tmp_all"
        printf '%s' "$specific_threads" > "$tmp_specific"
        merged_threads=$(jq -s '
            def key:
              if (.thread_id? and .thread_id != null and .thread_id != "") then "t:" + .thread_id
              elif (.node_id? and .node_id != null and .node_id != "") then "n:" + .node_id
              elif (.comment_id? and .comment_id != null) then "c:" + (.comment_id|tostring)
              else null end;

            (.[0] | map(key) | map(select(. != null))) as $existing_keys |
            .[0] + [.[1][] | select(key as $k | $k == null or ($existing_keys | index($k)) == null)]
        ' "$tmp_all" "$tmp_specific")
        rm -f "$tmp_all" "$tmp_specific"
        all_threads="$merged_threads"
    fi

    # Process and categorize threads
    echo "Categorizing threads by source..." >&2
    local categorized
    categorized=$(process_and_categorize "$all_threads")

    # Build final output
    local final_output
    final_output=$(jq -n \
        --arg owner "$owner" \
        --arg repo "$repo" \
        --arg pr_number "$pr_number" \
        --arg json_path "$json_path" \
        --argjson categorized "$categorized" \
        '{
            metadata: {
                owner: $owner,
                repo: $repo,
                pr_number: $pr_number,
                json_path: $json_path
            },
            human: $categorized.human,
            qodo: $categorized.qodo,
            coderabbit: $categorized.coderabbit
        }')

    # Save to file atomically
    local tmp_json_path
    tmp_json_path="$(mktemp "${out_dir}/pr-${pr_number}-reviews.json.XXXXXX")"
    TEMP_FILES+=("$tmp_json_path")

    echo "$final_output" > "$tmp_json_path"
    mv -f "$tmp_json_path" "$json_path"
    echo "Saved to: $json_path" >&2

    # Count by category
    local human_count qodo_count coderabbit_count
    human_count=$(echo "$final_output" | jq '.human | length')
    qodo_count=$(echo "$final_output" | jq '.qodo | length')
    coderabbit_count=$(echo "$final_output" | jq '.coderabbit | length')
    echo "Categories: human=$human_count, qodo=$qodo_count, coderabbit=$coderabbit_count" >&2

    # Output to stdout
    echo "$final_output"
}

main "$@"
