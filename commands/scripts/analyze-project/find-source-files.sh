#!/usr/bin/env bash
# find-source-files.sh - Find source files with smart exclusions
# Usage: find-source-files.sh [working_dir] [output_file]
# Input: Reads ${WORKING_DIR}/.analyze-project/project_info.json for all_types and temp_dir
# Output: Writes file list to output_file (default: project-specific temp dir from project_info.json)
# Exit codes: 0=success, 1=usage error, 2=script error

set -euo pipefail
trap 'echo "ERROR: Script failed at line $LINENO" >&2; exit 2' ERR

# Helper function to get temp_dir from project_info.json
get_temp_dir() {
    local working_dir="${1:-$PWD}"
    local project_info="$working_dir/.analyze-project/project_info.json"
    if [[ -f "$project_info" ]]; then
        # Extract temp_dir from JSON
        grep '"temp_dir"' "$project_info" | sed 's/.*"temp_dir": "//; s/".*//'
    else
        # Fallback: generate hash-based path if project_info doesn't exist yet
        local project_hash=$(echo -n "$working_dir" | sha256sum | cut -c1-8)
        echo "/tmp/claude/analyze-project/${project_hash}"
    fi
}

# If no project type specified, try to read from project_info.json
WORKING_DIR="${1:-$PWD}"
TEMP_DIR=$(get_temp_dir "$WORKING_DIR")
OUTPUT_FILE="${2:-${TEMP_DIR}/all_files.txt}"

cd "$WORKING_DIR"

# Try to get project types from project_info.json if it exists
PROJECT_INFO="$WORKING_DIR/.analyze-project/project_info.json"
if [[ -f "$PROJECT_INFO" ]]; then
    # Extract all_types array and convert to comma-separated
    PROJECT_TYPES=$(grep '"all_types"' "$PROJECT_INFO" | sed 's/.*\[//; s/\].*//; s/"//g; s/, */,/g' | tr -d ' ')
else
    PROJECT_TYPES="unknown"
fi

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Common exclusion patterns
EXCLUDES=(
    -not -path '*/node_modules/*'
    -not -path '*/vendor/*'
    -not -path '*/__pycache__/*'
    -not -path '*/.git/*'
    -not -path '*/.venv/*'
    -not -path '*/venv/*'
    -not -path '*/.tox/*'
    -not -path '*/dist/*'
    -not -path '*/build/*'
    -not -path '*/target/*'
    -not -path '*/.gradle/*'
    -not -path '*/out/*'
    -not -path '*/.next/*'
    -not -path '*/.nuxt/*'
    -not -path '*/.cache/*'
    -not -path '*/.eggs/*'
    -not -path '*/*.egg-info/*'
    -not -path '*/.mypy_cache/*'
    -not -path '*/.pytest_cache/*'
    -not -path '*/coverage/*'
    -not -path '*/tmp/*'
    -not -path '*/temp/*'
    -not -name '*.pyc'
    -not -name '*.pyo'
)

# Clear output file
> "$OUTPUT_FILE"

# Process each project type
IFS=',' read -ra TYPES <<< "$PROJECT_TYPES"
for ptype in "${TYPES[@]}"; do
    ptype=$(echo "$ptype" | tr -d ' ')  # Trim whitespace

    case "$ptype" in
        python)
            find . -type f -name '*.py' "${EXCLUDES[@]}" >> "$OUTPUT_FILE"
            ;;
        nodejs|javascript)
            find . -type f \( -name '*.js' -o -name '*.mjs' -o -name '*.cjs' \) "${EXCLUDES[@]}" >> "$OUTPUT_FILE"
            ;;
        typescript)
            find . -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' \) "${EXCLUDES[@]}" >> "$OUTPUT_FILE"
            ;;
        go)
            find . -type f -name '*.go' "${EXCLUDES[@]}" >> "$OUTPUT_FILE"
            ;;
        java)
            find . -type f -name '*.java' "${EXCLUDES[@]}" >> "$OUTPUT_FILE"
            ;;
        rust)
            find . -type f -name '*.rs' "${EXCLUDES[@]}" >> "$OUTPUT_FILE"
            ;;
        markdown)
            find . -type f -name '*.md' "${EXCLUDES[@]}" >> "$OUTPUT_FILE"
            ;;
        unknown|*)
            find . -type f \( -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.go' -o -name '*.java' -o -name '*.rs' -o -name '*.c' -o -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \) "${EXCLUDES[@]}" >> "$OUTPUT_FILE"
            ;;
    esac
done

# Sort and deduplicate
sort -u "$OUTPUT_FILE" -o "$OUTPUT_FILE"

# Count and output
COUNT=$(wc -l < "$OUTPUT_FILE" | tr -d ' ')

# Output summary
echo "📄 File Discovery Complete"
echo "   Types searched: $PROJECT_TYPES"
echo "   Files found: $COUNT"
echo "   Output: $OUTPUT_FILE"

# Also write count to a metadata file
echo "$COUNT" > "$(dirname "$OUTPUT_FILE")/file_count.txt"

exit 0
