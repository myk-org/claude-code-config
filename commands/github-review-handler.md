---
skipConfirmation: true
---

# GitHub Review Handler

**Description:** Unified handler that processes ALL review sources (human, Qodo, CodeRabbit) from the current
branch's GitHub PR.

---

## CRITICAL: SESSION ISOLATION & FLOW ENFORCEMENT

**THIS PROMPT DEFINES A STRICT, SELF-CONTAINED WORKFLOW THAT MUST BE FOLLOWED EXACTLY:**

1. **IGNORE ALL PREVIOUS CONTEXT**: Previous conversations, tasks, or commands in this session are IRRELEVANT
2. **START FRESH**: This prompt creates a NEW workflow that starts from Step 1 and follows the exact sequence
   below
3. **NO ASSUMPTIONS**: Do NOT assume any steps have been completed - follow the workflow from the beginning
4. **MANDATORY CHECKPOINTS**: Each phase MUST complete fully before proceeding to the next phase
5. **REQUIRED CONFIRMATIONS**: All user confirmations (commit, push) MUST be asked - NEVER skip them

**If this prompt is called multiple times in a session, treat EACH invocation as a completely independent
workflow.**

---

## Instructions

### Task Tracking

This workflow uses Claude Code's task system for progress tracking. Tasks are created at each phase with dependencies to ensure proper ordering.

**Task visibility:** Use `/tasks` to see all tasks or `Ctrl+T` to toggle task panel.

**Task phases:**
- Phase 1: Collection tasks (fetch, present to user)
- Phase 2: Execution tasks (one per approved comment, run in parallel)
- Phase 3: Review task
- Phase 4: Test task (just testing)
- Phase 5: Post tasks (update JSON, post & resolve, store to DB)
- Phase 6: Commit & Push task (optional)

### Step 1: Fetch all review comments using the unified fetcher

### CRITICAL: Simple Command - DO NOT OVERCOMPLICATE

**ALWAYS use this exact command format:**

```bash
uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py
```

**That's it. Nothing more. No script extraction. No variable assignments. Just one simple command.**

---

**Usage patterns:**

1. **No URL provided**: Fetches all unresolved review threads from the PR

   ```bash
   uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py
   ```

2. **Review URL provided**: Fetches threads with specific review context

   ```bash
   uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py \
     "https://github.com/owner/repo/pull/123#pullrequestreview-456"
   ```

**THAT'S ALL. DO NOT extract scripts, get PR info, or do ANY bash manipulation. The script handles
EVERYTHING.**

### Step 2: Process the JSON output

The script returns structured JSON containing:

- `metadata`: Contains `owner`, `repo`, `pr_number`, `json_path` (path to saved JSON file)
- `human`: Array of human review comments
- `qodo`: Array of Qodo AI comments
- `coderabbit`: Array of CodeRabbit AI comments

**Each comment has:**

| Field | Description |
|-------|-------------|
| `thread_id` | GraphQL thread ID (required for replying/resolving threads) |
| `node_id` | REST API comment node ID (informational only) |
| `comment_id` | Numeric comment ID |
| `author` | The reviewer's username |
| `path` | File path |
| `line` | Line number |
| `body` | Comment text |
| `priority` | HIGH, MEDIUM, or LOW (auto-classified) |
| `source` | "human", "qodo", or "coderabbit" |
| `reply` | Reply message (null until set) |
| `status` | Processing status ("pending", "addressed", "skipped", "not_addressed") |
| `replies` | Array of thread replies (check if already rejected) |

### Step 2.5: Pre-processing

#### Thread ID Guard

**CRITICAL**: Before processing any comment, validate the `thread_id`.

If any item has a missing, empty, or whitespace-only `thread_id`:
- Set `status: "skipped"`
- Set `reply: "Skipped: No valid thread_id available to reply/resolve"`
- Exclude from user presentation
- **Still write this update back to `metadata.json_path`** (so the final JSON reflects the outcome)
- **Do not expect a reply/resolution to be posted** for these items (the posting script cannot act without a valid `thread_id`)
- **Treat these entries as immutable for the rest of the workflow** (do not re-present them, do not change their `status`/`reply` in later phases)

#### Filter Positive Comments

