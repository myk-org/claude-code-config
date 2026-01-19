#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract data from JSON
model_name=$(echo "$input" | jq -r '.model.display_name')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')

# Get context usage percentage (pre-calculated by Claude Code v2.1.6+)
context_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Get current directory basename
dir_name=$(basename "$current_dir")

# Build status line components
status_parts=()

# Add directory name
status_parts+=("$dir_name")

# Add SSH info if connected via SSH
if [ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]; then
    status_parts+=("$(whoami)@$(hostname -s)")
fi

# Add git branch if in a git repository
if git rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null || echo "detached")
    status_parts+=("$branch")
fi

# Add virtual environment if active
if [ -n "$VIRTUAL_ENV" ]; then
    status_parts+=("($(basename "$VIRTUAL_ENV"))")
fi

# Add model and context usage
status_parts+=("$model_name")
if [ -n "$context_pct" ]; then
    status_parts+=("(${context_pct}%)")
fi

# Extract lines added/removed
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')

# Add lines added/removed if any changes
if [ "$lines_added" -gt 0 ] 2>/dev/null || [ "$lines_removed" -gt 0 ] 2>/dev/null; then
    status_parts+=("+${lines_added}/-${lines_removed}")
fi

# Join all parts with spaces and output
printf "%s\n" "${status_parts[*]}"
