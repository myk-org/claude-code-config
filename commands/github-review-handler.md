---
skipConfirmation: true
---

# GitHub Review Handler

**Description:** Finds and processes human reviewer comments from the current branch's GitHub PR.

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

### Step 1: Get human review comments using the unified fetcher

### CRITICAL: Simple Command - DO NOT OVERCOMPLICATE

**ALWAYS use this exact command format:**

```bash
uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py [review_url]
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
   # User provided review URL:
   uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py \
     "https://github.com/owner/repo/pull/123#pullrequestreview-456"

   # User provided discussion URL:
   uv run ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.py \
     "https://github.com/owner/repo/pull/123#discussion_r789"
   ```

**If user provides NO input:**

The script will fetch all unresolved review threads and categorize them by source.

**THAT'S ALL. DO NOT extract scripts, get PR info, or do ANY bash manipulation. The script handles
EVERYTHING.**

### Step 2: Process the JSON output

The script returns structured JSON containing:

- `metadata`: Contains `owner`, `repo`, `pr_number`, `json_path` (path to saved JSON file)
- `human`: Array of human review comments (ONLY use this array for this handler)
- `qodo`: Array of Qodo AI comments (ignore for this handler)
- `coderabbit`: Array of CodeRabbit AI comments (ignore for this handler)

**Each comment in the `human` array has:**
- `thread_id`: GraphQL thread ID (required for replying/resolving threads)
- `node_id`: REST API comment node ID (informational only; posting requires `thread_id`)
- `comment_id`: REST API comment ID (used for non-thread operations like fetching details)
- `author`: The reviewer's username
- `path`: File path
- `line`: Line number
- `body`: Comment text
- `priority`: HIGH, MEDIUM, or LOW (auto-classified)
- `source`: Always "human" for this handler
- `reply`: Reply message (null until set)
- `status`: Processing status ("pending", "addressed", "skipped", "not_addressed")

**IMPORTANT**: This handler only processes the `human` array. Ignore `qodo` and `coderabbit` arrays.

### Step 3: PHASE 1 - Collect User Decisions (COLLECTION ONLY - NO PROCESSING)

**CRITICAL: This is the COLLECTION phase. Do NOT execute, implement, or process ANY comments yet. Only ask
questions and create tasks.**

Go through ALL comments in the `human` array sequentially, collecting user decisions:

**IMPORTANT: Present each comment individually, WAIT for user response, but NEVER execute, implement, or
process anything during this phase.**

For each comment, present:

```text
Human Review - Comment X of Y
Reviewer: [author]
File: [path]
Line: [line]
Comment: [body]

Do you want to address this comment? (yes/no/skip/all)
```

#### CRITICAL: Track Comment Outcomes for Reply

For EVERY comment presented, track the outcome for the final reply:
- **Thread ID**: The `thread_id` from JSON (needed for threaded replies)
- **Comment number**: Sequential (1, 2, 3...)
- **Reviewer**: The author name
- **File**: The file path
- **Outcome**: Will be one of: `addressed`, `not_addressed`, `skipped`
- **Reason**: Required for `not_addressed` and `skipped` outcomes

When user responds:
- **"yes"**: Outcome will be set after execution (addressed or not_addressed)
- **"no" or "skip"**: MUST ask user: "Please provide a brief reason for skipping this comment:"
  - Set outcome = `skipped`, reason = user's response
  - If user doesn't provide reason, use "User chose to skip"
- **"all"**: Track all remaining as pending execution

**For each "yes" response:**

- Create a task with appropriate agent assignment
- Show confirmation: "Task created: [brief description]"
- **DO NOT execute the task - Continue to next comment immediately**

**For "all" response:**

- Create tasks for the current comment AND **ALL remaining comments** automatically
- **CRITICAL**: "all" means process EVERY remaining comment - do NOT skip any comments
- Show summary: "Created tasks for current comment + X remaining comments"
- **Skip to Phase 2 immediately**

**For "no" or "skip" responses:**

- Show: "Skipped"
- Continue to next comment immediately

**REMINDER: Do NOT execute, implement, fix, or process anything during this phase. Only collect decisions
and create tasks.**

### Step 4: PHASE 2 - Process All Approved Tasks (EXECUTION PHASE)

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

### Step 5: PHASE 3 - Review Unimplemented Changes

**MANDATORY CHECKPOINT**: Before proceeding to posting replies, MUST review any approved comments where AI
decided not to make changes.

If AI decided NOT to implement changes for ANY approved tasks (tasks where user said "yes" but AI determined
no changes needed):

- **Show summary of unimplemented changes:**

  ```text
  Unimplemented Changes Review (X approved comments not changed):

  1. Reviewer: [author] - File: [path] - Line: [line]
     Comment: [body (truncated)]
     Reason AI did not implement: [Explain why no changes were made]

  2. Reviewer: [author] - File: [path] - Line: [line]
     Comment: [body (truncated)]
     Reason AI did not implement: [Explain why no changes were made]
  ...
  ```