For each comment, analyze the body to filter out positive feedback:

**POSITIVE (Filter Out) - Comments that are:**
- Praise/acknowledgment: "good", "great", "nice", "excellent", "perfect", "well done", "correct"
- Positive feedback on fixes: "good fix", "nice improvement", "better approach"
- Acknowledgment without suggestions: No action words like "should", "consider", "recommend", "suggest"

**ACTIONABLE (Keep) - Comments that:**
- Contain suggestions: "should", "consider", "recommend", "suggest", "could", "might want to"
- Point out issues: "issue", "problem", "concern", "potential", "risk"
- Request changes: "change", "update", "modify", "improve", "refactor"

#### Check for Pre-Rejected Comments

For each comment, check the `replies` array. If the PR author already rejected the suggestion in a reply,
auto-skip it with their reason instead of asking again.

#### Duplicate Detection

Detect duplicates across sources using these criteria:
- Same file path
- Overlapping or adjacent line ranges (within 5 lines)
- Similar title/category (fuzzy match on body content)

**Stable identifier (required):**
- Prefer `thread_id` when present (unique per thread)
- Otherwise use a deterministic composite: `<source>:<comment_id>`

For duplicates:
- Mark with `is_duplicate: true` on the duplicate
- Set `duplicate_of: <stable_id>` pointing to the original
- Add `duplicate_sources: ["qodo", "coderabbit"]` on the original if applicable
- Present only the original to the user

### Step 2.6: Merge and Sort All Comments

1. **Merge** all arrays: `human` + `qodo` + `coderabbit`
2. **Filter** out: positive comments, pre-rejected, missing thread_id, duplicates
3. **Sort by priority** across ALL sources:
   - ALL HIGH-priority first (regardless of source)
   - ALL MEDIUM-priority second
   - ALL LOW-priority last

### Step 3: Display Summary Header

**BEFORE presenting the first comment**, show this summary:

```text
Found XX comments (Human: X, Qodo: X, CodeRabbit: X)
```

### Step 4: PHASE 1 - Collect User Decisions (COLLECTION ONLY - NO PROCESSING)

**Create Phase 1 task:**

```text
TaskCreate: "Collect user decisions on review comments"
  - activeForm: "Collecting decisions"
  - Status: in_progress
```

**CRITICAL: This is the COLLECTION phase. Do NOT execute, implement, or process ANY comments yet. Only ask
questions and create tasks.**

Go through ALL merged comments in priority order (HIGH -> MEDIUM -> LOW), collecting user decisions.

**IMPORTANT: Present each comment individually, WAIT for user response, but NEVER execute, implement, or
process anything during this phase.**

For each comment, present:

```text
[HIGH|MEDIUM|LOW] Priority - Comment X of Y
Source: [Human: @username | Qodo | CodeRabbit]
File: [path]
Line: [line]
Body: [body - truncate if very long, show first 200 chars]

Do you want to address? (yes/no/all/skip human/skip qodo/skip coderabbit/skip ai)
```

Note: If displaying emojis, use the label as well: HIGH, MEDIUM, or LOW must always appear as text for
accessibility.

#### Response Options

| Response | Action |
|----------|--------|
| `yes` | Create task, continue to next |
| `no` | Ask reason, mark `not_addressed`, continue |
| `all` | Create tasks for ALL remaining comments |
| `skip human` | Skip all remaining human comments |
| `skip qodo` | Skip all remaining Qodo comments |
| `skip coderabbit` | Skip all remaining CodeRabbit comments |
| `skip ai` | Skip all remaining AI comments (Qodo + CodeRabbit) |

