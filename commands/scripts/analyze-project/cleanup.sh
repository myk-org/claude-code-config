#!/usr/bin/env bash
# cleanup.sh - Clean up project-specific temp directory
# Usage: cleanup.sh [project_info.json]
# Default: Uses ${PWD}/.analyze-project/project_info.json
# Exit codes: 0=success, 1=usage error, 2=script error

set -euo pipefail
trap 'echo "ERROR: Script failed at line $LINENO" >&2; exit 2' ERR

PROJECT_INFO="${1:-${PWD}/.analyze-project/project_info.json}"

# Check project_info.json exists
if [[ ! -f "$PROJECT_INFO" ]]; then
    echo "ERROR: project_info.json not found: $PROJECT_INFO" >&2
    exit 1
fi

# Extract temp_dir from project_info.json
TEMP_DIR=$(grep -o '"temp_dir": "[^"]*"' "$PROJECT_INFO" | sed 's/"temp_dir": "//; s/"$//')

if [[ -z "$TEMP_DIR" ]]; then
    echo "ERROR: temp_dir not found in $PROJECT_INFO" >&2
    exit 1
fi

# Safety check: temp_dir must be under /tmp/claude/
if [[ "$TEMP_DIR" != /tmp/claude/* ]]; then
    echo "ERROR: temp_dir is not under /tmp/claude/: $TEMP_DIR" >&2
    exit 2
fi

# Check if directory exists
if [[ ! -d "$TEMP_DIR" ]]; then
    echo "⚠️  Temp directory already cleaned: $TEMP_DIR"
    exit 0
fi

# Remove temp directory
rm -rf "$TEMP_DIR"

echo "✅ Cleaned up temp files: $TEMP_DIR"
exit 0
