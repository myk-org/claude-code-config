#!/usr/bin/env bash
set -euo pipefail

# get-release-info.sh - Fetch all information needed for release analysis
# Usage: get-release-info.sh [--repo owner/repo]

# Temp files for cleanup
COMMITS_FILE=""
META_FILE=""

cleanup() {
    [[ -n "$COMMITS_FILE" && -f "$COMMITS_FILE" ]] && rm -f "$COMMITS_FILE"
    [[ -n "$META_FILE" && -f "$META_FILE" ]] && rm -f "$META_FILE"
    return 0
}
trap cleanup EXIT

# Check dependencies
check_dependencies() {
    local missing=()
    for cmd in gh jq git; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "{\"error\": \"Missing dependencies: ${missing[*]}\"}"
        exit 1
    fi
}

# Show usage
usage() {
    cat <<EOF
Usage: $(basename "$0") [--repo owner/repo]

Fetch release information for a GitHub repository.

Options:
  --repo owner/repo    Specify repository (default: detect from git context)
  -h, --help           Show this help message

Output: JSON with metadata, tags, and commits since last tag.
EOF
}

# Parse arguments
REPO=""
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --repo)
                if [[ -z "${2:-}" ]]; then
                    echo "{\"error\": \"--repo requires a value\"}"
                    exit 1
                fi
                REPO="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "{\"error\": \"Unknown argument: $1\"}"
                exit 1
                ;;
        esac
    done
}

# Detect repository from git context
detect_repo() {
    if [[ -n "$REPO" ]]; then
        echo "$REPO"
        return
    fi

    # Use gh repo view to get the repository
    local repo_info
    if ! repo_info=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null); then
        echo ""
        return
    fi
    echo "$repo_info"
}

# Get last tag
get_last_tag() {
    git describe --tags --abbrev=0 2>/dev/null || echo ""
}

# Get all recent tags (last 10, sorted by version)
get_all_tags() {
    local tags
    tags=$(git tag --sort=-v:refname 2>/dev/null | head -10)
    if [[ -z "$tags" ]]; then
        echo "[]"
    else
        echo "$tags" | jq -R -s 'split("\n") | map(select(length > 0))'
    fi
}

# Perform release prerequisite validations
# Sets global validation variables
perform_validations() {
    local default_branch="$1"
    local current_branch="$2"

    # 1. Default Branch Check
    ON_DEFAULT_BRANCH="false"
    if [[ "$current_branch" == "$default_branch" ]]; then
        ON_DEFAULT_BRANCH="true"
    fi

    # 2. Clean Working Tree Check
    WORKING_TREE_CLEAN="true"
    DIRTY_FILES=""
    if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
        WORKING_TREE_CLEAN="false"
        DIRTY_FILES=$(git status --porcelain 2>/dev/null | head -10)
    fi

    # 3. Remote Sync Check
    # Try to fetch from remote (quietly)
    FETCH_SUCCESSFUL="true"
    if ! git fetch origin "$default_branch" --quiet 2>/dev/null; then
        FETCH_SUCCESSFUL="false"
        # Can't verify sync status without fetch
        SYNCED_WITH_REMOTE="false"
        UNPUSHED_COMMITS="0"
        BEHIND_REMOTE="0"
    else
        # Check for unpushed commits
        UNPUSHED_COMMITS=$(git rev-list "origin/${default_branch}..${default_branch}" --count 2>/dev/null || echo "0")

        # Check if behind remote
        BEHIND_REMOTE=$(git rev-list "${default_branch}..origin/${default_branch}" --count 2>/dev/null || echo "0")

        SYNCED_WITH_REMOTE="true"
        if [[ "$UNPUSHED_COMMITS" -gt 0 ]] || [[ "$BEHIND_REMOTE" -gt 0 ]]; then
            SYNCED_WITH_REMOTE="false"
        fi
    fi

    # Calculate all_passed (requires fetch success to verify sync status)
    ALL_VALIDATIONS_PASSED="false"
    if [[ "$FETCH_SUCCESSFUL" == "true" ]] && \
       [[ "$ON_DEFAULT_BRANCH" == "true" ]] && \
       [[ "$WORKING_TREE_CLEAN" == "true" ]] && \
       [[ "$SYNCED_WITH_REMOTE" == "true" ]]; then
        ALL_VALIDATIONS_PASSED="true"
    fi
}