**AI Challenge Mode**: When you respond "no", Claude may challenge your decision if it independently
believes the comment is worth addressing (regardless of the source's priority label). Claude will
explain its reasoning once - your final decision is always respected.

#### CRITICAL: Track Comment Outcomes for Reply

For EVERY comment presented, track the outcome for the final reply:
- **Thread ID**: The `thread_id` from JSON (needed for threaded replies)
- **Source**: human, qodo, or coderabbit
- **Comment number**: Sequential (1, 2, 3...)
- **Reviewer**: The author name
- **File**: The file path
- **Outcome**: Will be one of: `addressed`, `not_addressed`, `skipped`
- **Reason**: Required for `not_addressed` and `skipped` outcomes

**For "yes" response:**
- Create a task with appropriate agent assignment
- Show confirmation: "Task created: [brief description]"
- **DO NOT execute the task - Continue to next comment immediately**

**For "all" response:**
- Create tasks for the current comment AND **ALL remaining comments** automatically
- Show summary: "Created tasks for current comment + X remaining comments"
- **Skip to Phase 2 immediately**

**For "no" response:**

1. **AI Independent Evaluation**: Before accepting "no", Claude independently evaluates whether this comment is worth addressing, ignoring the source's priority label. Consider:
   - Security implications (authentication, authorization, injection, data exposure)
   - Bug/correctness risk (logic errors, edge cases, race conditions)
   - Maintainability impact (code clarity, technical debt)
   - Best practices violations that could cause issues later

2. **Challenge Decision**:
   - If Claude believes the comment IS worth addressing -> Challenge the user (see below)
   - If Claude agrees with dismissal -> Accept "no" and ask for reason

3. **Challenge Flow** (one challenge only):
   ```text
   I'd push back on this one. [Explain WHY Claude thinks it's worth addressing,
   referencing specific concerns like security, bugs, or maintainability.
   Be concrete, not generic.]

   Do you want to reconsider? (yes/no)
   ```

   - If user says "yes" -> Create task, continue to next comment
   - If user still says "no" -> Accept gracefully, ask for reason, continue

4. **After final "no"**:
   - MUST ask user: "Please provide a brief reason:"
   - Set outcome = `not_addressed`, reason = user's response
   - If user doesn't provide reason, use "User declined"
   - Continue to next comment immediately

**Key principles:**
- Challenge ONCE only - respect user's final decision
- Provide concrete reasoning, not generic "you should do this"
- Be a collaborator, not a nag
- Claude's evaluation is independent of source priority (CodeRabbit LOW might be Claude HIGH)

**For "skip human" response:**
- Ask reason once: "Please provide a brief reason for skipping all remaining human comments:"
- Mark ALL remaining human source comments as `skipped` with the reason
- Continue presenting non-human comments

**For "skip qodo" response:**
- Ask reason once: "Please provide a brief reason for skipping all remaining Qodo comments:"
- Mark ALL remaining qodo source comments as `skipped` with the reason
- Continue presenting non-qodo comments

**For "skip coderabbit" response:**
- Ask reason once: "Please provide a brief reason for skipping all remaining CodeRabbit comments:"
- Mark ALL remaining coderabbit source comments as `skipped` with the reason
- Continue presenting non-coderabbit comments

**For "skip ai" response:**
- Ask reason once: "Please provide a brief reason for skipping all remaining AI comments:"
- Mark ALL remaining qodo AND coderabbit source comments as `skipped` with the reason
- Continue presenting human comments only

**REMINDER: Do NOT execute, implement, fix, or process anything during this phase. Only collect decisions
and create tasks.**

### Step 5: PHASE 2 - Process All Approved Tasks (EXECUTION PHASE)

**IMPORTANT: Only start this phase AFTER all comments have been presented and decisions collected.**

After ALL comments have been reviewed in Phase 1:

**Create execution tasks (parallel):**

For each approved comment, create a task:

```text
TaskCreate: "[File: path, Line: N] Brief description from body"
  - activeForm: "Implementing [brief]"
  - Status: pending
```

Set all execution tasks to `blockedBy` the Phase 1 collection task.

Then set all tasks to `in_progress` and process in parallel. Mark each as `completed` when done.

```text
Example task list for 3 approved comments:
├── Task 2: [scripts/foo.py:42] Add error handling (in_progress)
├── Task 3: [scripts/bar.py:10] Fix variable naming (in_progress)
└── Task 4: [tests/test_foo.py:25] Add missing test (in_progress)
```

Process multiple tasks in parallel by delegating to appropriate specialists simultaneously.

1. **Show approved tasks and proceed directly:**

```text
Processing X approved tasks:
1. [Task description]
2. [Task description]
...
```

Proceed directly to execution (no confirmation needed since user already approved each task in Phase 1)

1. **Process all approved tasks:**
   - **CRITICAL**: Process ALL tasks created during Phase 1
   - **NEVER skip tasks** - if a task was created in Phase 1, it MUST be executed in Phase 2
   - Route to appropriate specialists based on comment content
   - Process multiple tasks in parallel when possible
   - Mark each task as completed after finishing
   - **Track unimplemented changes**: If AI decides NOT to make changes for an approved task, track the reason

   **Update outcome tracking after each task:**
   - If changes were made successfully: Set outcome = `addressed`
   - If AI decided NOT to make changes: Set outcome = `not_addressed`, reason = [explanation of why]

### Step 6: PHASE 3 - Review Unimplemented Changes

**MANDATORY CHECKPOINT**: Before proceeding to posting replies, MUST review any approved comments where AI
decided not to make changes.

If AI decided NOT to implement changes for ANY approved tasks (tasks where user said "yes" but AI determined
no changes needed):

- **Show summary of unimplemented changes:**

  ```text
  Unimplemented Changes Review (X approved comments not changed):

  1. [PRIORITY] Priority - Source: [Human/@author | Qodo | CodeRabbit]
     File: [path] - Line: [line]
     Comment: [body (truncated)]
     Reason AI did not implement: [Explain why no changes were made]

  2. [PRIORITY] Priority - Source: [Human/@author | Qodo | CodeRabbit]
     File: [path] - Line: [line]
     Comment: [body (truncated)]
     Reason AI did not implement: [Explain why no changes were made]
  ...
  ```

- **MANDATORY**: Ask user for confirmation:

  ```text
  Do you approve proceeding without these changes? (yes/no)
  - yes: Proceed to Phase 4 (Testing)
  - no: Reconsider and implement the changes
  ```

- **If user says "no"**: Re-implement the changes as requested
- **If user says "yes"**: Proceed to Phase 4 (Testing)

**If ALL approved tasks were implemented**: Proceed directly to Phase 4

**CHECKPOINT**: User has reviewed and approved all unimplemented changes OR all approved tasks were implemented

### Step 7: PHASE 4 - Testing

**Create Phase 4 task:**

```text
TaskCreate: "Run tests with coverage"
  - activeForm: "Running tests"
  - blockedBy: [all execution tasks]
```

**MANDATORY STEP 1**: Run all tests WITH coverage

**MANDATORY STEP 2**: Check BOTH test results AND coverage results:
- **If tests pass AND coverage passes**: Proceed to Phase 5 (Post Review Replies)
- **If tests pass BUT coverage fails**: This is a FAILURE
  - Analyze coverage gaps and add missing tests
  - Re-run tests with coverage until BOTH pass
- **If tests fail**:
  - Analyze and fix test failures
  - Re-run until tests pass

**CHECKPOINT**: Tests AND coverage BOTH pass

### Step 8: PHASE 5 - Post Review Replies

**MANDATORY**: After Phase 4 (tests pass), update the JSON file and post replies.

**Create Phase 5 tasks with dependencies:**

```text
TaskCreate: "Update JSON with replies and status"
  - activeForm: "Updating JSON"
  - blockedBy: [test task]

TaskCreate: "Post replies and resolve threads"
  - activeForm: "Posting replies"
  - blockedBy: [update JSON task]

TaskCreate: "Store reviews to database"
  - activeForm: "Storing to database"
  - blockedBy: [post replies task]
```

Execute each task in order, respecting dependencies.

---

**STEP 1**: Update the JSON file at path from `metadata.json_path`

For each comment that was processed, update its entry in the appropriate array (`human`, `qodo`, or
`coderabbit`):

**For ADDRESSED comments:**

```json
{
  "reply": "Done",
  "status": "addressed"
}
```

**For SKIPPED comments:**

```json
{
  "reply": "Skipped: [user's reason]",
  "status": "skipped"
}
```

**For NOT ADDRESSED comments:**

```json
{
  "reply": "Not addressed: [reason]",
  "status": "not_addressed"
}
```

**STEP 2**: Write the updated JSON back to the file at `metadata.json_path`

**STEP 2.5**: Validate JSON before proceeding

After writing the JSON file, validate it to ensure proper escaping:

```bash
uv run -c "import json; json.load(open('<path from metadata.json_path>'))"
```

If validation fails, fix the JSON (usually unescaped quotes in body content) and re-validate before proceeding.

**STEP 3**: Call the posting script

```bash
uv run ~/.claude/commands/scripts/general/post-review-replies-from-json.py "<path from metadata.json_path>"
```

Use the actual path value from `metadata.json_path` in the JSON output.

**STEP 4**: Store reviews to database

After posting replies, persist the review data to the database for analytics:

```bash
uv run ~/.claude/commands/scripts/general/store-reviews-to-db.py "<path from metadata.json_path>"
```

Use the actual path value from `metadata.json_path` in the JSON output.

This stores all processed reviews (addressed, skipped, not_addressed) for future reference and statistics.

---

#### CRITICAL: Source-Specific Resolution Behavior

| Source | Resolve skipped/not_addressed? | Reason |
|--------|-------------------------------|--------|
| human | NO | Allow human reviewer to follow up |
| qodo | YES | AI bot, close all threads after reply |
| coderabbit | YES | AI bot, close all threads after reply |

**What this means:**

- **Human reviews**: Only `addressed` threads are resolved. `skipped` and `not_addressed` threads get
  replies but remain OPEN for the human reviewer to follow up.
- **AI reviews (Qodo/CodeRabbit)**: ALL threads are resolved after reply, regardless of status. The reply
  acknowledges the comment, and the thread closes.

**NOTE**: The posting script handles this logic automatically based on the `source` field. You only need to
set `status` and `reply` correctly.

**CHECKPOINT**: Replies posted to PR

### Step 9: PHASE 6 - Commit & Push

**IMPORTANT**: Tasks are created ONLY after user confirms each step. Never create tasks before asking.

**MANDATORY STEP 1**: After replies are posted, MUST ask: "All replies posted. Do you want to commit the changes? (yes/no)"

**MANDATORY STEP 2**: If user says "yes":
- Create commit task:

  ```text
  TaskCreate: "Commit changes"
    - activeForm: "Committing changes"
    - blockedBy: [store to DB task]
  ```

- Execute the commit

**MANDATORY STEP 3**: After commit (or commit decline), MUST ask: "Do you want to push to remote? (yes/no)"
- If no commit was made, ask: "Do you want to push any existing commits to remote? (yes/no)"

**MANDATORY STEP 4**: If user says "yes":
- Create push task:

  ```text
  TaskCreate: "Push to remote"
    - activeForm: "Pushing to remote"
    - blockedBy: [commit task] (if commit was made, otherwise blockedBy: [store to DB task])
  ```

- Execute the push

**CHECKPOINT**: Commit and push confirmations MUST be asked - this is the final step of the workflow

### Step 10: Final Cleanup

**MANDATORY**: Before completing the workflow, ensure all tasks are properly closed.

1. Run `TaskList` to check for any tasks still in `pending` or `in_progress` status
2. For each incomplete task:
   - If the work was actually completed, mark it as `completed`
   - If the task was skipped or no longer relevant, mark it as `completed` with a note
3. Verify all tasks show `completed` status

This prevents stale tasks from accumulating across workflow runs.

---

## CRITICAL WORKFLOW - STRICT PHASE SEQUENCE

This workflow has **6 MANDATORY PHASES** that MUST be executed in order. Each phase has **REQUIRED CHECKPOINTS**
that CANNOT be skipped:

### PHASE 1: Collection Phase

- Display summary header BEFORE first comment
- Present ALL comments in priority order (HIGH -> MEDIUM -> LOW) across ALL sources
- Collect decisions (yes/no/all/skip [source]) and create tasks - NO execution
- Support source-skip responses to skip remaining comments from specific sources
- **CHECKPOINT**: ALL comments have been presented and user decisions collected

### PHASE 2: Execution Phase

- ONLY execute tasks after ALL comments reviewed - NO more questions
- Process ALL approved tasks
- Track any tasks where AI decides not to make changes (with reasoning)
- **CHECKPOINT**: ALL approved tasks have been processed (implemented or reasoned skip)

### PHASE 3: Unimplemented Changes Review

- **MANDATORY STEP 1**: Show summary of any approved tasks where AI decided not to make changes
- **MANDATORY STEP 2**: Explain WHY changes were not made for each
- **MANDATORY STEP 3**: Ask user: "Do you approve proceeding without these changes? (yes/no)"
- **MANDATORY STEP 4**: If user says no, re-implement the changes
- **CHECKPOINT**: User has approved all unimplemented changes OR all tasks were implemented

### PHASE 4: Testing Phase

- **MANDATORY STEP 1**: Run all tests WITH coverage
- **MANDATORY STEP 2**: Check BOTH tests AND coverage - only proceed if BOTH pass
  - If tests pass BUT coverage fails - FIX coverage gaps (this is a FAILURE)
  - If tests fail - FIX test failures
- **CHECKPOINT**: Tests AND coverage BOTH pass

### PHASE 5: Post Review Replies

- Update JSON file with reply messages and status for each comment
- Call the posting script to post replies
- Script handles source-specific resolution (human: only addressed resolved; AI: all resolved)
- Store reviews to database
- **CHECKPOINT**: All replies posted successfully

### PHASE 6: Commit & Push Phase

- **IMPORTANT**: Create tasks ONLY after user confirms each step (not before asking)
- **MANDATORY STEP 1**: After replies posted, MUST ask user: "All replies posted. Do you want to commit the changes? (yes/no)"
- **MANDATORY STEP 2**: If user says yes: Create commit task, then execute
- **MANDATORY STEP 3**: MUST ask user: "Do you want to push to remote? (yes/no)"
- **MANDATORY STEP 4**: If user says yes: Create push task, then execute
- **CHECKPOINT**: Commit and push confirmations asked (even if user declined)

### Task Tracking Throughout Workflow

Tasks are created and managed automatically:

| Phase | Tasks Created | Dependencies |
|-------|--------------|--------------|
| 1 | 1 (collection) | None |
| 2 | N (one per approved comment) | blockedBy: Phase 1 |
| 3 | 0 (manual review) | - |
| 4 | 1 (testing) | blockedBy: Phase 2 |
| 5 | 3 (JSON, post, store) | blockedBy: Phase 4, then chained |
| 6 | 0-2 (commit if yes, push if yes) | Created after user confirms each |

Use `TaskList` to check progress. Use `TaskUpdate` to mark tasks completed.

---

## ENFORCEMENT RULES

- **NEVER skip phases** - all 6 phases are mandatory
- **NEVER skip checkpoints** - each phase must reach its checkpoint before proceeding
- **NEVER skip confirmations** - commit and push confirmations are REQUIRED even if previously discussed
- **NEVER assume** - always ask for confirmation, never assume user wants to commit/push
- **COMPLETE each phase fully** before starting the next phase

**If tests OR coverage fail**:

- Analyze and fix failures (add tests for coverage gaps)
- Re-run tests with coverage until BOTH pass before proceeding to Phase 5.

**If commit or push is declined**:

- Respect user's decision and proceed to next step (Phase 6's commit confirmation is mandatory to ask, but user can decline)

---

## Quick Reference

### Response Options Summary

| Response | Effect |
|----------|--------|
| `yes` | Create task for this comment |
| `no` | Mark as not_addressed (ask reason) |
| `all` | Create tasks for ALL remaining comments |
| `skip human` | Skip all remaining human comments |
| `skip qodo` | Skip all remaining Qodo comments |
| `skip coderabbit` | Skip all remaining CodeRabbit comments |
| `skip ai` | Skip all remaining Qodo AND CodeRabbit comments |

### Resolution Behavior Summary

| Source | addressed | skipped | not_addressed |
|--------|-----------|---------|---------------|
| Human | Resolve | Keep Open | Keep Open |
| Qodo | Resolve | Resolve | Resolve |
| CodeRabbit | Resolve | Resolve | Resolve |

### Scripts Reference

**Fetcher script:**
```bash
uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py
```

**Posting script:**
```bash
uv run ~/.claude/commands/scripts/general/post-review-replies-from-json.py "<path from metadata.json_path>"
```

**Storage script:**
```bash
uv run ~/.claude/commands/scripts/general/store-reviews-to-db.py "<path from metadata.json_path>"
```
