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

**MANDATORY: Present ALL fetched items to the user for decision.
Never silently hide or omit items — including auto-skipped ones.**

Even if an item appears to be a repeat from a previous round, was already addressed,
or seems trivial — present it to the user. The user decides what to address or skip,
not the AI.

**Presentation format (MANDATORY — always use this exact structure):**

**HARD RULE: The table MUST include ALL items — pending AND auto-skipped.
No exceptions. Never present a partial table. If you omit auto-skipped items,
the output is INVALID and must be redone.**

Present one table per source (human, qodo, coderabbit). Skip sources with zero items.
Within each table, sort by priority (HIGH → MEDIUM → LOW).
Use a **global counter** for the `#` column across all tables (not per-table).

```text
## Review Items: {source} ({total} total, {auto_skipped} auto-skipped)

| # | Priority | File | Line | Summary | Status |
|---|----------|------|------|---------|--------|
| 1 | HIGH | src/storage.py | 231 | Backfill destroys historical chronology | Pending |
| 2 | MEDIUM | src/html_report.py | 1141 | Add/delete leaves badges stale | Pending |
| 3 | LOW | src/utils.py | 42 | Unused import | Auto-skipped (skipped): "style only" |
| 4 | LOW | src/config.py | 15 | Missing validation | Auto-skipped (addressed): "added in prev PR" |

(Numbering continues across tables — e.g., if this table ends at 4, the next table starts at 5.)
```

**Table rules:**

- **Always a table** — never use bullets, prose, or any other format
- **Summary column:** 1-2 lines summarizing the comment.
  Include "Also applies to" references if present
- **Status column values:**
  - `Pending` — awaiting user decision
  - `Auto-skipped ({original_status}): "{reason}"` — showing the original status (addressed/skipped/not_addressed) and the stored reason
- **Every item gets a row** — including auto-skipped items so the user can override

**After presenting all tables, show the response options:**

```text
Respond with:
- 'yes' / 'no' (per item number — if 'no', ask for a reason)
- 'all' — address all remaining pending items
- 'skip human/qodo/coderabbit' — skip remaining from that source (ask for a reason)
- 'skip ai' — skip all AI sources (qodo + coderabbit) (ask for a reason)
```

**User input method (MANDATORY):**

Always use the `AskUserQuestion` tool to collect user decisions — never rely on
free-text conversation. Present the tables first as regular output, then call
`AskUserQuestion` with a concise prompt summarizing the available options.

Example `AskUserQuestion` prompt:

```text
Enter your decisions (e.g., '1 yes, 2 no: already addressed, 3 yes, skip coderabbit: duplicates human review'):
```

The handler collects ALL decisions in a single `AskUserQuestion` call.
If the user says 'no' or 'skip' without a reason, follow up with another
`AskUserQuestion` asking for the reason before proceeding.

### Phase 3: Execute Approved Tasks

For each approved comment, delegate to appropriate specialist agent.
When delegating, pass the FULL original review thread to the agent — including the complete comment body,
all replies, every code suggestion/diff, and all referenced locations. Do NOT summarize or compress the thread.

**When fixing review comments (MANDATORY):**

- If the reviewer provides a specific code suggestion or diff, implement IT exactly — not your own interpretation
- Do NOT simplify, minimize, or "half-fix" the suggestion
- After fixing, verify your code matches what the reviewer asked for, not just "addresses the concern"
- **NO SKIP WITHOUT USER APPROVAL:** If you disagree with the suggestion, ASK THE USER before skipping, partially fixing, or applying a minimum-viable fix
- **Read the ENTIRE review thread before acting.** Review threads contain a top-level comment plus replies.
  Comments often contain multiple parts: a main issue description, code suggestions, AND additional references
  like "Also applies to: 663-668" or mentions of other files/lines. Replies may contain clarifications,
  additional locations, or refined suggestions. You MUST address ALL parts from the comment AND replies,
  not just the first paragraph.
- **Multi-location fixes are MANDATORY.** When a comment says "Also applies to: X-Y" or references other lines/files,
  apply the same logical fix, adapted as needed to each location. These are not optional — they are part of the
  comment's requirements.
- **Post-fix verification checklist.** After fixing a comment, re-read the ORIGINAL review thread in full and verify:
  1. Every code suggestion or diff was implemented
  2. Every referenced file and line range was addressed
  3. Every "Also applies to" location was fixed
  4. No secondary instructions or reply clarifications were skipped
  If any part was missed, fix it before moving to the next comment.

### Phase 4: Review Unimplemented

If any approved tasks weren't implemented, review with user.

### Phase 5: Testing

Run tests with coverage. Fix failures before proceeding.

### Phase 6: Commit & Push

Ask user if they want to commit and push changes.

Code must be pushed before posting replies so that reviewers can see the fixes
when threads are resolved.

### Phase 7: Post Replies

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
  (include the user's skip reason in `reply`)
- User said **skip ai** → `skipped` for all remaining AI sources
  (include the user's skip reason in `reply`)

**Body comments (outside-diff, nitpick, duplicate):**

Comments that don't have GitHub review threads (e.g., CodeRabbit outside-diff,
nitpick, and duplicate comments) are replied to via a single consolidated PR
comment per reviewer. The comment mentions the reviewer (e.g., `@coderabbitai`)
and includes sections for each comment with the decision made. This ensures
automated reviewers know their comments were reviewed and won't re-raise them.

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
