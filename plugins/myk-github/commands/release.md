---
description: Create a GitHub release with automatic changelog generation
argument-hint: [--dry-run] [--prerelease] [--draft]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion
---

# GitHub Release Command

Creates a GitHub release with automatic changelog generation based on conventional commits.

## Prerequisites Check (MANDATORY)

### Step 1: Check myk-claude-tools

```bash
myk-claude-tools --version
```

If not found, prompt to install: `uv tool install myk-claude-tools`

## Usage

- `/myk-github:release` - Normal release
- `/myk-github:release --dry-run` - Preview without creating
- `/myk-github:release --prerelease` - Create prerelease
- `/myk-github:release --draft` - Create draft release

## Workflow

### Phase 1: Validation

```bash
myk-claude-tools release info
```

Check validations:

- Must be on default branch
- Working tree must be clean
- Must be synced with remote

### Phase 2: Changelog Analysis

Parse commits from the output and categorize by conventional commit type:

- Breaking Changes (MAJOR)
- Features (MINOR)
- Bug Fixes, Docs, Maintenance (PATCH)

Determine version bump and generate changelog.

### Phase 3: User Approval

Display proposed version, changelog preview, and ask for confirmation:

- 'yes' - Proceed
- 'major/minor/patch' - Override version bump
- 'no' - Cancel

### Phase 4: Create Release

Create temp directory with cleanup, write changelog to temp file, and create release:

```bash
mkdir -p /tmp/claude
trap 'rm -f /tmp/claude/release-changelog.md' EXIT
```

Write the changelog content (generated from Phase 2 analysis) to the file, then create the release:

```bash
# Write changelog content to file (use heredoc or echo)
cat > /tmp/claude/release-changelog.md << 'EOF'
<changelog content from Phase 2>
EOF

myk-claude-tools release create {owner}/{repo} {tag} /tmp/claude/release-changelog.md [--prerelease] [--draft]
```

### Phase 5: Summary

Display release URL and summary.
