#!/usr/bin/env bash
# calculate-hashes.sh - Calculate SHA256 hashes for files
# Usage: calculate-hashes.sh <file_list> <output_json>
# Input: Reads file list from file_list (default: project-specific temp dir from project_info.json)
# Output: Writes JSON to output_json (default: .analyze-project/current_hashes.json), prints count to stdout
# Exit codes: 0=success, 1=usage error (file not found), 2=script error

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

TEMP_DIR=$(get_temp_dir)
FILE_LIST="${1:-${TEMP_DIR}/all_files.txt}"
OUTPUT_JSON="${2:-.analyze-project/current_hashes.json}"

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT_JSON")"

# Check if file list exists
if [[ ! -f "$FILE_LIST" ]]; then
    echo "Error: File list not found: $FILE_LIST" >&2
    exit 1
fi

# Start JSON object
echo "{" > "$OUTPUT_JSON"

FIRST=true
COUNT=0

while IFS= read -r file; do
    # Skip empty lines
    [[ -z "$file" ]] && continue

    # Skip if file doesn't exist
    [[ ! -f "$file" ]] && continue

    # Calculate hash
    HASH=$(sha256sum "$file" 2>/dev/null | cut -d' ' -f1)

    # Add comma for all but first entry
    if [[ "$FIRST" == "true" ]]; then
        FIRST=false
    else
        echo "," >> "$OUTPUT_JSON"
    fi

    # Write JSON entry (escape the file path for JSON)
    ESCAPED_FILE=$(echo "$file" | sed 's/\\/\\\\/g; s/"/\\"/g')
    printf '  "%s": "%s"' "$ESCAPED_FILE" "$HASH" >> "$OUTPUT_JSON"

    ((COUNT++)) || true
done < "$FILE_LIST"

# Close JSON object
echo "" >> "$OUTPUT_JSON"
echo "}" >> "$OUTPUT_JSON"

echo "$COUNT"

exit 0
