#!/usr/bin/env bash
set -euo pipefail

# Create a GitHub release with the finalized version and changelog
# Dependencies: gh, jq

SCRIPT_NAME="$(basename "$0")"

# Output JSON and exit
json_output() {
    local status="$1"
    shift
    if [[ "$status" == "success" ]]; then
        local tag="$1"
        local url="$2"
        local prerelease="$3"
        local draft="$4"
        jq -n \
            --arg tag "$tag" \
            --arg url "$url" \
            --argjson prerelease "$prerelease" \
            --argjson draft "$draft" \
            '{"status":"success","tag":$tag,"url":$url,"prerelease":$prerelease,"draft":$draft}'
        exit 0
    else
        local error="$1"
        jq -n --arg error "$error" '{"status":"failed","error":$error}'
        exit 1
    fi
}

show_help() {
    cat <<EOF
Usage: $SCRIPT_NAME <owner/repo> <tag> <changelog_file> [options]

Create a GitHub release with the specified tag and changelog.

Arguments:
  owner/repo      Repository in owner/repo format (e.g., myk-org/my-project)
  tag             Release tag (e.g., v1.3.0)
  changelog_file  Path to file containing release notes

Options:
  --target <branch>   Target branch for the release (default: current branch)
  --prerelease        Mark as pre-release
  --draft             Create as draft release
  -h, --help          Show this help message

Examples:
  $SCRIPT_NAME myk-org/my-project v1.3.0 CHANGELOG.md
  $SCRIPT_NAME myk-org/my-project v2.0.0-rc.1 notes.md --prerelease
  $SCRIPT_NAME owner/repo v1.0.0 release.md --draft --target main

Dependencies:
  - gh (GitHub CLI) must be installed and authenticated
  - jq must be installed for JSON output
EOF
}

# Check required dependencies
for cmd in gh jq; do
    if ! command -v "$cmd" &>/dev/null; then
        echo '{"status":"failed","error":"Required command '"'$cmd'"' is not installed"}' >&2
        exit 1
    fi
done

# Show help if explicitly requested (exit 0)
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    show_help
    exit 0
fi

# Error if no arguments provided (exit 1)
if [[ $# -eq 0 ]]; then
    echo "Error: Missing required arguments" >&2
    echo "" >&2
    show_help >&2
    exit 1
fi

# Parse positional arguments
if [[ $# -lt 3 ]]; then
    json_output "failed" "Missing required arguments. Usage: $SCRIPT_NAME <owner/repo> <tag> <changelog_file> [options]"
fi

REPO="$1"
TAG="$2"
CHANGELOG_FILE="$3"
shift 3

# Default values for optional arguments
TARGET_BRANCH=""
PRERELEASE=false
DRAFT=false

# Parse optional arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            if [[ $# -lt 2 ]]; then
                json_output "failed" "--target requires a branch name argument"
            fi
            TARGET_BRANCH="$2"
            shift 2
            ;;
        --prerelease)
            PRERELEASE=true
            shift
            ;;
        --draft)
            DRAFT=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            json_output "failed" "Unknown option: $1"
            ;;
    esac
done

# Validate repository format (owner/repo)
if [[ ! "$REPO" =~ ^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$ ]]; then
    json_output "failed" "Invalid repository format: '$REPO'. Expected format: owner/repo"
fi

# Warn if tag doesn't follow vX.Y.Z format (output to stderr, continue execution)
if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    echo "Warning: Tag '$TAG' does not follow semantic versioning format (vX.Y.Z)" >&2
fi

# Validate changelog file exists
if [[ ! -f "$CHANGELOG_FILE" ]]; then
    json_output "failed" "Changelog file not found: $CHANGELOG_FILE"
fi

# Build gh release create command
GH_CMD=(gh release create "$TAG" --repo "$REPO" --notes-file "$CHANGELOG_FILE")

if [[ -n "$TARGET_BRANCH" ]]; then
    GH_CMD+=(--target "$TARGET_BRANCH")
fi

if [[ "$PRERELEASE" == "true" ]]; then
    GH_CMD+=(--prerelease)
fi

if [[ "$DRAFT" == "true" ]]; then
    GH_CMD+=(--draft)
fi

# Execute gh release create and capture output
GH_OUTPUT=""
set +e
GH_OUTPUT=$("${GH_CMD[@]}" 2>&1)
GH_EXIT_CODE=$?
set -e

if [[ $GH_EXIT_CODE -ne 0 ]]; then
    json_output "failed" "gh release create failed: $GH_OUTPUT"
fi

# Extract URL from gh output (gh outputs the release URL on success)
RELEASE_URL="$GH_OUTPUT"

# If URL is empty, construct it
if [[ -z "$RELEASE_URL" ]]; then
    RELEASE_URL="https://github.com/$REPO/releases/tag/$TAG"
fi

# Output success JSON
json_output "success" "$TAG" "$RELEASE_URL" "$PRERELEASE" "$DRAFT"
