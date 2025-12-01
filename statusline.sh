#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract data from JSON
model_name=$(echo "$input" | jq -r '.model.display_name')
output_style=$(echo "$input" | jq -r '.output_style.name')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')

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

# Add model and output style
status_parts+=("$model_name")
status_parts+=("$output_style")

# Join all parts with spaces and output
printf "%s\n" "${status_parts[*]}"