---
description: Review a GitHub PR and post inline comments on selected findings
argument-hint: [PR_NUMBER|PR_URL]
allowed-tools: Bash(myk-claude-tools *), Bash(uv *), Bash(git *), Bash(gh *), AskUserQuestion, Task
---

# GitHub PR Review Command

Reviews a GitHub PR and posts inline review comments on selected findings.

## Prerequisites Check (MANDATORY)

Before starting, verify the tools are available:

### Step 1: Check myk-claude-tools

```bash
myk-claude-tools --version
```

If not found, prompt user: "myk-claude-tools is required. Install with: `uv tool install myk-claude-tools`. Install now?"

- Yes: Run `uv tool install myk-claude-tools`
- No: Abort with instructions

### Step 2: Continue with workflow

## Usage

- `/github:pr-review` - Review PR from current branch (auto-detect)
- `/github:pr-review 123` - Review PR #123 in current repo
- `/github:pr-review https://github.com/owner/repo/pull/123` - Review from URL

## Workflow

### Phase 1a: Data Fetching

Run the diff script to get PR data:

```bash
myk-claude-tools pr diff $ARGUMENTS
```

Store the JSON output containing metadata, diff, and files.

### Phase 1b: Fetch CLAUDE.md

```bash
myk-claude-tools pr claude-md $ARGUMENTS
```

### Phase 2: Code Analysis

Delegate to `code-reviewer` agent with the diff and CLAUDE.md content. The agent should return JSON with findings.

### Phase 3: User Selection

Present findings to user grouped by severity (CRITICAL, WARNING, SUGGESTION). Ask which to post:

- 'all' = Post all
- 'none' = Skip posting
- Specific numbers = Post only those

### Phase 4: Post Comments

If user selected findings, write JSON to temp file and post:

```bash
myk-claude-tools pr post-comment {owner}/{repo} {pr_number} {head_sha} /tmp/claude/pr-review-comments.json
```

### Phase 5: Summary

Display final summary with counts and links.
