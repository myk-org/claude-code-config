---
description: Process ALL review sources (human, Qodo, CodeRabbit) from current PR
argument-hint: [REVIEW_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task
---

# GitHub Review Handler

Unified handler that processes ALL review sources from the current branch's GitHub PR.

## Prerequisites Check (MANDATORY)

### Step 0: Check uv

```bash
uv --version
```

If not found, install from <https://docs.astral.sh/uv/getting-started/installation/>

### Step 1: Check myk-claude-tools

```bash
myk-claude-tools --version
```

If not found, prompt to install: `uv tool install myk-claude-tools`

## Usage

- `/myk-github:review-handler` - Process reviews from current PR
- `/myk-github:review-handler https://github.com/owner/repo/pull/123#pullrequestreview-456` - With specific review URL

## Workflow

### Phase 1: Fetch Reviews

The `reviews fetch` command auto-detects the PR from the current branch.

If a specific review URL is provided in `$ARGUMENTS`:

```bash
myk-claude-tools reviews fetch $ARGUMENTS
```

Otherwise (auto-detect from current branch):

```bash
myk-claude-tools reviews fetch
```

Returns JSON with:

- `metadata`: owner, repo, pr_number, json_path
- `human`: Human review threads
- `qodo`: Qodo AI review threads
- `coderabbit`: CodeRabbit AI review threads

### Phase 2: User Decision Collection

**MANDATORY: Present ALL fetched items to the user for decision. Never auto-skip or auto-categorize items.**

Even if an item appears to be a repeat from a previous round, was already addressed, or seems trivial — present it to the user. The user decides what to address or skip, not the AI.

When presenting items:

1. Group by source (human, qodo, coderabbit)
2. Within each source, order by priority (HIGH → MEDIUM → LOW)
3. For items that appear to be repeats of previously addressed work, note this but still present them
4. Summarize each item concisely (1-2 lines) with file path and line number

User response options:

- 'yes' - Address this comment
- 'no' - Skip (ask reason)
- 'all' - Address all remaining
- 'skip human/qodo/coderabbit' - Skip remaining from that source
- 'skip ai' - Skip remaining from all AI sources (qodo + coderabbit)

### Phase 3: Execute Approved Tasks

For each approved comment, delegate to appropriate specialist agent.

### Phase 4: Review Unimplemented

If any approved tasks weren't implemented, review with user.

### Phase 5: Testing

Run tests with coverage. Fix failures before proceeding.

### Phase 6: Post Replies

Update each JSON entry with `status` and `reply` fields before posting.

**Valid status values:**

| Status | Behavior |
|--------|----------|
| `addressed` | Post reply, resolve thread |
| `not_addressed` | Post reply (human: leave unresolved; AI: resolve) |
| `skipped` | Post reply with skip reason (human: leave unresolved; AI: resolve) |
| `pending` | Skip (not processed yet) |
| `failed` | Retry posting |

**Mapping from user decisions (Phase 2):**

- User said **yes** and code was changed → `addressed`
- User said **yes** but change was not implemented → `not_addressed`
- User said **no** → `skipped` (include the user's skip reason in `reply`)
- User said **all** → same as **yes** for each remaining comment
- User said **skip \<source\>** → `skipped` for all remaining from that source

Post replies to GitHub:

```bash
myk-claude-tools reviews post {json_path}
```

If the command exits with a non-zero code, some threads failed to post.
The command prints an ACTION REQUIRED message with the exact retry command.
Re-run it to retry — only unposted entries are retried. Repeat until all succeed.

**Output verification (MANDATORY):**

After `reviews post` completes successfully, check the output:

- `Processed N threads` — N should equal the number of entries with status `addressed`, `not_addressed`, `skipped`, or `failed` (everything except `pending`)
- `Resolved: N` — should be non-zero if any entries have status `addressed` or if AI-source entries have status `skipped`/`not_addressed`
- If `Processed 0 threads`, the status values in the JSON are wrong — fix them to use valid values from the table above and re-run before proceeding
- If output shows `Warning: Unknown status`, fix those entries — e.g., `"done"` or `"completed"` are not valid, use `"addressed"` instead

Do NOT proceed to `reviews store` until `reviews post` shows the expected thread count.

Store to database:

```bash
myk-claude-tools reviews store {json_path}
```

### Phase 7: Commit & Push

Ask user if they want to commit and push changes.