# Get commits since tag and write to files
# Writes commits JSON to COMMITS_FILE and metadata to META_FILE
get_commits() {
    local last_tag="$1"
    local range
    local is_first_release="false"

    if [[ -z "$last_tag" ]]; then
        # First release - get all commits (limited to 100)
        range="HEAD"
        is_first_release="true"
    else
        range="${last_tag}..HEAD"
    fi

    # Create temp files in project-standard temp directory
    mkdir -p /tmp/claude
    COMMITS_FILE=$(mktemp /tmp/claude/commits.XXXXXX)
    META_FILE=$(mktemp /tmp/claude/meta.XXXXXX)

    local commit_count=0
    echo "[" > "$COMMITS_FILE"
    local first="true"

    while IFS= read -r line; do
        if [[ -z "$line" ]]; then
            continue
        fi

        # Parse the commit line using ASCII Unit Separator (0x1F) as delimiter
        # This control character cannot appear in commit messages
        # Format: hash<US>short_hash<US>subject<US>author<US>date
        local hash short_hash subject author date body
        hash=$(echo "$line" | awk -F$'\x1F' '{print $1}')
        short_hash=$(echo "$line" | awk -F$'\x1F' '{print $2}')
        subject=$(echo "$line" | awk -F$'\x1F' '{print $3}')
        author=$(echo "$line" | awk -F$'\x1F' '{print $4}')
        date=$(echo "$line" | awk -F$'\x1F' '{print $5}')

        # Get commit body separately (everything after first line of message)
        body=$(git log -1 --format='%b' "$hash" 2>/dev/null | tr '\n' ' ' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//')

        # Add comma separator for all but first
        if [[ "$first" == "true" ]]; then
            first="false"
        else
            echo "," >> "$COMMITS_FILE"
        fi

        # Output JSON object using jq for proper escaping
        jq -n \
            --arg hash "$hash" \
            --arg short_hash "$short_hash" \
            --arg subject "$subject" \
            --arg body "$body" \
            --arg author "$author" \
            --arg date "$date" \
            '{hash: $hash, short_hash: $short_hash, subject: $subject, body: $body, author: $author, date: $date}' >> "$COMMITS_FILE"

        ((commit_count++)) || true
    done < <(git log --format='%H%x1F%h%x1F%s%x1F%an%x1F%ai' -n 100 "$range" 2>/dev/null || true)

    echo "]" >> "$COMMITS_FILE"

    # Write metadata to separate file
    echo "${commit_count}:${is_first_release}" > "$META_FILE"
}

# Main function
main() {
    check_dependencies
    parse_args "$@"

    # Detect repository
    local full_repo
    full_repo=$(detect_repo)

    if [[ -z "$full_repo" ]]; then
        echo "{\"error\": \"Could not determine repository. Use --repo owner/repo or run from a git repository.\"}"
        exit 1
    fi

    # Parse owner and repo
    local owner repo
    owner=$(echo "$full_repo" | cut -d'/' -f1)
    repo=$(echo "$full_repo" | cut -d'/' -f2)

    # Get branch info
    local current_branch default_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    default_branch=$(gh repo view --json defaultBranchRef -q '.defaultBranchRef.name' 2>/dev/null || echo "main")

    # Perform release prerequisite validations (before collecting commit data)
    perform_validations "$default_branch" "$current_branch"

    # Early return if validations failed - skip expensive commit collection
    if [[ "$ALL_VALIDATIONS_PASSED" == "false" ]]; then
        jq -n \
            --arg owner "$owner" \
            --arg repo "$repo" \
            --arg current_branch "$current_branch" \
            --arg default_branch "$default_branch" \
            --argjson on_default_branch "$ON_DEFAULT_BRANCH" \
            --argjson working_tree_clean "$WORKING_TREE_CLEAN" \
            --arg dirty_files "$DIRTY_FILES" \
            --argjson fetch_successful "$FETCH_SUCCESSFUL" \
            --argjson synced_with_remote "$SYNCED_WITH_REMOTE" \
            --argjson unpushed_commits "$UNPUSHED_COMMITS" \
            --argjson behind_remote "$BEHIND_REMOTE" \
            --argjson all_passed false \
            '{
                metadata: {
                    owner: $owner,
                    repo: $repo,
                    current_branch: $current_branch,
                    default_branch: $default_branch
                },
                validations: {
                    on_default_branch: $on_default_branch,
                    default_branch: $default_branch,
                    current_branch: $current_branch,
                    working_tree_clean: $working_tree_clean,
                    dirty_files: $dirty_files,
                    fetch_successful: $fetch_successful,
                    synced_with_remote: $synced_with_remote,
                    unpushed_commits: $unpushed_commits,
                    behind_remote: $behind_remote,
                    all_passed: $all_passed
                },
                last_tag: null,
                all_tags: [],
                commits: [],
                commit_count: 0,
                is_first_release: null
            }'
        exit 0
    fi

    # Validations passed - proceed with expensive operations
    # Get last tag
    local last_tag
    last_tag=$(get_last_tag)

    # Get all tags
    local all_tags
    all_tags=$(get_all_tags)

    # Get commits (writes to COMMITS_FILE and META_FILE)
    get_commits "$last_tag"

    # Read commits and metadata
    local commits_json commit_count is_first_release meta_data
    commits_json=$(cat "$COMMITS_FILE")
    meta_data=$(cat "$META_FILE")
    commit_count=$(echo "$meta_data" | cut -d':' -f1)
    is_first_release=$(echo "$meta_data" | cut -d':' -f2)

    # Build final JSON output
    # Prepare last_tag as JSON value: null if empty, quoted string otherwise
    local last_tag_json
    if [[ -z "$last_tag" ]]; then
        last_tag_json="null"
    else
        last_tag_json="\"$last_tag\""
    fi

    jq -n \
        --arg owner "$owner" \
        --arg repo "$repo" \
        --arg current_branch "$current_branch" \
        --arg default_branch "$default_branch" \
        --argjson on_default_branch "$ON_DEFAULT_BRANCH" \
        --argjson working_tree_clean "$WORKING_TREE_CLEAN" \
        --arg dirty_files "$DIRTY_FILES" \
        --argjson fetch_successful "$FETCH_SUCCESSFUL" \
        --argjson synced_with_remote "$SYNCED_WITH_REMOTE" \
        --argjson unpushed_commits "$UNPUSHED_COMMITS" \
        --argjson behind_remote "$BEHIND_REMOTE" \
        --argjson all_passed "$ALL_VALIDATIONS_PASSED" \
        --argjson last_tag "$last_tag_json" \
        --argjson all_tags "$all_tags" \
        --argjson commits "$commits_json" \
        --argjson commit_count "$commit_count" \
        --argjson is_first_release "$is_first_release" \
        '{
            metadata: {
                owner: $owner,
                repo: $repo,
                current_branch: $current_branch,
                default_branch: $default_branch
            },
            validations: {
                on_default_branch: $on_default_branch,
                default_branch: $default_branch,
                current_branch: $current_branch,
                working_tree_clean: $working_tree_clean,
                dirty_files: $dirty_files,
                fetch_successful: $fetch_successful,
                synced_with_remote: $synced_with_remote,
                unpushed_commits: $unpushed_commits,
                behind_remote: $behind_remote,
                all_passed: $all_passed
            },
            last_tag: $last_tag,
            all_tags: $all_tags,
            commits: $commits,
            commit_count: $commit_count,
            is_first_release: $is_first_release
        }'
}

main "$@"
