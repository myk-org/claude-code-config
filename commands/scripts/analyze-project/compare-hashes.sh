#!/usr/bin/env bash
# compare-hashes.sh - Compare current and previous file hashes
# Usage: compare-hashes.sh <current_hashes.json> [previous_hashes.json] [output_file]
# Input: Reads current_hashes.json and previous_hashes.json (if exists)
# Output: Writes changed files to output_file (default: project-specific temp dir from project_info.json), prints JSON summary to stdout
# Exit codes: 0=success, 1=usage error, 2=script error

set -euo pipefail
trap 'echo "ERROR: Script failed at line $LINENO" >&2; exit 2' ERR

# Helper function to get temp_dir from project_info.json
get_temp_dir() {
    local project_info=".analyze-project/project_info.json"
    if [[ -f "$project_info" ]]; then
        # Extract temp_dir from JSON
        grep '"temp_dir"' "$project_info" | sed 's/.*"temp_dir": "//; s/".*//'
    else
        # Fallback: generate hash-based path if project_info doesn't exist yet
        local project_hash=$(echo -n "$PWD" | sha256sum | cut -c1-8)
        echo "/tmp/claude/analyze-project/${project_hash}"
    fi
}

CURRENT_JSON="${1:-.analyze-project/current_hashes.json}"
PREVIOUS_JSON="${2:-.analyze-project/previous_hashes.json}"
TEMP_DIR=$(get_temp_dir)
OUTPUT_FILE="${3:-${TEMP_DIR}/files_to_analyze.txt}"

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Initialize counters
NEW_COUNT=0
CHANGED_COUNT=0
DELETED_COUNT=0
UNCHANGED_COUNT=0

# Clear output file
> "$OUTPUT_FILE"

# If no previous hashes, all files are new
if [[ ! -f "$PREVIOUS_JSON" ]]; then
    # Extract all files from current and write to output
    grep -o '"[^"]*":' "$CURRENT_JSON" | sed 's/"//g; s/://' > "$OUTPUT_FILE"
    NEW_COUNT=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')

    cat <<EOF
{
  "new_files": $NEW_COUNT,
  "changed_files": 0,
  "deleted_files": 0,
  "unchanged_files": 0,
  "files_to_analyze": $NEW_COUNT,
  "is_first_analysis": true
}
EOF
    exit 0
fi

# Create temp files for comparison
CURRENT_SORTED=$(mktemp)
PREVIOUS_SORTED=$(mktemp)
trap "rm -f $CURRENT_SORTED $PREVIOUS_SORTED" EXIT

# Extract and sort file:hash pairs
grep -o '"[^"]*": "[^"]*"' "$CURRENT_JSON" | sort > "$CURRENT_SORTED"
grep -o '"[^"]*": "[^"]*"' "$PREVIOUS_JSON" | sort > "$PREVIOUS_SORTED"

# Find new files (in current, not in previous)
while IFS= read -r line; do
    FILE=$(echo "$line" | sed 's/"//g; s/:.*//')
    echo "$FILE" >> "$OUTPUT_FILE"
    ((NEW_COUNT++)) || true
done < <(comm -23 <(cut -d: -f1 "$CURRENT_SORTED" | sed 's/"//g') <(cut -d: -f1 "$PREVIOUS_SORTED" | sed 's/"//g'))

# Find changed files (same file, different hash)
while IFS= read -r current_line; do
    FILE=$(echo "$current_line" | sed 's/"//g; s/:.*//')
    CURRENT_HASH=$(echo "$current_line" | sed 's/.*: "//; s/"$//')

    # Check if file exists in previous
    PREVIOUS_LINE=$(grep "\"$FILE\":" "$PREVIOUS_SORTED" 2>/dev/null || true)
    if [[ -n "$PREVIOUS_LINE" ]]; then
        PREVIOUS_HASH=$(echo "$PREVIOUS_LINE" | sed 's/.*: "//; s/"$//')
        if [[ "$CURRENT_HASH" != "$PREVIOUS_HASH" ]]; then
            echo "$FILE" >> "$OUTPUT_FILE"
            ((CHANGED_COUNT++)) || true
        else
            ((UNCHANGED_COUNT++)) || true
        fi
    fi
done < "$CURRENT_SORTED"

# Find deleted files (in previous, not in current)
DELETED_COUNT=$(comm -23 <(cut -d: -f1 "$PREVIOUS_SORTED" | sed 's/"//g') <(cut -d: -f1 "$CURRENT_SORTED" | sed 's/"//g') | wc -l | tr -d ' ')

TOTAL_TO_ANALYZE=$((NEW_COUNT + CHANGED_COUNT))

cat <<EOF
{
  "new_files": $NEW_COUNT,
  "changed_files": $CHANGED_COUNT,
  "deleted_files": $DELETED_COUNT,
  "unchanged_files": $UNCHANGED_COUNT,
  "files_to_analyze": $TOTAL_TO_ANALYZE,
  "is_first_analysis": false
}
EOF

exit 0
