---
skipConfirmation: true
---

# GitHub AI Review Handler (Unified)

**Description:** Processes AI code review comments from BOTH Qodo and CodeRabbit with deduplication.

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

## Overview

This unified command:
1. Fetches suggestions from BOTH Qodo and CodeRabbit using a single unified script
2. Detects and marks duplicates (same file + similar issue)
3. Presents suggestions with source attribution
4. Implements approved changes (AI picks one version for duplicates)
5. Updates the JSON file with reply messages and status
6. Posts replies and resolves ALL threads using the posting script
7. Supports optional URL arguments for specific reviews

---

## Key Concepts

### Comment Sources

**Qodo (`qodo-code-review[bot]`):**
- **Issue comments**: URL contains `#issuecomment-XXX` - Cannot be resolved via GraphQL
- **Inline review comments**: Part of PR review threads - CAN be resolved

**CodeRabbit (`coderabbitai[bot]`):**
- **Review body comments**: Part of the PR review body
- **Inline review comments**: Part of PR review threads - CAN be resolved

### JSON Structure

The unified fetcher produces JSON with this structure:

```json
{
  "metadata": {
    "owner": "...",
    "repo": "...",
    "pr_number": "...",
    "json_path": "/tmp/claude/pr-<number>-reviews.json"
  },
  "human": [ ... ],
  "qodo": [ ... ],
  "coderabbit": [ ... ]
}
```

Each comment in the arrays has:
- `thread_id`: GraphQL thread ID for replying/resolving
- `node_id`: REST API node ID (fallback)
- `comment_id`: REST API comment ID
- `author`: Username of commenter
- `path`: File path
- `line`: Line number
- `body`: Comment content
- `priority`: "HIGH", "MEDIUM", or "LOW" (auto-classified)
- `source`: "qodo", "coderabbit", or "human"
- `reply`: null (to be set after processing)
- `status`: "pending" (to be set to "addressed" or "skipped")

### Deduplication

When the same issue is flagged by BOTH AI reviewers:
- Marked as duplicate with `is_duplicate: true`
- Shows both sources in presentation
- AI picks one implementation (both are valid)
- Both Qodo AND CodeRabbit threads are updated and resolved

---

## Instructions

### Step 1: Fetch AI Review Comments

Run the unified fetcher to get all unresolved reviews from both Qodo and CodeRabbit.

**Script path:**

```text
~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh
```

**Usage:**

1. **No URL provided** - Fetches all unresolved from both:

   ```bash
   ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh
   ```

2. **URL provided** - Fetches all unresolved plus ensures specific review is included:

   ```bash
   ~/.claude/commands/scripts/general/get-all-github-unresolved-reviews-for-pr.sh "<review_url>"
   ```

**Examples:**

- `/github-ai-review-handler` - All unresolved from both AI reviewers
- `/github-ai-review-handler https://github.com/org/repo/pull/123#pullrequestreview-456` - All + specific review

**IMPORTANT:** The script handles everything. Do NOT do additional bash manipulation.

The script outputs JSON to stdout and saves to the path in `metadata.json_path`.

### Step 2: Filter to AI Reviews Only

The unified fetcher returns categorized arrays: `human`, `qodo`, `coderabbit`.

**For this command, use ONLY the `qodo` and `coderabbit` arrays.** Ignore the `human` array.

Merge the `qodo` and `coderabbit` arrays into a single list for processing, preserving the `source` field
to track origin.

### Step 2.5: Detect Duplicates and Filter Positive Comments

#### Duplicate Detection

When the same issue is flagged by BOTH AI reviewers:

**Deduplication criteria:**
- Same file path
- Overlapping or adjacent line ranges (within 5 lines)
- Similar title/category (fuzzy match - same keywords or semantic meaning)

**For duplicates:**
- Keep both suggestions in the list but mark the second one as duplicate
- Set `is_duplicate: true` on the duplicate
- Set `duplicate_of: <id>` pointing to the original
- Include `duplicate_sources: ["qodo", "coderabbit"]` on the original

#### Filter Positive Comments

Before presenting MEDIUM-priority comments, filter out positive feedback.

