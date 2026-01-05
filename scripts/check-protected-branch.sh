#!/bin/bash
# Check if current branch is a protected branch (main or master)
# Exit 0: NOT on protected branch (safe to proceed)
# Exit 1: ON protected branch (should ask orchestrator)

set -e

CURRENT_BRANCH=$(git branch --show-current)

# Handle detached HEAD
if [ -z "$CURRENT_BRANCH" ]; then
    echo "⚠️ WARNING: In detached HEAD state"
    exit 0  # Not on a protected branch
fi

# Check if on main or master
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    echo "⛔ ERROR: On protected branch '$CURRENT_BRANCH'"
    echo ""
    echo "Direct commits to $CURRENT_BRANCH should be avoided."
    echo ""
    echo "To proceed:"
    echo "1. Ask the orchestrator for guidance"
    echo "2. Or create a feature branch: git checkout -b feature/your-feature"
    echo ""
    exit 1
fi

echo "✅ Not on protected branch - OK to proceed"
exit 0
