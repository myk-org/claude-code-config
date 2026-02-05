---
description: Process ALL review sources (human, Qodo, CodeRabbit) from current PR
argument-hint: [REVIEW_URL]
allowed-tools: Bash(myk-claude-tools *), Bash(uv *), Bash(git *), Bash(gh *), AskUserQuestion, Task
---

# GitHub Review Handler

Unified handler that processes ALL review sources from the current branch's GitHub PR.

## Prerequisites Check (MANDATORY)

### Step 1: Check myk-claude-tools

```bash
myk-claude-tools --version
```

If not found, prompt to install: `uv tool install myk-claude-tools`

## Usage

- `/github:review-handler` - Process reviews from current PR
- `/github:review-handler https://github.com/owner/repo/pull/123#pullrequestreview-456` - With specific review URL

## Workflow

### Phase 1: Fetch Reviews

```bash
myk-claude-tools reviews fetch [REVIEW_URL]
```

Returns JSON with categorized comments (human, qodo, coderabbit).

### Phase 2: User Decision Collection

Present each comment in priority order (HIGH -> MEDIUM -> LOW):

- 'yes' - Address this comment
- 'no' - Skip (ask reason)
- 'all' - Address all remaining
- 'skip human/qodo/coderabbit/ai' - Skip remaining from source

### Phase 3: Execute Approved Tasks

For each approved comment, delegate to appropriate specialist agent.

### Phase 4: Review Unimplemented

If any approved tasks weren't implemented, review with user.

### Phase 5: Testing

Run tests with coverage. Fix failures before proceeding.

### Phase 6: Post Replies

Update JSON with status and replies:

```bash
myk-claude-tools reviews post {json_path}
```

Store to database:

```bash
myk-claude-tools reviews store {json_path}
```

### Phase 7: Commit & Push

Ask user if they want to commit and push changes.
