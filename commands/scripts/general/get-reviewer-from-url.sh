#!/usr/bin/env bash
set -euo pipefail

# Script to detect which AI reviewer authored a GitHub comment/review
# Usage: get-reviewer-from-url.sh <github-url>
# Input: GitHub URL with fragment (#issuecomment-XXX, #pullrequestreview-XXX, #discussion_rXXX)
# Output: "qodo", "coderabbit", or "human"

# Known AI reviewer usernames
# NOTE: Update these lists when adding new AI reviewer integrations
QODO_USERS="qodo-code-review qodo-code-review[bot]"
CODERABBIT_USERS="coderabbitai coderabbitai[bot]"

usage() {
    echo "Usage: $0 <github-url>" >&2
    echo "" >&2
    echo "Supported URL formats:" >&2
    echo "  https://github.com/owner/repo/pull/123#issuecomment-XXXXXXXXXX" >&2
    echo "  https://github.com/owner/repo/pull/123#pullrequestreview-XXXXXXXXXX" >&2
    echo "  https://github.com/owner/repo/pull/123#discussion_rXXXXXXXXXX" >&2
    exit 1
}

error() {
    echo "Error: $1" >&2
    exit 1
}

# Check required tools
check_dependencies() {
    if ! command -v gh &>/dev/null; then
        error "gh (GitHub CLI) is required but not installed"
    fi
    if ! command -v jq &>/dev/null; then
        error "jq is required but not installed"
    fi
}

# Parse GitHub URL and extract components
parse_url() {
    local url="$1"

    # Remove trailing whitespace (spaces/tabs/newlines)
    url="${url%"${url##*[! $'\t\r\n']}"}"

    # Validate URL format (with optional /files segment)
    if [[ ! "$url" =~ ^https://github\.com/([^/]+)/([^/]+)/pull/([0-9]+)(/files)?#(.+)$ ]]; then
        error "Invalid GitHub URL format: $url"
    fi

    OWNER="${BASH_REMATCH[1]}"
    REPO="${BASH_REMATCH[2]}"
    PR_NUMBER="${BASH_REMATCH[3]}"
    # BASH_REMATCH[4] is optional /files, BASH_REMATCH[5] is fragment
    FRAGMENT="${BASH_REMATCH[5]}"
}

# Get author login from the appropriate API endpoint
get_author() {
    local author=""
    local api_response=""

    if [[ "$FRAGMENT" =~ ^issuecomment-([0-9]+)$ ]]; then
        local comment_id="${BASH_REMATCH[1]}"
        api_response=$(gh api "/repos/${OWNER}/${REPO}/issues/comments/${comment_id}" 2>&1) || {
            error "Failed to fetch issue comment: $api_response"
        }
        author=$(echo "$api_response" | jq -r '.user.login // empty')

    elif [[ "$FRAGMENT" =~ ^pullrequestreview-([0-9]+)$ ]]; then
        local review_id="${BASH_REMATCH[1]}"
        api_response=$(gh api "/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}/reviews/${review_id}" 2>&1) || {
            error "Failed to fetch PR review: $api_response"
        }
        author=$(echo "$api_response" | jq -r '.user.login // empty')

    elif [[ "$FRAGMENT" =~ ^discussion_r([0-9]+)$ ]]; then
        local comment_id="${BASH_REMATCH[1]}"
        api_response=$(gh api "/repos/${OWNER}/${REPO}/pulls/comments/${comment_id}" 2>&1) || {
            error "Failed to fetch discussion comment: $api_response"
        }
        author=$(echo "$api_response" | jq -r '.user.login // empty')

    else
        error "Unrecognized fragment type: #$FRAGMENT"
    fi

    if [[ -z "$author" ]]; then
        error "Could not extract author from API response"
    fi

    echo "$author"
}

# Match author against known AI reviewers
detect_reviewer() {
    local author="$1"

    # Check for Qodo
    for user in $QODO_USERS; do
        if [[ "$author" == "$user" ]]; then
            echo "qodo"
            return
        fi
    done

    # Check for CodeRabbit
    for user in $CODERABBIT_USERS; do
        if [[ "$author" == "$user" ]]; then
            echo "coderabbit"
            return
        fi
    done

    # Human reviewer (not an AI)
    echo "human"
}

main() {
    if [[ $# -ne 1 ]] || [[ -z "$1" ]]; then
        usage
    fi

    check_dependencies
    parse_url "$1"

    local author
    author=$(get_author)

    detect_reviewer "$author"
}

main "$@"
