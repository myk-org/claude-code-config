#!/usr/bin/env bash
set -euo pipefail

# Check dependencies
for cmd in gh jq git; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "❌ Error: Required command '$cmd' is not installed" >&2
        exit 1
    fi
done

# Script: get-claude-md.sh
# Purpose: Fetch CLAUDE.md content for a repository
# Usage: get-claude-md.sh <owner/repo> <pr_number>
#        get-claude-md.sh https://github.com/owner/repo/pull/123
#        get-claude-md.sh <pr_number>

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
  Fetches CLAUDE.md content for a repository.
  Checks local files first if current git repo matches target repo,
  then falls back to GitHub API.

  Output: CLAUDE.md content (or empty if not found)

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

# Function to check if current git repo matches target repo
is_current_repo() {
    # Get current repo's remote URL
    local current_remote
    current_remote=$(git remote get-url origin 2>/dev/null) || return 1

    # Extract owner/repo from remote URL (supports both HTTPS and SSH)
    local current_repo_name=""
    if [[ "$current_remote" =~ github\.com[:/]([^/]+)/([^/]+)(\.git)?$ ]]; then
        current_repo_name="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    else
        return 1
    fi

    # Compare (case-insensitive)
    if [[ "${current_repo_name,,}" == "${REPO_FULL_NAME,,}" ]]; then
        return 0
    else
        return 1
    fi
}

# Function to fetch from GitHub API
fetch_from_github() {
    local file_path="$1"
    local content

    # Use gh api to fetch file content
    content=$(gh api "/repos/$OWNER/$REPO/contents/$file_path" --jq '.content' 2>/dev/null) || return 1

    # Decode base64 content
    echo "$content" | base64 -d 2>/dev/null || return 1

    return 0
}

# Strategy: Check in order, stop on first match
# 1. Check local ./CLAUDE.md if current repo matches
# 2. Check local ./.claude/CLAUDE.md if current repo matches
# 3. Fetch upstream CLAUDE.md from GitHub API
# 4. Fetch upstream .claude/CLAUDE.md from GitHub API
# 5. If nothing found, output empty string and exit 0

if is_current_repo; then
    # Check local ./CLAUDE.md
    if [[ -f "./CLAUDE.md" ]]; then
        cat "./CLAUDE.md"
        exit 0
    fi

    # Check local ./.claude/CLAUDE.md
    if [[ -f "./.claude/CLAUDE.md" ]]; then
        cat "./.claude/CLAUDE.md"
        exit 0
    fi
fi

# Fetch upstream CLAUDE.md
if CLAUDE_MD_CONTENT=$(fetch_from_github "CLAUDE.md"); then
    echo "$CLAUDE_MD_CONTENT"
    exit 0
fi

# Fetch upstream .claude/CLAUDE.md
if CLAUDE_MD_CONTENT=$(fetch_from_github ".claude/CLAUDE.md"); then
    echo "$CLAUDE_MD_CONTENT"
    exit 0
fi

# Nothing found - output empty string and exit 0 (not an error)
echo ""
exit 0
