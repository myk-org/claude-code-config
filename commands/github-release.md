---
skipConfirmation: true
---

# GitHub Release Command

**Description:** Creates a GitHub release with automatic changelog generation and semantic versioning based on conventional commits.

---

## CRITICAL: SESSION ISOLATION

**THIS PROMPT DEFINES A STRICT, SELF-CONTAINED WORKFLOW THAT MUST BE FOLLOWED EXACTLY:**

1. **IGNORE ALL PREVIOUS CONTEXT**: Previous conversations, tasks, or commands in this session are IRRELEVANT
2. **START FRESH**: This prompt creates a NEW workflow that starts from Phase 1 and follows the exact sequence below
3. **NO ASSUMPTIONS**: Do NOT assume any steps have been completed - follow the workflow from the beginning
4. **MANDATORY CHECKPOINTS**: Each phase MUST complete fully before proceeding to the next phase
5. **REQUIRED CONFIRMATIONS**: User approval in Phase 3 is MANDATORY - NEVER skip it

**If this prompt is called multiple times in a session, treat EACH invocation as a completely independent workflow.**

---

## Usage

- `/github-release` - Normal release (determines version from commits)
- `/github-release --dry-run` - Preview without creating release
- `/github-release --prerelease` - Create a pre-release
- `/github-release --draft` - Create a draft release
- `/github-release --dry-run --prerelease` - Preview a pre-release
- `/github-release --prerelease --draft` - Create a draft pre-release

### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview the release without creating it. Skips user approval and release creation. |
| `--prerelease` | Mark the release as a pre-release (beta). |
| `--draft` | Create a draft release (not published until manually released). |

---

## Architecture Overview

```text
PHASE 1: Validation (bash-expert agent)
  -> Run get-release-info.sh script
  -> Validate: default branch, clean tree, synced with remote
  -> If validation fails: ABORT with clear error message
  -> If validation passes: Return JSON with tags, commits, repo info
  -> CHECKPOINT: Validation passed, data retrieved

PHASE 2: Changelog & Version Analysis (MAIN CONVERSATION)
  -> Parse commits using conventional commit patterns
  -> Categorize changes by type
  -> Determine version bump (MAJOR/MINOR/PATCH)
  -> Generate changelog preview
  -> CHECKPOINT: Changelog generated

PHASE 3: User Approval (MAIN CONVERSATION - MANDATORY STOP)
  -> Display proposed version and reasoning
  -> Show changelog preview
  -> Show release type flags
  -> WAIT FOR USER INPUT
  -> CHECKPOINT: User approved

PHASE 4: Create Release (bash-expert agent)
  -> [SKIPPED if --dry-run]
  -> Write changelog to temp file
  -> Run create-github-release.sh script
  -> CHECKPOINT: Release created

PHASE 5: Summary (MAIN CONVERSATION)
  -> Display release URL
  -> Show final version and changelog
```

---

## Instructions

### PHASE 1: Validation (DELEGATE TO bash-expert)

**Route to `bash-expert` agent with this prompt:**

