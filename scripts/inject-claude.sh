#!/usr/bin/env bash
#
# inject-claude.sh - Inject CLAUDE.md content into Claude prompts
#
# Description:
#   This script checks if the CLAUDE.md file exists in the dotfiles repository
#   and outputs its content prefixed with "@CLAUDE.md\n" to signal Claude that
#   this is a file attachment. The script always exits with code 0 to allow
#   prompts to proceed even if the file is not found.
#
# Usage:
#   This script is typically called by Claude's prompt injection mechanism
#   to automatically include project-specific instructions.
#
# Exit Codes:
#   0 - Success (always, even if file not found)
#
# Author: Claude Code
# Date: 2025-10-25

set -euo pipefail

# Configuration
readonly CLAUDE_MD_PATH="$HOME/CLAUDE.md"
readonly FILE_PREFIX="@CLAUDE.md"

# Main execution
main() {
    # Check if CLAUDE.md exists and is readable
    if [[ ! -f "${CLAUDE_MD_PATH}" ]]; then
        # File doesn't exist - exit silently to allow prompt to proceed
        exit 0
    fi

    if [[ ! -r "${CLAUDE_MD_PATH}" ]]; then
        # File exists but is not readable - log to stderr but exit success
        echo "Warning: ${CLAUDE_MD_PATH} exists but is not readable" >&2
        exit 0
    fi

    # Output the file prefix to signal this is a file attachment
    echo "${FILE_PREFIX}"
    echo ""

    # Output the file content
    # Using cat is appropriate here as we need the entire file content
    if ! cat "${CLAUDE_MD_PATH}"; then
        # If cat fails, log error but still exit with success
        echo "Warning: Failed to read ${CLAUDE_MD_PATH}" >&2
        exit 0
    fi

    # Success
    exit 0
}

# Execute main function
main "$@"