- **MANDATORY**: Ask user for confirmation:

  ```text
  Do you approve proceeding without these changes? (yes/no)
  - yes: Proceed to Phase 3.5 (Post Review Reply)
  - no: Reconsider and implement the changes
  ```

- **If user says "no"**: Re-implement the changes as requested
- **If user says "yes"**: Proceed to Phase 3.5 (Post Review Reply)

**If ALL approved tasks were implemented**: Proceed directly to Phase 3.5

**CHECKPOINT**: User has reviewed and approved all unimplemented changes OR all approved tasks were implemented

### Step 6: PHASE 3.5 - Post Review Reply

**MANDATORY**: After Phase 3 approval (or if all tasks were implemented), update the JSON file and post replies.

---

**STEP 1**: Update the JSON file at path from `metadata.json_path`

For each comment in the `human` array that was processed:
- Set `reply` to the appropriate reply message:
  - For addressed: "Done" or a brief description of what was done
  - For skipped/not_addressed: The reason provided
- Set `status` to the outcome:
  - `"addressed"` - Comment was addressed with code changes
  - `"skipped"` - User chose to skip (reply posted but thread NOT resolved)
  - `"not_addressed"` - Could not be addressed (reply posted but thread NOT resolved)

#### IMPORTANT: Human Review Handling Differs from AI Reviews

Unlike AI review handlers (Qodo/CodeRabbit) where ALL threads are resolved after reply:
- **Addressed comments**: Reply with "Done" and RESOLVE the thread
- **Skipped comments**: Reply with reason but DO NOT resolve (allow human reviewer to follow up)
- **Not addressed comments**: Reply with reason but DO NOT resolve (allow human reviewer to follow up)

**STEP 2**: Write the updated JSON back to the file at `metadata.json_path`

Example update using jq:

```bash
# Update a specific comment's status and reply
jq '.human[0].status = "addressed" | .human[0].reply = "Done"' /tmp/claude/pr-123-reviews.json > /tmp/claude/pr-123-reviews.json.tmp && mv /tmp/claude/pr-123-reviews.json.tmp /tmp/claude/pr-123-reviews.json
```

**STEP 3**: Call the posting script to handle replies and resolution

```bash
uv run ~/.claude/commands/scripts/general/post-review-replies-from-json.py /tmp/claude/pr-<number>-reviews.json
```

Where `<number>` is the PR number from `metadata.pr_number`.

**NOTE**: The posting script will:
- Post replies to all threads with status != "pending"
- Resolve threads with status = "addressed"
- For status = "skipped" or "not_addressed", it posts the reply but does NOT resolve the thread (allows reviewer follow-up)

**Note**: The posting script correctly handles human reviews by NOT resolving threads with `skipped` or `not_addressed` statuses. No manual handling is required for these cases.

**Key difference from AI review handlers:** Human reviewer comments that are not addressed or skipped
do NOT get resolved - only replied to. This allows the human reviewer to follow up.

**CHECKPOINT**: Replies posted to PR

### Step 7: PHASE 4 - Testing & Commit

**MANDATORY STEP 1**: Run all tests

**MANDATORY STEP 2**: Check test results:
- **If tests pass**: MUST ask: "All tests pass. Do you want to commit the changes? (yes/no)"
  - If user says "yes": Commit the changes
  - If user says "no": Acknowledge and proceed to Phase 5 checkpoint (ask about push anyway)
- **If tests fail**:
  - Analyze and fix test failures
  - Re-run until tests pass

**CHECKPOINT**: Tests pass, AND commit confirmation asked (even if user declined)

### Step 8: PHASE 5 - Push to Remote

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

- ONLY collect decisions (yes/no/skip/all) and create tasks - NO execution
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

### PHASE 3.5: Post Review Reply

- Update JSON file with reply messages and status for each comment
- For addressed comments: Reply and resolve thread
- For skipped/not_addressed comments: Reply WITHOUT resolving (human reviews differ from AI reviews)
- **CHECKPOINT**: All replies posted successfully

### PHASE 4: Testing & Commit Phase

- **MANDATORY STEP 1**: Run all tests
- **MANDATORY STEP 2**: If tests pass, MUST ask user: "All tests pass. Do you want to commit
  the changes? (yes/no)"
- **MANDATORY STEP 3**: If user says yes: Commit the changes
- **CHECKPOINT**: Tests completed AND commit confirmation asked (even if user declined)

### PHASE 5: Push Phase

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

**If tests fail**:

- Analyze and fix failures
- Re-run tests until they pass before proceeding to Phase 4's commit confirmation.

Note: Human review comments are treated equally (no priority system like AI reviews).
Human reviews differ from AI reviews in that skipped/not_addressed comments are NOT resolved,
allowing the human reviewer to follow up on unaddressed feedback.