```markdown
# Release Validation Task

Execute the release info script to validate prerequisites and gather repository data for creating a GitHub release.

## Script Path

```bash
GET_RELEASE_INFO=~/.claude/commands/scripts/github-release/get-release-info.sh
```

## Execution

Run the script:

```bash
$GET_RELEASE_INFO
```

The script will:
1. Get the current repository owner and name
2. Find the latest git tag (if any)
3. Collect all commits since the last tag (or all commits if no tag)
4. Get the current branch name

## Expected Output

The script returns JSON with this structure:

```json
{
  "metadata": {
    "owner": "owner-name",
    "repo": "repo-name",
    "current_branch": "main",
    "default_branch": "main"
  },
  "validations": {
    "on_default_branch": true,
    "default_branch": "main",
    "current_branch": "main",
    "working_tree_clean": true,
    "dirty_files": "",
    "synced_with_remote": true,
    "unpushed_commits": 0,
    "behind_remote": 0,
    "all_passed": true
  },
  "is_first_release": false,
  "last_tag": "v1.2.3",
  "all_tags": ["v1.2.3", "v1.2.2", "v1.2.1", "v1.2.0"],
  "commits": [
    {
      "hash": "0000000000000000000000000000000000000000",
      "short_hash": "0000000",
      "subject": "feat: add new feature",
      "body": "",
      "author": "Author Name",
      "date": "2024-01-15 10:30:00 +0000"
    },
    {
      "hash": "0000000000000000000000000000000000000000",
      "short_hash": "0000000",
      "subject": "fix: resolve bug in parser",
      "body": "",
      "author": "Author Name",
      "date": "2024-01-14 14:20:00 +0000"
    }
  ],
  "commit_count": 2
}
```

If no tags exist, `last_tag` will be `null`.

## Output Format

Return the complete JSON output from the script.

If the script fails, include an "error" field with the error message:

```json
{
  "error": "Error message here"
}
```
```

**Store the agent's JSON response for Phase 2.**

**If agent returns malformed JSON:**
- Show error: "Failed to parse agent response. Expected valid JSON."
- Display first 500 characters of raw agent output
- Abort workflow

**Validation Checks (MUST ALL PASS):**

1. **On default branch**: `validations.on_default_branch` must be `true`
   - **On failure:** "You must be on the default branch ({default_branch}) to create a release. Current branch: {current_branch}"

2. **Clean working tree**: `validations.working_tree_clean` must be `true`
   - **On failure:** "Working tree is not clean. Please commit or stash your changes first."
   - Show first 10 dirty files if `dirty_files` is not empty

3. **Synced with remote**: `validations.synced_with_remote` must be `true`
   - **On failure:**
     - If `unpushed_commits` > 0: "You have {n} unpushed commit(s). Please push before releasing."
     - If `behind_remote` > 0: "You are {n} commit(s) behind remote. Please pull before releasing."

**If ANY validation fails:** Display error message(s) and ABORT workflow.

**If `validations.all_passed` is `true`:** Proceed to Phase 2.

**CHECKPOINT**: Validation passed, release data retrieved.

- **On script failure:** Show error and abort.
- **On zero commits:** Show "No commits found since last release. Nothing to release." and complete workflow.

---

### PHASE 2: Changelog & Version Analysis (MAIN CONVERSATION - DO NOT DELEGATE)

**Parse commits and determine version bump:**

#### Step 1: Categorize Commits

Parse each commit message using conventional commit patterns:

| Pattern | Category | Version Impact |
|---------|----------|----------------|
| `BREAKING CHANGE:` or `!:` in message | Breaking Changes | MAJOR |
| `feat:` or `feat(scope):` | Features | MINOR |
| `fix:` or `fix(scope):` | Bug Fixes | PATCH |
| `docs:` or `docs(scope):` | Documentation | PATCH |
| `chore:`, `build:`, `ci:`, `refactor:`, `perf:`, `test:`, `style:` | Maintenance | PATCH |
| No pattern match | Other | PATCH |

**Parsing Rules:**
1. Check for `BREAKING CHANGE:` anywhere in commit message (case insensitive) -> Breaking Changes
2. Check for `!:` after type (e.g., `feat!:`) -> Breaking Changes
3. Match type prefix at start of message (case insensitive)
4. Extract scope if present: `type(scope): message`
5. Clean up message: remove type prefix, capitalize first letter

#### Step 2: Determine Version Bump

Based on highest-priority change category:

1. **MAJOR**: If ANY breaking changes exist
2. **MINOR**: If ANY features exist (and no breaking changes)
3. **PATCH**: Otherwise (fixes, docs, maintenance, other)

**Calculate new version:**

- If `latest_tag` is `null` (first release):
  - Default to `v0.1.0` for initial development
  - Or `v1.0.0` if any breaking change or explicit feat indicates production-ready

