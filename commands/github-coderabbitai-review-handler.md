---
skipConfirmation: true
---

# GitHub CodeRabbit AI Review Handler

**Description:** Finds and processes CodeRabbit AI comments from the current branch's GitHub PR with
priority-based handling.

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

### Step 1: Fetch CodeRabbit comments using the unified fetcher

**Script path:**

```text
FETCHER_SCRIPT = ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh
```

### CRITICAL: Simple Command - DO NOT OVERCOMPLICATE

**ALWAYS use this exact command format:**

```bash
$FETCHER_SCRIPT [USER_INPUT_IF_PROVIDED]
```

**That's it. Nothing more. No script extraction. No variable assignments. Just one simple command.**

---

**Usage patterns:**

1. **No URL provided**: Fetches all unresolved inline review comments from the PR

   ```bash
   ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh
   ```

2. **Review URL provided**: Fetches comments from that specific review plus all unresolved

   ```bash
   # User provided review URL:
   ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh \
     "https://github.com/owner/repo/pull/123#pullrequestreview-3379917343"

   # User provided review ID:
   ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh 3379917343
   ```

**If user provides NO input:**

The script will fetch all unresolved inline review comments. If you want to process a specific review,
instruct the user:

```text
Running without arguments will fetch all unresolved inline review comments.

To process a specific CodeRabbit review, provide its URL or ID:
1. Go to the GitHub PR page
2. Find the CodeRabbit review you want to process
3. Click on the review timestamp/link
4. Copy the URL from your browser (it will contain #pullrequestreview-XXXXXXXXXX)

Example:
  /github-coderabbitai-review-handler https://github.com/owner/repo/pull/123#pullrequestreview-3379917343

Or just provide the review ID number:
  /github-coderabbitai-review-handler 3379917343
```

**THAT'S ALL. DO NOT extract scripts, get PR info, or do ANY bash manipulation. The scripts handle
EVERYTHING.**

### Step 2: Process the JSON output

The unified fetcher returns structured JSON with categorized comments.

**IMPORTANT: This command only processes CodeRabbit comments. Filter to use only the `coderabbit` array.**

**JSON structure:**

```json
{
  "metadata": {
    "owner": "...",
    "repo": "...",
    "pr_number": "...",
    "json_path": "/tmp/claude/pr-<number>-reviews.json"
  },
  "human": [...],
  "qodo": [...],
  "coderabbit": [
    {
      "thread_id": "PRRT_xxx",
      "node_id": "PRRC_xxx",
      "comment_id": 123456,
      "author": "coderabbitai[bot]",
      "path": "src/file.py",
      "line": 42,
      "body": "...",
      "priority": "HIGH",
      "source": "coderabbit",
      "reply": null,
      "status": "pending"
    }
  ]
}
```

**Each comment in the `coderabbit` array has:**
- `thread_id`: GraphQL thread ID for replying and resolving (may be null for REST API fetches)
- `node_id`: REST API node ID (fallback for thread_id)
- `comment_id`: Numeric comment ID
- `author`: Always `coderabbitai[bot]`
- `path`: File path
- `line`: Line number (may be null)
- `body`: The comment content
- `priority`: Already classified as HIGH, MEDIUM, or LOW by the fetcher
- `source`: Always `coderabbit`
- `reply`: null initially, updated after processing
- `status`: `pending` initially, updated after processing

**Note**: For inline review comments, `thread_id` is present for GraphQL operations.
For comments fetched via REST API (specific review URL), `thread_id` may be null but `node_id` is available.

### Step 2.5: Filter Positive Comments

**CRITICAL: Before presenting comments to user, classify each to filter out positive feedback.**

For each comment in `coderabbit` array, analyze the body to determine:

**POSITIVE (Filter Out) - Comments that are:**

- Praise/acknowledgment: Contains words like "good", "great", "nice", "excellent", "perfect", "well done",
  "correct"
- Positive feedback on fixes: "good fix", "nice improvement", "better approach", "correct implementation"
- Acknowledgment without suggestions: No action words like "should", "consider", "recommend", "suggest", "try"

**ACTIONABLE (Keep) - Comments that:**

- Contain suggestions: "should", "consider", "recommend", "suggest", "could", "might want to"
- Point out issues: "issue", "problem", "concern", "potential", "risk"
- Request changes: "change", "update", "modify", "improve", "refactor"

**Examples:**

- POSITIVE (filter out): "Windows-safe resource import guard: good portability fix"
- POSITIVE (filter out): "Nice error handling improvement"
- ACTIONABLE (keep): "Consider adding error handling here"
- ACTIONABLE (keep): "This could cause performance issues"

