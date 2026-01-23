---
name: github-qodo-review-handler
description: Processes Qodo AI code review comments
skipConfirmation: true
---

# GitHub Qodo AI Review Handler

**Description:** Processes Qodo AI code review comments from GitHub PRs with priority-based handling.

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

## Key Concepts

**Qodo bot username**: `qodo-code-review[bot]`

**Comment types**:
- **Inline review comments**: Part of PR review threads - CAN be resolved, reply threads and resolves
- Comments without `thread_id` cannot be resolved via the posting script

**Reply mechanism**:
- The posting script handles replying and resolving threads automatically
- You only need to update the JSON file with `reply` and `status` fields

---

## Instructions

### Step 1: Fetch Qodo comments using the unified fetcher

**CRITICAL: Simple Command - DO NOT OVERCOMPLICATE**

**ALWAYS use this exact command format:**

```bash
~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh "<USER_INPUT_IF_PROVIDED>"
```

**That's it. Nothing more. No script extraction. No variable assignments. Just one simple command.**

---

**Command invocation formats:**

1. **With URL argument**: Pass a specific review URL to process
   ```text
   /github-qodo-review-handler https://github.com/owner/repo/pull/123#pullrequestreview-456
   ```

2. **Without URL argument**: Fetches all unresolved Qodo comments from the PR
   ```text
   /github-qodo-review-handler
   ```

---

**Usage patterns:**

1. **No URL provided**: Fetches all unresolved inline review comments from the PR

   ```bash
   ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh
   ```

2. **PR review URL provided**: Fetches comments from that specific review plus all unresolved

   ```bash
   ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh "https://github.com/owner/repo/pull/123#pullrequestreview-2838476123"
   ```

**If user provides NO input:**

The script will fetch all unresolved inline review comments. This is the normal use case.

**THAT'S ALL. DO NOT extract scripts, get PR info, or do ANY bash manipulation. The script handles
EVERYTHING.**

### Step 2: Process the JSON output

The script returns structured JSON with categorized comments. **Filter to use ONLY the `qodo` array.**

**JSON structure:**

```json
{
  "metadata": {
    "owner": "...",
    "repo": "...",
    "pr_number": "...",
    "json_path": "/tmp/claude/pr-<number>-reviews.json"
  },
  "human": [ ... ],
  "qodo": [
    {
      "thread_id": "PRRT_xxx",
      "node_id": "PRRC_xxx",
      "comment_id": 123456,
      "author": "qodo-code-review[bot]",
      "path": "src/main.py",
      "line": 42,
      "body": "...",
      "priority": "HIGH",
      "source": "qodo",
      "reply": null,
      "status": "pending"
    }
  ],
  "coderabbit": [ ... ]
}
```

**Field descriptions:**
- `thread_id`: GraphQL thread ID (required for replying/resolving threads)
- `node_id`: REST API comment node ID (informational only; posting requires `thread_id`)
- `comment_id`: REST API comment ID (used for non-thread operations like fetching details)
- `author`: The bot username
- `path`: File path affected
- `line`: Line number
- `body`: Full description of the suggestion
- `priority`: HIGH, MEDIUM, or LOW (auto-classified)
- `source`: Always "qodo" for items in this array
- `reply`: Reply message (initially null, you will set this)
- `status`: Status (initially "pending", you will update to "addressed", "skipped", or "not_addressed")

**IMPORTANT**: The `metadata.json_path` contains the path to the saved JSON file. You will update this
file in Phase 5 before calling the posting script.

### Step 3: PHASE 1 - Collect User Decisions (COLLECTION ONLY - NO PROCESSING)

**CRITICAL: This is the COLLECTION phase. Do NOT execute, implement, or process ANY comments yet. Only ask
questions and create tasks.**

Go through ALL Qodo suggestions in priority order, collecting user decisions:

1. **HIGH Priority** first
2. **MEDIUM Priority** second
3. **LOW Priority** last

**IMPORTANT: Present each suggestion individually, WAIT for user response, but NEVER execute, implement, or
process anything during this phase.**

For ALL suggestions, use this unified format:

```text
[PRIORITY_EMOJI] [PRIORITY] Priority - Suggestion X of Y
File: [path]
Line: [line]
Body: [body - truncate if very long, show first 200 chars]

Do you want to address this suggestion? (yes/no/skip/all)
```

Note: Use 🔴 for HIGH priority, 🟡 for MEDIUM priority, and 🟢 for LOW priority.

### CRITICAL: Track Suggestion Outcomes for Reply

For EVERY suggestion presented, track the outcome for the final reply:
- **Index**: Position in the qodo array (0, 1, 2...)
- **Path**: The file path
- **Line**: The line number
- **Outcome**: Will be one of: `addressed`, `skipped`, or `not_addressed`
- **Reason**: Required for `skipped` and `not_addressed` outcomes
- **Reply message**: What to post as the reply