**POSITIVE (Filter Out) - Comments that are:**
- Praise/acknowledgment: Contains words like "good", "great", "nice", "excellent", "perfect", "well done"
- Positive feedback on fixes: "good fix", "nice improvement", "better approach"
- Acknowledgment without suggestions: No action words like "should", "consider", "recommend"

**ACTIONABLE (Keep) - Comments that:**
- Contain suggestions: "should", "consider", "recommend", "suggest", "could", "might want to"
- Point out issues: "issue", "problem", "concern", "potential", "risk"
- Request changes: "change", "update", "modify", "improve", "refactor"

Remove all POSITIVE comments before proceeding to Step 3.

### Step 3: PHASE 1 - Collect User Decisions (COLLECTION ONLY - NO PROCESSING)

**CRITICAL: This is the COLLECTION phase. Do NOT execute, implement, or process ANY suggestions yet. Only ask
questions and create tasks.**

Go through ALL suggestions in priority order, collecting user decisions:

1. **HIGH Priority** first
2. **MEDIUM Priority** second
3. **LOW Priority** last

**IMPORTANT: Skip duplicate suggestions (is_duplicate: true) during presentation - they will be handled
automatically when the original is processed.**

**Unified presentation format:**

```text
[PRIORITY_EMOJI] [PRIORITY] Priority - Suggestion X of Y
[AI_SOURCE_LINE]
[DUPLICATE_LINE if applicable]
File: [file path]
Line: [line]
Body: [body]

Do you want to address this suggestion? (yes/no/skip/all)
```

**Priority emojis:** Use 🔴 for HIGH, 🟡 for MEDIUM, 🟢 for LOW.

**AI Source line formats:**
- Single source: `AI Source: Qodo` or `AI Source: CodeRabbit`
- Duplicate: `AI Source: DUPLICATE - Found in both Qodo and CodeRabbit`

**For duplicates found in both:**
```text
DUPLICATE: This issue was flagged by both Qodo and CodeRabbit.
           Addressing this will resolve threads in BOTH systems.
```

#### Track Suggestion Outcomes for Reply

For EVERY suggestion presented, track the outcome for the final reply:
- **thread_id**: The GraphQL thread ID for replying/resolving
- **source**: Which AI reviewer flagged this (qodo or coderabbit)
- **path**: The file path
- **line**: The line number
- **Outcome**: Will be one of: `addressed`, `skipped`
- **Reason**: Required for `skipped` outcomes

When user responds:
- **"yes"**: Outcome will be set after execution (addressed or not_addressed)
- **"no" or "skip"**: MUST ask user: "Please provide a brief reason for skipping this suggestion:"
  - Set outcome = `skipped`, reason = user's response
  - If user doesn't provide reason, use "User chose to skip"
- **"all"**: Track all remaining as pending execution

**For each "yes" response:**
- Create a task with appropriate agent assignment
- Show confirmation: "Task created: [brief description]"
- **DO NOT execute the task - Continue to next suggestion immediately**

**For "all" response:**
- Create tasks for the current suggestion AND **ALL remaining suggestions across ALL priority levels**
- **CRITICAL**: "all" means process EVERY remaining suggestion (HIGH, MEDIUM, and LOW) - do NOT skip any
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

2. **Process all approved tasks:**
   - **CRITICAL**: Process ALL tasks created during Phase 1, regardless of priority level
   - **NEVER skip LOW-priority tasks** - if a task was created in Phase 1, it MUST be executed in Phase 2
   - Use the `body` field as guidance when implementing changes
   - Route to appropriate specialists to implement the changes
   - Process multiple tasks in parallel when possible
   - Mark each task as completed after finishing
   - **Track unimplemented changes**: If AI decides NOT to make changes for an approved task, track the reason

   **Update outcome tracking after each task:**
   - If changes were made successfully: Set outcome = `addressed`
   - If AI decided NOT to make changes: Set outcome = `not_addressed`, reason = [explanation of why]

### Step 5: PHASE 3 - Review Unimplemented Changes

**MANDATORY CHECKPOINT**: Before proceeding to posting replies, MUST review any approved suggestions where AI
decided not to make changes.

