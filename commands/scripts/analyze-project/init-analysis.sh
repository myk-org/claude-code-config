#!/usr/bin/env bash
# init-analysis.sh - Initialize project analysis with smart full/incremental detection
# Usage: init-analysis.sh [--full] [working_dir]
# Arguments: --full (optional - force full re-analysis even when previous data exists)
# Output: Updates .analyze-project/project_info.json with analysis settings
# Exit codes: 0=success, 1=usage error, 2=script error

set -euo pipefail
trap 'echo "ERROR: Script failed at line $LINENO" >&2; exit 2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKING_DIR="$PWD"

# Parse arguments
FORCE_FULL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --full)
            FORCE_FULL=true
            shift
            ;;
        *)
            # Assume it's the working directory if it exists
            if [[ -d "$1" ]]; then
                WORKING_DIR="$1"
            fi
            shift
            ;;
    esac
done

# Run detect-project.sh first (creates .analyze-project/ and project_info.json)
"$SCRIPT_DIR/detect-project.sh" "$WORKING_DIR"

# Always use basename of working directory as project name
PROJECT_NAME=$(basename "$WORKING_DIR")
GROUP_ID="$PROJECT_NAME"

# Generate project-specific temp directory using hash of working directory
# This ensures each project gets its own temp space, preventing conflicts
PROJECT_HASH=$(echo -n "$WORKING_DIR" | sha256sum | cut -c1-8)
TEMP_DIR="/tmp/claude/analyze-project/${PROJECT_HASH}"

# Read existing project_info.json and add new fields
PROJECT_INFO="$WORKING_DIR/.analyze-project/project_info.json"
PREVIOUS_HASHES="$WORKING_DIR/.analyze-project/previous_hashes.json"

# Smart detection: Full analysis if no previous data, incremental otherwise
# --full flag overrides this to force full re-analysis
if [[ "$FORCE_FULL" == "true" ]]; then
    IS_FULL_ANALYSIS=true
    FULL_REASON="user_flag"  # User passed --full
elif [[ ! -f "$PREVIOUS_HASHES" ]]; then
    IS_FULL_ANALYSIS=true
    FULL_REASON="no_hashes"  # No previous_hashes.json exists
else
    IS_FULL_ANALYSIS=false
    FULL_REASON="incremental"  # Has previous data, will do incremental
fi

# Use a temp file to update JSON
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

# Read existing JSON and add new fields using sed/awk
# Remove the closing brace, add new fields, close brace
head -n -1 "$PROJECT_INFO" > "$TEMP_FILE"
cat >> "$TEMP_FILE" <<EOF
,
  "project_name": "$PROJECT_NAME",
  "group_id": "$GROUP_ID",
  "is_full_analysis": $IS_FULL_ANALYSIS,
  "full_analysis_reason": "$FULL_REASON",
  "temp_dir": "$TEMP_DIR"
}
EOF

# Write back
mv "$TEMP_FILE" "$PROJECT_INFO"
trap - EXIT  # Remove trap since we moved the file

# Create project-specific temp directory
mkdir -p "$TEMP_DIR"

# Output summary
echo ""
echo "🏷️  Project: $PROJECT_NAME"
echo "📂 Group ID: $GROUP_ID"
if [[ "$IS_FULL_ANALYSIS" == "true" ]]; then
    if [[ "$FULL_REASON" == "user_flag" ]]; then
        echo "🔄 Mode: Full Analysis (--full flag)"
    else
        echo "🔄 Mode: Full Analysis (no previous hashes)"
    fi
else
    echo "🔄 Mode: Incremental Analysis"
fi

exit 0