When user responds:
- **"yes"**: Outcome will be set after execution (addressed)
- **"no" or "skip"**: MUST ask user: "Please provide a brief reason for skipping this suggestion:"
  - Set outcome = `skipped`, reason = user's response
  - If user doesn't provide reason, use "User chose to skip"
- **"all"**: Track all remaining as pending execution

**For each "yes" response:**

- Create a task with appropriate agent assignment
- Show confirmation: "Task created: [brief description]"
- **DO NOT execute the task - Continue to next suggestion immediately**

**For "all" response:**

- Create tasks for the current suggestion AND **ALL remaining suggestions across ALL priority levels** automatically
- **CRITICAL**: "all" means process EVERY remaining suggestion (HIGH, MEDIUM, and LOW priority) - do NOT skip any
  priority level
- Show summary: "Created tasks for current suggestion + X remaining suggestions (Y HIGH, Z MEDIUM, W LOW)"
- **Skip to Phase 2 immediately**

**For "no" or "skip" responses:**

- Show: "Skipped"
- Continue to next suggestion immediately

**REMINDER: Do NOT execute, implement, fix, or process anything during this phase. Only collect decisions
and create tasks.**

### Step 4: PHASE 2 - Process All Approved Tasks (EXECUTION PHASE)

**IMPORTANT: Only start this phase AFTER all suggestions have been presented and decisions collected.**

After ALL suggestions have been reviewed in Phase 1:

1. **Show approved tasks and proceed directly:**

```text
Processing X approved tasks:
1. [Task description]
2. [Task description]
...
```

Proceed directly to execution (no confirmation needed since user already approved each task in Phase 1)

1. **Process all approved tasks:**
   - **CRITICAL**: Process ALL tasks created during Phase 1, regardless of priority level
   - **NEVER skip LOW priority tasks** - if a task was created in Phase 1, it MUST be executed in Phase 2
   - Use the `body` content as guidance when implementing changes
   - Route to appropriate specialists to implement the changes
   - Process multiple tasks in parallel when possible
   - Mark each task as completed after finishing
   - **Track unimplemented changes**: If AI decides NOT to make changes for an approved task, track the reason

   **Update outcome tracking after each task:**
   - If changes were made successfully: Set outcome = `addressed`
   - If AI decided NOT to make changes: Set outcome = `not_addressed`, reason = [explanation of why]

**Note**: LOW-priority tasks are just as important as higher-priority tasks during execution.

### Step 5: PHASE 3 - Review Unimplemented Changes

**MANDATORY CHECKPOINT**: Before proceeding to posting reply, MUST review any approved suggestions where AI
decided not to make changes.

If AI decided NOT to implement changes for ANY approved tasks (tasks where user said "yes" but AI determined
no changes needed):

- **Show summary of unimplemented changes:**

  ```text
  Unimplemented Changes Review (X approved suggestions not changed):

  1. [PRIORITY] Priority - File: [path] - Line: [line]
     Reason AI did not implement: [Explain why no changes were made - e.g., "Current code already
     implements the suggestion", "Suggestion is not applicable", "Suggested change would break existing
     functionality"]

  2. [PRIORITY] Priority - File: [path] - Line: [line]
     Reason AI did not implement: [Explain why no changes were made]
  ...
  ```

- **MANDATORY**: Ask user for confirmation:

  ```text
  Do you approve proceeding without these changes? (yes/no)
  - yes: Proceed to Phase 4 (Testing & Commit)
  - no: Reconsider and implement the changes
  ```

- **If user says "no"**: Re-implement the changes as requested
- **If user says "yes"**: Proceed to Phase 4 (Testing & Commit)

**If ALL approved tasks were implemented**: Proceed directly to Phase 4

**CHECKPOINT**: User has reviewed and approved all unimplemented changes OR all approved tasks were implemented

### Step 6: PHASE 4 - Testing & Commit

**MANDATORY STEP 1**: Run all tests WITH coverage

**MANDATORY STEP 2**: Check BOTH test results AND coverage results:
- **If tests pass AND coverage passes**: MUST ask: "All tests and coverage pass. Do you want to commit
  the changes? (yes/no)"
  - If user says "yes": Commit the changes
  - If user says "no": Acknowledge and proceed to Phase 4 checkpoint (ask about push anyway)
- **If tests pass BUT coverage fails**: This is a FAILURE - do NOT ask about commit yet
  - Analyze coverage gaps and add missing tests
  - Re-run tests with coverage until BOTH pass
- **If tests fail**:
  - Analyze and fix test failures
  - Re-run until tests pass