If AI decided NOT to implement changes for ANY approved tasks (tasks where user said "yes" but AI determined
no changes needed):

- **Show summary of unimplemented changes:**

  ```text
  Unimplemented Changes Review (X approved suggestions not changed):

  1. [PRIORITY] Priority - File: [file] - Line: [line]
     AI Source: [Qodo | CodeRabbit | Both]
     Body: [body excerpt]
     Reason AI did not implement: [Explain why no changes were made]

  2. [PRIORITY] Priority - File: [file] - Line: [line]
     AI Source: [Qodo | CodeRabbit | Both]
     Body: [body excerpt]
     Reason AI did not implement: [Explain why no changes were made]
  ...
  ```

- **MANDATORY**: Ask user for confirmation:

  ```text
  Do you approve proceeding without these changes? (yes/no)
  - yes: Proceed to Phase 3.5 (Update JSON and Post Replies)
  - no: Reconsider and implement the changes
  ```

- **If user says "no"**: Re-implement the changes as requested
- **If user says "yes"**: Proceed to Phase 3.5

**If ALL approved tasks were implemented**: Proceed directly to Phase 3.5

**CHECKPOINT**: User has reviewed and approved all unimplemented changes OR all approved tasks were implemented

### Step 6: PHASE 3.5 - Update JSON and Post Replies

**MANDATORY**: After Phase 3 approval (or if all tasks were implemented), update the JSON file and post
replies to all AI reviewers.

#### Step 6a: Update the JSON File

Read the JSON file from the path stored in `metadata.json_path` and update each processed comment:

**For ADDRESSED suggestions:**
- Set `reply` to `"Done"` or a brief description of the fix
- Set `status` to `"addressed"`

**For SKIPPED suggestions:**
- Set `reply` to `"Skipped: <reason>"` where reason is the user's skip reason
- Set `status` to `"skipped"`

**For duplicates:**
Update BOTH the original Qodo thread AND the duplicate CodeRabbit thread (or vice versa).

**Example update for a qodo comment:**

```json
{
  "thread_id": "PRRT_xxx",
  "node_id": "...",
  "comment_id": 123456,
  "author": "qodo-code-review[bot]",
  "path": "src/main.py",
  "line": 42,
  "body": "...",
  "priority": "HIGH",
  "source": "qodo",
  "reply": "Done",
  "status": "addressed"
}
```

Write the updated JSON back to the same file path.

#### Step 6b: Post Replies Using the Posting Script

After updating the JSON, call the posting script:

```bash
~/.claude/commands/scripts/general/post-review-replies-from-json.sh "<json_path>"
```

Where `<json_path>` is the value from `metadata.json_path` (e.g., `/tmp/claude/pr-123-reviews.json`).

**The script handles:**
- Reading the updated JSON
- Posting replies to each thread with `status` of "addressed" or "skipped"
- Resolving all processed threads
- Updating the JSON with `posted_at` timestamps
- Skipping threads that are still "pending"

**CHECKPOINT**: All replies posted to ALL AI sources (Qodo AND CodeRabbit)

### Step 7: PHASE 4 - Testing & Commit

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

- Fetch from unified script (covers BOTH Qodo and CodeRabbit)
- Filter to use only `qodo` and `coderabbit` arrays
- Detect duplicates and filter positive comments
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

### PHASE 3.5: Update JSON and Post Replies

- Update JSON file (at `metadata.json_path`) with `reply` and `status` for each processed comment
- For duplicates, update BOTH the Qodo AND CodeRabbit threads
- Call the posting script: `post-review-replies-from-json.sh <json_path>`
- The script posts replies, resolves threads, and updates timestamps
- **CHECKPOINT**: All replies posted to ALL AI sources

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
- **NEVER forget duplicate threads** - if a suggestion was flagged by both AI reviewers, update BOTH in JSON
- **COMPLETE each phase fully** before starting the next phase

**If tests OR coverage fail**:
- Analyze and fix failures (add tests for coverage gaps)
- Re-run tests with coverage until BOTH pass before proceeding to Phase 4's commit confirmation.