- If `latest_tag` exists:
  - Parse current version: `vMAJOR.MINOR.PATCH`
  - Apply bump:
    - MAJOR: increment MAJOR, reset MINOR and PATCH to 0
    - MINOR: increment MINOR, reset PATCH to 0
    - PATCH: increment PATCH

#### Step 3: Generate Changelog Preview

Build changelog with sections (only include sections with content):

```markdown
## What's Changed

### Breaking Changes
- Description of breaking change (@author) - #hash

### Features
- Description of new feature (@author) - #hash

### Bug Fixes
- Description of bug fix (@author) - #hash

### Documentation
- Description of docs change (@author) - #hash

### Maintenance
- Description of maintenance task (@author) - #hash

### Other
- Description of other change (@author) - #hash

**Full Changelog**: https://github.com/{owner}/{repo}/compare/{latest_tag}...{new_tag}
```

**If first release (no latest_tag):**
```markdown
**Full Changelog**: https://github.com/{owner}/{repo}/commits/{new_tag}
```

**Store:**
- `proposed_version`: The calculated new version (e.g., `v1.3.0`)
- `version_bump`: The bump type (MAJOR, MINOR, or PATCH)
- `bump_reason`: Why this bump was chosen (e.g., "Contains 2 new features")
- `changelog`: The formatted changelog markdown
- `categories`: Object with commit counts per category

**CHECKPOINT**: Changelog generated and version determined.

---

### PHASE 3: User Approval (MAIN CONVERSATION - MANDATORY STOP)

**If `--dry-run` is specified:**
- Display the proposed version and changelog preview (same format as below)
- Display: "DRY RUN: No release will be created."
- Skip user approval prompt
- Proceed directly to Phase 5 (Summary)

**If NOT dry-run:**

## STOP - MANDATORY USER INTERACTION

**YOU MUST STOP HERE AND WAIT FOR USER INPUT.**

Do NOT proceed to Phase 4 until the user has explicitly approved.
Do NOT create any release without user confirmation.

---

**Display the release preview:**

```text
## Release Preview

**Repository**: {owner}/{repo}
**Current Tag**: {latest_tag or "none (first release)"}
**Proposed Version**: {proposed_version}
**Version Bump**: {version_bump}
**Reason**: {bump_reason}

**Release Type**:
- Pre-release: {yes/no based on --prerelease flag}
- Draft: {yes/no based on --draft flag}

---

### Changelog Preview

{changelog}

---

### Commit Summary

- Breaking Changes: {count}
- Features: {count}
- Bug Fixes: {count}
- Documentation: {count}
- Maintenance: {count}
- Other: {count}
- **Total**: {total_commits}

---

**Options**:
- `yes` or `y` - Create release with proposed version ({proposed_version})
- `major` - Override to MAJOR version bump
- `minor` - Override to MINOR version bump
- `patch` - Override to PATCH version bump
- `prerelease` - Toggle pre-release flag
- `draft` - Toggle draft flag
- `no` or `n` - Cancel release

Your choice:
```

---

## DO NOT PROCEED WITHOUT USER RESPONSE

**You MUST wait for user to type their selection before continuing.**
**This is NOT optional. The workflow STOPS here until user responds.**

---

**Parse user input:**

| Input | Action |
|-------|--------|
| `yes`, `y`, `Y` | Proceed with proposed version |
| `major`, `MAJOR` | Recalculate version with MAJOR bump, show updated preview, ask again |
| `minor`, `MINOR` | Recalculate version with MINOR bump, show updated preview, ask again |
| `patch`, `PATCH` | Recalculate version with PATCH bump, show updated preview, ask again |
| `prerelease` | Toggle pre-release flag, show updated preview, ask again |
| `draft` | Toggle draft flag, show updated preview, ask again |
| `no`, `n`, `N` | Cancel workflow, show "Release cancelled." and stop |
| Other | Show "Invalid input. Please enter 'yes', 'no', 'major', 'minor', 'patch', 'prerelease', or 'draft'." and ask again |

