#!/usr/bin/env bash
# cleanup.sh - Clean up project-specific temp directory
# Usage: cleanup.sh [working_dir]
# Default: Uses current working directory
# Can be run before or after analysis
# Exit codes: 0=success, 1=usage error, 2=script error

set -euo pipefail
trap 'echo "ERROR: Script failed at line $LINENO" >&2; exit 2' ERR

WORKING_DIR="${1:-$PWD}"

# Calculate temp_dir the same way init-analysis.sh does
PROJECT_HASH=$(echo -n "$WORKING_DIR" | sha256sum | cut -c1-8)
TEMP_DIR="/tmp/claude/analyze-project/${PROJECT_HASH}"

# Safety check: temp_dir must be under /tmp/claude/
if [[ "$TEMP_DIR" != /tmp/claude/* ]]; then
    echo "ERROR: temp_dir is not under /tmp/claude/: $TEMP_DIR" >&2
    exit 2
fi

# Check if directory exists
if [[ ! -d "$TEMP_DIR" ]]; then
    echo "✅ No temp directory to clean: $TEMP_DIR"
    exit 0
fi

# Remove temp directory
rm -rf "$TEMP_DIR"

echo "✅ Cleaned up temp files: $TEMP_DIR"
exit 0