**CHECKPOINT**: Tests AND coverage BOTH pass, AND commit confirmation asked (even if user declined)

### Step 7: PHASE 5 - Post Qodo Reply

**MANDATORY**: After Phase 4 approval (or if all tasks were implemented), update the JSON file and call the
posting script.

---

#### Step 7.1: Update the JSON file

Read the JSON file from `metadata.json_path` (e.g., `/tmp/claude/pr-<number>-reviews.json`).

For each processed Qodo comment, update its entry in the `qodo` array:

**For ADDRESSED suggestions:**
```json
{
  "reply": "Done",
  "status": "addressed"
}
```

**For SKIPPED suggestions:**
```json
{
  "reply": "Skipped: [user's reason]",
  "status": "skipped"
}
```

**For NOT ADDRESSED suggestions (AI decided not to implement):**
```json
{
  "reply": "Not addressed: [AI's reason]",
  "status": "not_addressed"
}
```

Write the updated JSON back to the same file path.

---

#### Step 7.2: Call the posting script

After updating the JSON file, call the posting script:

```bash
~/.claude/commands/scripts/general/post-review-replies-from-json.sh "$JSON_PATH"
```

Where `$JSON_PATH` is the value from `metadata.json_path` (e.g., `/tmp/claude/pr-<number>-reviews.json`).

The script will:
- Read the JSON file
- For each comment with status "addressed" or "skipped":
  - Post the reply to the thread
  - Resolve the thread
- Skip comments with status "pending"
- Update the JSON with `posted_at` timestamps

**CHECKPOINT**: All Qodo replies posted successfully

### Step 8: PHASE 6 - Push to Remote

**MANDATORY STEP 1**: After Phase 5 completion, MUST ask about pushing:
- If a commit was made: "Changes committed successfully. Do you want to push the changes to remote? (yes/no)"
- If no commit was made: "No new commit was created. Do you want to push any existing commits to remote? (yes/no)"

**MANDATORY STEP 2**: If user says "yes": Push the changes to remote

**CHECKPOINT**: Push confirmation MUST be asked - this is the final step of the workflow

---

## CRITICAL WORKFLOW - STRICT PHASE SEQUENCE

This workflow has **6 MANDATORY PHASES** that MUST be executed in order. Each phase has **REQUIRED CHECKPOINTS**
that CANNOT be skipped:

### PHASE 1: Collection Phase

- ONLY collect decisions (yes/no/skip/all) and create tasks - NO execution
- **CHECKPOINT**: ALL suggestions have been presented and user decisions collected

### PHASE 2: Execution Phase

- ONLY execute tasks after ALL suggestions reviewed - NO more questions
- Process ALL approved tasks (HIGH, MEDIUM, LOW priority)
- Track any tasks where AI decides not to make changes (with reasoning)
- **CHECKPOINT**: ALL approved tasks have been processed (implemented or reasoned skip)

### PHASE 3: Unimplemented Changes Review

- **MANDATORY STEP 1**: Show summary of any approved tasks where AI decided not to make changes
- **MANDATORY STEP 2**: Explain WHY changes were not made for each
- **MANDATORY STEP 3**: Ask user: "Do you approve proceeding without these changes? (yes/no)"
- **MANDATORY STEP 4**: If user says no, re-implement the changes
- **CHECKPOINT**: User has approved all unimplemented changes OR all tasks were implemented

### PHASE 4: Testing & Commit Phase

- **MANDATORY STEP 1**: Run all tests WITH coverage
- **MANDATORY STEP 2**: Check BOTH tests AND coverage - only proceed if BOTH pass
  - If tests pass BUT coverage fails - FIX coverage gaps (this is a FAILURE)
  - If tests fail - FIX test failures
- **MANDATORY STEP 3**: Once BOTH pass, MUST ask user: "All tests and coverage pass. Do you want to commit the
  changes? (yes/no)"
- **MANDATORY STEP 4**: If user says yes: Commit the changes
- **CHECKPOINT**: Tests AND coverage BOTH pass, AND commit confirmation asked (even if user declined)

### PHASE 5: Post Qodo Reply

- Update the JSON file with reply messages and status for each processed comment
- Call the posting script to post replies and resolve threads
- **CHECKPOINT**: All replies posted successfully

### PHASE 6: Push Phase

- **MANDATORY STEP 1**: After Phase 5 completion, MUST ask about pushing:
  - If a commit was made: "Changes committed successfully. Do you want to push the changes to remote? (yes/no)"
  - If no commit was made: "No new commit was created. Do you want to push any existing commits to remote? (yes/no)"
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
- Re-run tests with coverage until BOTH pass before proceeding to Phase 4's commit confirmation.