**When user overrides version:**
1. Recalculate the new version based on override
2. Update `proposed_version` and `version_bump`
3. Update `bump_reason` to "User override: {bump_type}"
4. Show updated preview
5. Ask for confirmation again

**CHECKPOINT**: User approved release. **On cancel:** Show "Release cancelled." and stop.

---

### PHASE 4: Create Release (DELEGATE TO bash-expert)

**If `--dry-run` is specified:** SKIP this phase entirely. Proceed to Phase 5.

**Only proceed after user has explicitly approved.**

**Route to `bash-expert` agent with this prompt:**

```markdown
# Create GitHub Release Task

Create a GitHub release with the provided version and changelog.

## Release Information

```json
{
  "owner": "{owner}",
  "repo": "{repo}",
  "tag": "{proposed_version}",
  "prerelease": {prerelease_flag},
  "draft": {draft_flag}
}
```

## Changelog Content

The changelog content is provided below. Write it to a temp file.

```markdown
{changelog}
```

## Instructions

### Step 1: Write Changelog to Temp File

Use the Write tool to create the changelog file:
- Path: `/tmp/claude/release-changelog.md`
- Content: The changelog markdown above

**IMPORTANT**: Use the Write tool directly (not bash commands) to ensure proper formatting.

### Step 2: Create Release

Run the release script:

```bash
CREATE_RELEASE=~/.claude/commands/scripts/github-release/create-github-release.sh
$CREATE_RELEASE "{owner}/{repo}" "{tag}" /tmp/claude/release-changelog.md [--prerelease] [--draft]
```

Parameters:
- `owner/repo`: Repository in owner/repo format (e.g., myorg/myrepo)
- `tag`: Tag/version to create (e.g., v1.3.0)
- Changelog file path
- `--prerelease`: Optional flag to mark as pre-release
- `--draft`: Optional flag to mark as draft

Note: The script uses the tag as the release title automatically.

### Output Format

Return a JSON object with the results:

```json
{
  "status": "success",
  "url": "https://github.com/{owner}/{repo}/releases/tag/{tag}",
  "tag": "{tag}",
  "prerelease": {true/false},
  "draft": {true/false}
}
```

**If release creation fails:**

```json
{
  "status": "failed",
  "error": "Error message from script"
}
```

**If tag already exists:**

```json
{
  "status": "failed",
  "error": "Tag {tag} already exists. Please choose a different version."
}
```

Show progress while working:
```text
Creating release {tag} for {owner}/{repo}...
```

Return ONLY the JSON object after completion.
```

**Replace placeholders:**
- `{owner}`, `{repo}` from Phase 1 data
- `{proposed_version}` from Phase 3 approval
- `{prerelease_flag}`, `{draft_flag}` - true/false based on flags
- `{changelog}` from Phase 2

**Parse the agent's JSON response.**

**If agent returns malformed JSON:**
- Show error: "Failed to parse agent response. Expected valid JSON."
- Display first 500 characters of raw agent output
- Abort workflow

**CHECKPOINT**: Release created. **On failure:** Show error and abort.

---

### PHASE 5: Summary (MAIN CONVERSATION)

**Display final summary based on results:**

**If dry-run mode:**

```text
## Dry Run Complete

DRY RUN: This was a dry run - no release was created.

**Would have created:**
- Version: {proposed_version}
- Repository: {owner}/{repo}
- Pre-release: {yes/no}
- Draft: {yes/no}

---

### Changelog that would be used

{changelog}

---

To create this release for real, run:
`/github-release` (without --dry-run)
```

**If actual release - On success:**

```text
## Release Created Successfully

**Release URL**: {url}

**Details**:
- Version: {tag}
- Pre-release: {yes/no}
- Draft: {yes/no}

---

### Changelog

{changelog}

---

The release has been created on GitHub. {draft_message}
```

