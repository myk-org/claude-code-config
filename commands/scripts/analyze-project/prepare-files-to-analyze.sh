#!/usr/bin/env bash
# prepare-files-to-analyze.sh - Prepare the list of files to analyze
# Usage: prepare-files-to-analyze.sh
# Reads: .analyze-project/project_info.json, temp_dir/all_files.txt
# Writes: temp_dir/files_to_analyze.txt
# Output: JSON with mode and count information
# Exit codes: 0=success, 1=usage error, 2=script error

set -euo pipefail
trap 'echo "ERROR: Script failed at line $LINENO" >&2; exit 2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_INFO=".analyze-project/project_info.json"

# Check project_info.json exists
if [[ ! -f "$PROJECT_INFO" ]]; then
    echo "Error: $PROJECT_INFO not found" >&2
    exit 1
fi

# Read values from project_info.json
TEMP_DIR=$(grep '"temp_dir"' "$PROJECT_INFO" | sed 's/.*"temp_dir": "//; s/".*//')
IS_FULL=$(grep '"is_full_analysis"' "$PROJECT_INFO" | grep -q 'true' && echo "true" || echo "false")

ALL_FILES="${TEMP_DIR}/all_files.txt"
FILES_TO_ANALYZE="${TEMP_DIR}/files_to_analyze.txt"

# Check all_files.txt exists
if [[ ! -f "$ALL_FILES" ]]; then
    echo "Error: $ALL_FILES not found" >&2
    exit 1
fi

if [[ "$IS_FULL" == "true" ]]; then
    # Full analysis mode: copy all files
    cp "$ALL_FILES" "$FILES_TO_ANALYZE"
    COUNT=$(wc -l < "$FILES_TO_ANALYZE" | tr -d ' ')

    cat <<EOF
{
  "mode": "full",
  "reason": "full_analysis_mode",
  "files_to_analyze": $COUNT,
  "message": "Full analysis mode: all $COUNT files will be analyzed"
}
EOF
else
    # Incremental mode: run compare-hashes.sh
    # compare-hashes.sh writes to files_to_analyze.txt and outputs JSON
    "${SCRIPT_DIR}/compare-hashes.sh"
fi

exit 0
