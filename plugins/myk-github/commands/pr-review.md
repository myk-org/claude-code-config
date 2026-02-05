---
description: Review a GitHub PR and post inline comments on selected findings
argument-hint: [PR_NUMBER|PR_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task
---

# GitHub PR Review Command

Reviews a GitHub PR and posts inline review comments on selected findings.

## Prerequisites Check (MANDATORY)

Before starting, verify the tools are available:

### Step 0: Check uv

```bash
uv --version
```

If not found, install from <https://docs.astral.sh/uv/getting-started/installation/>

### Step 1: Check myk-claude-tools

```bash
myk-claude-tools --version
```

If not found, prompt user: "myk-claude-tools is required. Install with: `uv tool install myk-claude-tools`. Install now?"

- Yes: Run `uv tool install myk-claude-tools`
- No: Abort with instructions

### Step 2: Continue with workflow

## Usage

- `/myk-github:pr-review` - Review PR from current branch (auto-detect)
- `/myk-github:pr-review 123` - Review PR #123 in current repo
- `/myk-github:pr-review https://github.com/owner/repo/pull/123` - Review from URL

## Workflow

### Phase 0: PR Detection (when no arguments provided)

If `$ARGUMENTS` is empty:

1. Detect PR from current branch:

   ```bash
   gh pr view --json number,headRefOid
   ```

2. Get base repository context (where PR targets):

   The base repository (where the PR is opened) is determined by the current working directory context.
   When you run `gh pr view` from a cloned repository, it operates in that repository's context.

   To get `owner` and `repo`:

   ```bash
   gh repo view --json owner,name
   ```

   This returns the base repository information regardless of whether the PR comes from a fork.

   **Note:** `baseRepository` is NOT available in `gh pr view --json`. For fork PRs, `headRepository` would incorrectly point to the fork, not the target repository.

3. Extract and store:

   - `pr_number` from the PR JSON response
   - `owner` from `gh repo view` → `owner.login`
   - `repo` from `gh repo view` → `name`
   - `head_sha` from `headRefOid`

4. Use `{pr_number}` for subsequent CLI commands

If `$ARGUMENTS` contains a PR number or URL, use it directly.

### Phase 1a: Data Fetching

Run the diff command to get PR data:

If PR was auto-detected (no arguments):

```bash
myk-claude-tools pr diff {pr_number}
```

Otherwise:

```bash
myk-claude-tools pr diff $ARGUMENTS
```

Store the JSON output containing metadata, diff, and files.

### Phase 1b: Fetch CLAUDE.md

Run the claude-md command to get project rules:

If PR was auto-detected (no arguments):

```bash
myk-claude-tools pr claude-md {pr_number}
```

Otherwise:

```bash
myk-claude-tools pr claude-md $ARGUMENTS
```

Store the output as `claude_md_content`.

### Phase 2: Code Analysis

Delegate to `code-reviewer` agent with:

- The diff content from Phase 1a
- The CLAUDE.md content from Phase 1b (or "No CLAUDE.md found" if empty)

The agent should analyze for security, bugs, error handling, performance issues and return JSON with findings.

### Phase 3: User Selection

Present findings to user grouped by severity (CRITICAL, WARNING, SUGGESTION). Ask which to post:

- 'all' = Post all
- 'none' = Skip posting
- Specific numbers = Post only those

### Phase 4: Post Comments

If user selected findings, create temp directory and write JSON to temp file:

```bash
mkdir -p /tmp/claude
```

Use the `owner`, `repo`, `pr_number`, and `head_sha` from Phase 0 or Phase 1a metadata:

```bash
myk-claude-tools pr post-comment {owner}/{repo} {pr_number} {head_sha} /tmp/claude/pr-review-comments.json
```

### Phase 5: Summary

Display final summary with counts and links.
