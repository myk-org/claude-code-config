---
description: Create a GitHub release with automatic changelog generation
argument-hint: [--dry-run] [--prerelease] [--draft]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion
---

# GitHub Release Command

Creates a GitHub release with automatic changelog generation based on conventional commits.
Optionally detects and updates version files before creating the release.

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

### Phase 2: Version Detection

```bash
myk-claude-tools release detect-versions
```

Parse the JSON output. If version files are found, store them for Phase 4.
If no version files are detected, skip version bumping phases and continue normally.

### Phase 3: Changelog Analysis

Parse commits from Phase 1 output and categorize by conventional commit type:

- Breaking Changes (MAJOR)
- Features (MINOR)
- Bug Fixes, Docs, Maintenance (PATCH)

Determine version bump and generate changelog.

### Phase 4: User Approval

Display the proposed release information. If version files were detected in Phase 2,
include them in the approval prompt.

**With version files:**

Present using AskUserQuestion. Show:

- Proposed version (e.g., v1.2.0, minor bump)
- List of version files to update with current to new version
- Changelog preview

User options:

- 'yes' -- Proceed with proposed version and all listed files
- 'major/minor/patch' -- Override the version bump type
- User can request to exclude specific files from the version bump
- 'no' -- Cancel the release

**Without version files:**

Same as before -- show proposed version and changelog, ask for confirmation.

### Phase 5: Bump Version (if version files detected)

Skip this phase if no version files were detected in Phase 2.

Run the bump command with the confirmed version and files:

```bash
myk-claude-tools release bump-version <VERSION> --files <file1> --files <file2>
```

Where `<VERSION>` is the version number without `v` prefix (e.g., `1.2.0`).

Then commit and push the version bump:

```bash
git add <updated-files>
git commit -m "chore: bump version to <VERSION>"
git push
```

### Phase 6: Create Release

Create temp directory with cleanup, write changelog to temp file, and create release:

```bash
mkdir -p /tmp/claude
trap 'rm -f /tmp/claude/release-changelog.md' EXIT
```

Write the changelog content (generated from Phase 3 analysis) to the file,
then create the release:

```bash
cat > /tmp/claude/release-changelog.md << 'EOF'
<changelog content from Phase 3>
EOF

myk-claude-tools release create {owner}/{repo} {tag} \
  /tmp/claude/release-changelog.md [--prerelease] [--draft]
```

### Phase 7: Summary

Display release URL and summary.
If version files were bumped, include the list of updated files in the summary.