After classification, remove all POSITIVE comments before proceeding to Step 3.

### Step 3: PHASE 1 - Collect User Decisions (COLLECTION ONLY - NO PROCESSING)

**CRITICAL: This is the COLLECTION phase. Do NOT execute, implement, or process ANY comments yet. Only ask
questions and create tasks.**

Go through ALL comments in priority order, collecting user decisions:

1. **HIGH Priority** first
2. **MEDIUM Priority** second
3. **LOW Priority** last

**IMPORTANT: Present each comment individually, WAIT for user response, but NEVER execute, implement, or
process anything during this phase.**

For ALL comments, use this unified format:

```text
[PRIORITY_EMOJI] [PRIORITY] Priority - Comment X of Y
Source: CodeRabbit
File: [path]
Line: [line] (if available)
Description: [body]

Do you want to address this comment? (yes/no/skip/all)
```

Note: Use 🔴 for HIGH priority, 🟡 for MEDIUM priority, and 🟢 for LOW priority.

### CRITICAL: Track Comment Outcomes for Reply

For EVERY comment presented, track the outcome for the final reply:
- **Array index**: The index in the `coderabbit` array (for updating JSON)
- **Comment number**: Sequential (1, 2, 3...)
- **File**: The file path
- **Outcome**: Will be one of: `addressed`, `skipped`
- **Reason**: Required for `skipped` outcomes

When user responds:
- **"yes"**: Outcome will be set after execution (addressed)
- **"no" or "skip"**: MUST ask user: "Please provide a brief reason for skipping this comment:"
  - Set outcome = `skipped`, reason = user's response
  - If user doesn't provide reason, use "User chose to skip"
- **"all"**: Track all remaining as pending execution

**For each "yes" response:**

- Create a task with appropriate agent assignment
- Show confirmation: "Task created: [brief description]"
- **DO NOT execute the task - Continue to next comment immediately**

**For "all" response:**

- Create tasks for the current comment AND **ALL remaining comments across ALL priority levels** automatically
- **CRITICAL**: "all" means process EVERY remaining comment (HIGH, MEDIUM, and LOW priority) - do NOT skip any
  priority level
- Show summary: "Created tasks for current comment + X remaining comments (Y HIGH, Z MEDIUM, W LOW)"
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

2. **Process all approved tasks:**
   - **CRITICAL**: Process ALL tasks created during Phase 1, regardless of priority level
   - **NEVER skip LOW-priority tasks** - if a task was created in Phase 1, it MUST be executed in Phase 2
   - Route to appropriate specialists to implement the changes
   - Process multiple tasks in parallel when possible
   - Mark each task as completed after finishing
   - **Track unimplemented changes**: If AI decides NOT to make changes for an approved task, track the reason

   **Update outcome tracking after each task:**
   - If changes were made successfully: Set outcome = `addressed`
   - If AI decided NOT to make changes: Set outcome = `not_addressed`, reason = [explanation of why]

3. **Review unimplemented changes (MANDATORY CHECKPOINT):**

   **CRITICAL: Before proceeding to Phase 3.5, MUST review any approved comments where AI decided not to make
   changes.**

   If AI decided NOT to implement changes for ANY approved tasks (tasks where user said "yes" but AI determined
   no changes needed):
   - **Show summary of unimplemented changes:**

     ```text
     Unimplemented Changes Review (X approved comments not changed):

     1. [PRIORITY] Priority - File: [path] - Line: [line]
        Description: [brief body summary]
        Reason AI did not implement: [Explain why no changes were made - e.g., "Current code already
        implements the suggestion", "Comment is not applicable", "Suggested change would break existing
        functionality"]

     2. [PRIORITY] Priority - File: [path] - Line: [line]
        Description: [brief body summary]
        Reason AI did not implement: [Explain why no changes were made]
     ...
     ```

   - **MANDATORY**: Ask user for confirmation:

     ```text
     Do you approve proceeding without these changes? (yes/no)
     - yes: Proceed to Phase 3.5 (Post CodeRabbit Reply)
     - no: Reconsider and implement the changes
     ```

   - **If user says "no"**: Re-implement the changes as requested
   - **If user says "yes"**: Proceed to Phase 3.5 (Post CodeRabbit Reply)

   **If ALL approved tasks were implemented**: Proceed directly to Phase 3.5

   **CHECKPOINT**: User has reviewed and approved all unimplemented changes OR all approved tasks were implemented

