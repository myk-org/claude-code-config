---
description: Create a GitHub release with automatic changelog generation
argument-hint: [--dry-run] [--prerelease] [--draft] [--target <branch>]
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

Store the detect-versions JSON output for use in Phase 4. The key fields are:

- `version_files[].path` -- file path relative to repo root
- `version_files[].current_version` -- current version string
- `count` -- number of detected files (0 means skip version bumping)

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
- 'exclude N' -- Exclude file by number from the version bump (e.g., 'exclude 2')
- 'no' -- Cancel the release

To exclude files, remove them from the list. Pass remaining file paths as
`--files <path>` arguments to `bump-version` in Phase 5.

**Without version files:**

Same as before -- show proposed version and changelog, ask for confirmation.

### Phase 5: Bump Version (if version files detected)

Skip this phase if no version files were detected in Phase 2.

Run the bump command with the confirmed version and files:

```bash
myk-claude-tools release bump-version <VERSION> --files <file1> --files <file2>
```

Where `<VERSION>` is the version number without `v` prefix (e.g., `1.2.0`, not `v1.2.0`).

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

cat > /tmp/claude/release-changelog.md << 'EOF'
<changelog content from Phase 3>
EOF

myk-claude-tools release create {owner}/{repo} {tag} /tmp/claude/release-changelog.md [--prerelease] [--draft] [--target {target_branch}]
```

### Phase 7: Summary

Display release URL and summary.
If version files were bumped, include the list of updated files in the summary.