Where `{draft_message}` is:
- If draft: "This is a draft release. Visit the URL to publish it."
- If not draft: "The release is now live."

**If actual release - On failure:**

```text
## Release Failed

**Error**: {error_message}

**Attempted**:
- Version: {proposed_version}
- Repository: {owner}/{repo}

Please check:
- GitHub authentication (gh auth status)
- Repository permissions
- Whether the tag already exists
```

**Workflow complete.**

---

## Prerequisites

Before creating a release, the following conditions MUST be met:

| Requirement | Check | Error Message |
|-------------|-------|---------------|
| Default branch | Must be on main/master | "You must be on the default branch ({default_branch}) to create a release. Current branch: {current_branch}" |
| Clean working tree | No uncommitted changes | "Working tree is not clean. Please commit or stash your changes first." |
| Synced with remote | No unpushed/unpulled commits | "You have X unpushed commit(s)..." or "You are X commit(s) behind remote..." |

The command will ABORT if any prerequisite fails.

---

## Edge Cases

### First Release (No Tags)

When `latest_tag` is `null`:
- Default to `v0.1.0` for initial development
- If commits contain breaking changes or production-ready features, suggest `v1.0.0`
- Show "(first release)" in preview
- Changelog shows commits since repository start

### No Commits Since Last Tag

When `commit_count` is 0:
- Show: "No commits found since {latest_tag}. Nothing to release."
- Abort workflow gracefully
- Do not prompt for version or changelog

### User Overrides Version

When user enters `major`, `minor`, or `patch`:
1. Keep the same commits and categories
2. Recalculate version based on override:
   - MAJOR: `vX.0.0` where X = current major + 1
   - MINOR: `vX.Y.0` where Y = current minor + 1
   - PATCH: `vX.Y.Z` where Z = current patch + 1
3. Update `bump_reason` to "User override"
4. Show updated preview
5. Ask for confirmation again (do not auto-proceed)

### Tag Already Exists

When create-release script returns "tag already exists" error:
- Show clear error: "Tag {version} already exists"
- Suggest: "Use a different version or delete the existing tag first"
- Do not retry automatically

### Pre-release Version Formats

When `--prerelease` flag is set:
- Version format remains standard: `v1.2.3`
- GitHub release is marked as pre-release
- Show "Pre-release: yes" in preview

---

## Error Handling

**If Phase 1 (validation) fails:**
- Show error message from bash-expert agent
- Common issues: not in a git repo, gh not authenticated
- Abort workflow

**If Phase 2 (analysis) fails:**
- Show error message
- Common issues: malformed commit messages, version parsing
- Abort workflow

**If Phase 3 (approval) - user cancels:**
- Show "Release cancelled."
- Complete workflow gracefully (not an error)

**If Phase 4 (release creation) fails:**
- Show error from script
- Common issues: tag exists, no permission, network error
- Do not retry automatically
- Suggest troubleshooting steps

**If invalid user input in Phase 3:**
- Show error message
- Re-display options
- Wait for valid input

---

## Enforcement Rules

**NEVER skip phases** - all phases are mandatory:
1. Phase 1: Validation (bash-expert agent)
2. Phase 2: Changelog Analysis (main conversation)
3. Phase 3: User Approval (main conversation - MANDATORY STOP)
4. Phase 4: Create Release (bash-expert agent - only after approval)
5. Phase 5: Summary (main conversation)

**NEVER delegate Phase 2 or 3** - analysis and approval must happen in main conversation

**NEVER create a release without user approval** - user MUST explicitly confirm with `yes` or `y`

**NEVER auto-proceed after version override** - always ask for confirmation again

**ALWAYS wait for user input in Phase 3** before proceeding to Phase 4

**ALWAYS validate agent responses** - ensure JSON is properly formatted before parsing

**ALWAYS use Write tool for changelog file** in Phase 4 - never bash heredoc or echo