### Step 5: PHASE 3.5 - Post CodeRabbit Reply

**MANDATORY**: After Phase 3 approval (or if all tasks were implemented), update the JSON file and post replies.

---

#### Step 5.1: Update the JSON file

**CRITICAL**: Update the JSON file at the path from `metadata.json_path` with the processing results.

For each processed comment in the `coderabbit` array, update:
- `reply`: Set to the reply message (e.g., "Addressed." or "Skipped: [reason]")
- `status`: Set to `"addressed"` or `"skipped"`

**Example updates:**
- For addressed comments: `reply: "Addressed."`, `status: "addressed"`
- For skipped comments: `reply: "Skipped: [reason]"`, `status: "skipped"`

Use `jq` or similar to update the JSON file in place.

---

#### Step 5.2: Post replies using the posting script

**Script path:**

```text
POSTING_SCRIPT = ~/.claude/commands/scripts/general/post-review-replies-from-json.sh
```

**Run the posting script:**

```bash
~/.claude/commands/scripts/general/post-review-replies-from-json.sh /tmp/claude/pr-<number>-reviews.json
```

The script will:
1. Read the JSON file
2. Find all comments with `status` of `"addressed"` or `"skipped"` that have not been posted yet
3. Post replies to each thread using the `reply` message
4. Resolve each thread
5. Update the JSON with `posted_at` timestamps

**The script handles:**
- Inline review thread replies (using `thread_id` or `node_id`)
- Thread resolution (marks threads as resolved after replying)

**IMPORTANT**: The script only processes comments from the `coderabbit` array since that's what this
command focuses on. Other categories (`human`, `qodo`) are left untouched.

---

**CHECKPOINT**: All replies posted successfully

### Step 6: PHASE 4 - Testing & Commit

**MANDATORY STEP 1**: Run all tests WITH coverage

**MANDATORY STEP 2**: Check BOTH test results AND coverage results:
- **If tests pass AND coverage passes**: MUST ask: "All tests and coverage pass. Do you want to commit
  the changes? (yes/no)"
  - If user says "yes": Commit the changes
  - If user says "no": Acknowledge and proceed to Phase 5 checkpoint (ask about push anyway)
- **If tests pass BUT coverage fails**: This is a FAILURE - do NOT ask about commit yet
  - Analyze coverage gaps and add missing tests
  - Re-run tests with coverage until BOTH pass
- **If tests fail**:
  - Analyze and fix test failures
  - Re-run until tests pass

**CHECKPOINT**: Tests AND coverage BOTH pass, AND commit confirmation asked (even if user declined)

### Step 7: PHASE 5 - Push to Remote

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
- Process ALL approved tasks (HIGH, MEDIUM, LOW priority)
- Track any tasks where AI decides not to make changes (with reasoning)
- **CHECKPOINT**: ALL approved tasks have been processed (implemented or reasoned skip)

### PHASE 3: Unimplemented Changes Review

- **MANDATORY STEP 1**: Show summary of any approved tasks where AI decided not to make changes
- **MANDATORY STEP 2**: Explain WHY changes were not made for each
- **MANDATORY STEP 3**: Ask user: "Do you approve proceeding without these changes? (yes/no)"
- **MANDATORY STEP 4**: If user says no, re-implement the changes
- **CHECKPOINT**: User has approved all unimplemented changes OR all tasks were implemented

### PHASE 3.5: Post CodeRabbit Reply

- Update the JSON file with `reply` and `status` for each processed comment
- Call the posting script to post replies and resolve threads
- **CHECKPOINT**: All replies posted successfully

### PHASE 4: Testing & Commit Phase

- **MANDATORY STEP 1**: Run all tests WITH coverage
- **MANDATORY STEP 2**: Check BOTH tests AND coverage - only proceed if BOTH pass
  - If tests pass BUT coverage fails - FIX coverage gaps (this is a FAILURE)
  - If tests fail - FIX test failures
- **MANDATORY STEP 3**: Once BOTH pass, MUST ask user: "All tests and coverage pass. Do you want to commit the
  changes? (yes/no)"
- **MANDATORY STEP 4**: If user says yes: Commit the changes
- **CHECKPOINT**: Tests AND coverage BOTH pass, AND commit confirmation asked (even if user declined)

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

**If tests OR coverage fail**:

- Analyze and fix failures (add tests for coverage gaps)
- Re-run tests with coverage until BOTH pass before proceeding to Phase 4's commit confirmation.
