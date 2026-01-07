#!/bin/bash
# Check if current branch is already merged into main/master
# Exit 0: Branch NOT merged (safe to proceed)
# Exit 1: Branch IS merged (refuse operation)

set -e

CURRENT_BRANCH=$(git branch --show-current)

# Handle detached HEAD
if [ -z "$CURRENT_BRANCH" ]; then
    echo "⚠️ WARNING: In detached HEAD state"
    exit 0  # Allow - not a merged branch issue
fi

# Skip check if on main/master (handled by other protection)
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    echo "On $CURRENT_BRANCH branch"
    exit 0  # Let other protection handle this
fi

# Detect main branch (prefer remote for accuracy)
MAIN_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$MAIN_BRANCH" ]; then
    if git show-ref --verify --quiet refs/heads/main 2>/dev/null; then
        MAIN_BRANCH="main"
    elif git show-ref --verify --quiet refs/heads/master 2>/dev/null; then
        MAIN_BRANCH="master"
    else
        MAIN_BRANCH="main"
    fi
fi

# Use remote main if available for accurate merge detection
REMOTE_MAIN="origin/$MAIN_BRANCH"
if git rev-parse --verify "$REMOTE_MAIN" >/dev/null 2>&1; then
    TARGET_BRANCH="$REMOTE_MAIN"
else
    TARGET_BRANCH="$MAIN_BRANCH"
fi

# If branch HEAD equals target HEAD exactly, it's a fresh branch (just created)
BRANCH_HEAD=$(git rev-parse "$CURRENT_BRANCH")
TARGET_HEAD=$(git rev-parse "$TARGET_BRANCH")

if [ "$BRANCH_HEAD" = "$TARGET_HEAD" ]; then
    echo "✅ Branch '$CURRENT_BRANCH' is at same point as $TARGET_BRANCH - fresh branch, OK to proceed"
    exit 0
fi

# Check if current branch is ancestor of main (meaning it's merged)
if git merge-base --is-ancestor "$CURRENT_BRANCH" "$TARGET_BRANCH" 2>/dev/null; then
    echo "⛔ ERROR: Branch '$CURRENT_BRANCH' has already been merged into $TARGET_BRANCH"
    echo ""
    echo "This branch is STALE. Committing here would create confusion."
    echo ""
    echo "To proceed:"
    echo "1. Checkout main: git checkout main && git pull"
    echo "2. Create new branch: git checkout -b feature/your-new-feature"
    echo ""
    exit 1
fi

echo "✅ Branch '$CURRENT_BRANCH' is not merged - OK to proceed"
exit 0
