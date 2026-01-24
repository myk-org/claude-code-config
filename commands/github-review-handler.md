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

### Step 1: Fetch all review comments using the unified fetcher

### CRITICAL: Simple Command - DO NOT OVERCOMPLICATE

**ALWAYS use this exact command format:**

```bash
uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py "[optional_url]"
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

**CRITICAL**: Before processing any comment, validate the `thread_id`:

If any item has a missing, empty, or whitespace-only `thread_id`:
- Set `status: "skipped"`
- Set `reply: "Skipped: No valid thread_id available to reply/resolve"`
- Exclude from user presentation

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

For duplicates:
- Mark with `is_duplicate: true` on the duplicate
- Set `duplicate_of: <stable_id>` pointing to the original
- Add `duplicate_sources: ["qodo", "coderabbit"]` on the original if applicable
- Present only the original to the user

### Step 2.6: Merge and Sort All Comments

1. **Merge** all arrays: `human` + `qodo` + `coderabbit`
2. **Filter** out: positive comments, pre-rejected, missing thread_id, duplicates
3. **Sort by priority** across ALL sources:
   - ALL HIGH priority first (regardless of source)
   - ALL MEDIUM priority second
   - ALL LOW priority last

### Step 3: Display Summary Header

**BEFORE presenting the first comment**, show this summary:

```text
Found XX comments (Human: X, Qodo: X, CodeRabbit: X)

Responses: yes | no | all | skip human | skip qodo | skip coderabbit | skip ai
```

### Step 4: PHASE 1 - Collect User Decisions (COLLECTION ONLY - NO PROCESSING)

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
- MUST ask user: "Please provide a brief reason:"
- Set outcome = `not_addressed`, reason = user's response
- If user doesn't provide reason, use "User declined"
- Continue to next comment immediately

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

1. **Show approved tasks and proceed directly:**

```text
Processing X approved tasks:
1. [Task description]
2. [Task description]
...
```

Proceed directly to execution (no confirmation needed since user already approved each task in Phase 1)

2. **Process all approved tasks:**
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
  - yes: Proceed to Phase 4 (Post Review Replies)
  - no: Reconsider and implement the changes
  ```

- **If user says "no"**: Re-implement the changes as requested
- **If user says "yes"**: Proceed to Phase 4 (Post Review Replies)

**If ALL approved tasks were implemented**: Proceed directly to Phase 4

**CHECKPOINT**: User has reviewed and approved all unimplemented changes OR all approved tasks were implemented

### Step 7: PHASE 4 - Post Review Replies

**MANDATORY**: After Phase 3 approval (or if all tasks were implemented), update the JSON file and post replies.

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

**STEP 3**: Call the posting script

```bash
uv run ~/.claude/commands/scripts/general/post-review-replies-from-json.py /tmp/claude/pr-<number>-reviews.json
```

Where `<number>` is the PR number from `metadata.pr_number`.

**STEP 4**: Store reviews to database

After posting replies, persist the review data to the database for analytics:

```bash
uv run ~/.claude/commands/scripts/general/store-reviews-to-db.py /tmp/claude/pr-<number>-reviews.json
```

Where `<number>` is the PR number from `metadata.pr_number`.

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

### Step 8: PHASE 5 - Testing & Commit

**MANDATORY STEP 1**: Run all tests WITH coverage

**MANDATORY STEP 2**: Check BOTH test results AND coverage results:
- **If tests pass AND coverage passes**: MUST ask: "All tests and coverage pass. Do you want to commit
  the changes? (yes/no)"
  - If user says "yes": Commit the changes
  - If user says "no": Acknowledge and proceed to Phase 6 checkpoint (ask about push anyway)
- **If tests pass BUT coverage fails**: This is a FAILURE - do NOT ask about commit yet
  - Analyze coverage gaps and add missing tests
  - Re-run tests with coverage until BOTH pass
- **If tests fail**:
  - Analyze and fix test failures
  - Re-run until tests pass

**CHECKPOINT**: Tests AND coverage BOTH pass, AND commit confirmation asked (even if user declined)

### Step 9: PHASE 6 - Push to Remote

**MANDATORY STEP 1**: After successful commit (or commit decline), MUST ask: "Changes committed
successfully. Do you want to push the changes to remote? (yes/no)"
- If no commit was made, ask: "Do you want to push any existing commits to remote? (yes/no)"

**MANDATORY STEP 2**: If user says "yes": Push the changes to remote

**CHECKPOINT**: Push confirmation MUST be asked - this is the final step of the workflow

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

### PHASE 4: Post Review Replies

- Update JSON file with reply messages and status for each comment
- Call the posting script to post replies
- Script handles source-specific resolution (human: only addressed resolved; AI: all resolved)
- **CHECKPOINT**: All replies posted successfully

### PHASE 5: Testing & Commit Phase

- **MANDATORY STEP 1**: Run all tests WITH coverage
- **MANDATORY STEP 2**: Check BOTH tests AND coverage - only proceed if BOTH pass
  - If tests pass BUT coverage fails - FIX coverage gaps (this is a FAILURE)
  - If tests fail - FIX test failures
- **MANDATORY STEP 3**: Once BOTH pass, MUST ask user: "All tests and coverage pass. Do you want to commit
  the changes? (yes/no)"
- **MANDATORY STEP 4**: If user says yes: Commit the changes
- **CHECKPOINT**: Tests AND coverage BOTH pass, AND commit confirmation asked (even if user declined)

### PHASE 6: Push Phase

- **MANDATORY STEP 1**: After successful commit, MUST ask user: "Changes committed successfully. Do you want to
  push the changes to remote? (yes/no)"
- **MANDATORY STEP 2**: If user says yes: Push the changes to remote
- **CHECKPOINT**: Push confirmation asked (even if user declined)

---

## ENFORCEMENT RULES

- **NEVER skip phases** - all 6 phases are mandatory
- **NEVER skip checkpoints** - each phase must reach its checkpoint before proceeding
- **NEVER skip confirmations** - commit and push confirmations are REQUIRED even if previously discussed
- **NEVER assume** - always ask for confirmation, never assume user wants to commit/push
- **COMPLETE each phase fully** before starting the next phase

**If tests OR coverage fail**:

- Analyze and fix failures (add tests for coverage gaps)
- Re-run tests with coverage until BOTH pass before proceeding to Phase 5's commit confirmation.

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
uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py "[optional_url]"
```

**Posting script:**
```bash
uv run ~/.claude/commands/scripts/general/post-review-replies-from-json.py /tmp/claude/pr-<number>-reviews.json
```

**Storage script:**
```bash
uv run ~/.claude/commands/scripts/general/store-reviews-to-db.py /tmp/claude/pr-<number>-reviews.json
```
