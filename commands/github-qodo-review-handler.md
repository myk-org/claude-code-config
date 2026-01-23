---
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

## Key Differences from CodeRabbit

**IMPORTANT**: Qodo uses **two types of comments**, which affects how we handle them:

1. **Bot username**: `qodo-code-review[bot]`
2. **Comment types**:
   - **Issue comments**: URL contains `#issuecomment-XXX` - Cannot be resolved, reply is a new issue comment
   - **Inline review comments**: Part of PR review threads - CAN be resolved, reply threads and resolves
3. **Reply mechanism differs by type**:
   - Issue comments: Post a NEW issue comment (cannot thread replies)
   - Inline reviews: Reply to thread AND resolve it via GraphQL

---

## Instructions

### Step 1: Get Qodo comments using the extraction script

MAIN_SCRIPT = ~/.claude/commands/scripts/github-qodo-review-handler/get-qodo-comments.sh
PR_INFO_SCRIPT = ~/.claude/commands/scripts/general/get-pr-info.sh

### CRITICAL: Simple Command - DO NOT OVERCOMPLICATE

**ALWAYS use this exact command format:**

```bash
$MAIN_SCRIPT $PR_INFO_SCRIPT <USER_INPUT_IF_PROVIDED>
```

**That's it. Nothing more. No script extraction. No variable assignments. Just one simple command.**

---

**Usage patterns:**

1. **No URL provided**: Fetches all unresolved inline review comments from the PR
   ```bash
   $MAIN_SCRIPT $PR_INFO_SCRIPT
   ```

2. **Issue comment URL provided**: Fetches that issue comment + all unresolved inline comments
   ```bash
   $MAIN_SCRIPT $PR_INFO_SCRIPT "https://github.com/owner/repo/pull/123#issuecomment-2838476123"
   ```

3. **PR review URL provided**: Fetches comments from that specific review only
   ```bash
   $MAIN_SCRIPT $PR_INFO_SCRIPT "https://github.com/owner/repo/pull/123#pullrequestreview-2838476123"
   ```

**If user provides NO input:**

The script will fetch all unresolved inline review comments. If you want to also process an issue comment,
instruct the user:

```text
Running without arguments will fetch all unresolved inline review comments.

To also include a specific Qodo issue comment, provide its URL:
1. Go to the GitHub PR page
2. Find the Qodo review comment you want to process (from qodo-code-review[bot])
3. Click on the comment timestamp/link
4. Copy the URL from your browser

Example:
  /github-qodo-review-handler https://github.com/owner/repo/pull/123#issuecomment-2838476123
```

**THAT'S ALL. DO NOT extract scripts, get PR info, or do ANY bash manipulation. The scripts handle
EVERYTHING.**

### Step 2: Process the JSON output

The script returns structured JSON containing:

- `metadata`: Contains `owner`, `repo`, `pr_number`, `comment_id`, `comment_type` (review|improve)
- `summary`: Counts by priority level, plus `by_source` breakdown:
  - `by_source.issue_comment`: Count of suggestions from issue comments
  - `by_source.inline_review`: Count of suggestions from inline review threads
- `suggestions`: Array of items with:
  - `source`: Either `"issue_comment"` or `"inline_review"` - indicates comment origin
  - `thread_id`: (inline reviews only) The GraphQL thread ID for replying/resolving
  - `comment_id`: (inline reviews only) The specific comment ID in the thread
  - `priority`: HIGH, MEDIUM, or LOW
  - `category`: The type of suggestion (e.g., "Enhancement", "Bug Fix", "Code Style")
  - `title`: Brief description of the suggestion
  - `file`: File path affected
  - `line_range`: Line number or range (e.g., "42" or "42-50")
  - `importance`: Why this change matters
  - `description`: Full description of the suggestion
  - `suggested_diff`: The proposed code change (if provided)

**Note**: For issue comments, the `metadata.comment_id` applies to the entire comment.
For inline reviews, each suggestion has its own `thread_id` and `comment_id` for
replying and resolving.

### Step 3: PHASE 1 - Collect User Decisions (COLLECTION ONLY - NO PROCESSING)

**CRITICAL: This is the COLLECTION phase. Do NOT execute, implement, or process ANY comments yet. Only ask
questions and create tasks.**

Go through ALL suggestions in priority order, collecting user decisions:

1. **HIGH Priority** first
2. **MEDIUM Priority** second
3. **LOW Priority** last

**IMPORTANT: Present each suggestion individually, WAIT for user response, but NEVER execute, implement, or
process anything during this phase.**

For ALL suggestions, use this unified format:

```text
🔴 [PRIORITY] Priority - Suggestion X of Y
📍 Source: [Inline Review | Issue Comment]
📁 File: [file path]
📍 Lines: [line_range]
📋 Title: [title]
💬 Description: [description]

Suggested Diff:
[suggested_diff if available, otherwise "No diff provided"]

Do you want to address this suggestion? (yes/no/skip/all)
```

Note: Use 🔴 for HIGH priority, 🟡 for MEDIUM priority, and 🟢 for LOW priority.
Note: Source indicates where the suggestion came from - "Inline Review" can be resolved, "Issue Comment" cannot.

**CRITICAL: Track Suggestion Outcomes for Reply**

For EVERY suggestion presented, track the outcome for the final reply:
- **Suggestion number**: Sequential (1, 2, 3...)
- **Category**: The suggestion category
- **Title**: The suggestion title
- **File**: The file path
- **Outcome**: Will be one of: `addressed`, `not_addressed`, `skipped`
- **Reason**: Required for `not_addressed` and `skipped` outcomes

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

2. **Process all approved tasks:**
   - **CRITICAL**: Process ALL tasks created during Phase 1, regardless of priority level
   - **NEVER skip LOW priority tasks** - if a task was created in Phase 1, it MUST be executed in Phase 2
   - Use the `suggested_diff` as guidance when implementing changes
   - Route to appropriate specialists to implement the changes
   - Process multiple tasks in parallel when possible
   - Mark each task as completed after finishing
   - **Track unimplemented changes**: If AI decides NOT to make changes for an approved task, track the reason

   **Update outcome tracking after each task:**
   - If changes were made successfully: Set outcome = `addressed`
   - If AI decided NOT to make changes: Set outcome = `not_addressed`, reason = [explanation of why]

### Step 5: PHASE 3 - Review Unimplemented Changes

**MANDATORY CHECKPOINT**: Before proceeding to posting reply, MUST review any approved suggestions where AI
decided not to make changes.

If AI decided NOT to implement changes for ANY approved tasks (tasks where user said "yes" but AI determined
no changes needed):

- **Show summary of unimplemented changes:**

  ```text
  Unimplemented Changes Review (X approved suggestions not changed):

  1. [PRIORITY] Priority - File: [file] - Line: [line_range]
     Category: [category]
     Title: [title]
     Reason AI did not implement: [Explain why no changes were made - e.g., "Current code already
     implements the suggestion", "Suggestion is not applicable", "Suggested change would break existing
     functionality"]

  2. [PRIORITY] Priority - File: [file] - Line: [line_range]
     Category: [category]
     Title: [title]
     Reason AI did not implement: [Explain why no changes were made]
  ...
  ```

- **MANDATORY**: Ask user for confirmation:

  ```text
  Do you approve proceeding without these changes? (yes/no)
  - yes: Proceed to Phase 3.5 (Post Qodo Reply)
  - no: Reconsider and implement the changes
  ```

- **If user says "no"**: Re-implement the changes as requested
- **If user says "yes"**: Proceed to Phase 3.5 (Post Qodo Reply)

**If ALL approved tasks were implemented**: Proceed directly to Phase 3.5

**CHECKPOINT**: User has reviewed and approved all unimplemented changes OR all approved tasks were implemented

### Step 6: PHASE 3.5 - Post Qodo Reply

**MANDATORY**: After Phase 3 approval (or if all tasks were implemented), generate and post replies.

**Handling differs by source type:**

---

#### For Issue Comment Suggestions

Post a **NEW issue comment** as the reply (cannot thread or resolve):

**STEP 1**: Generate reply message using this format:

```markdown
## Qodo Review Response

### Addressed
| Category | Title | File |
|----------|-------|------|
| [category] | [title] | `[file]` |

### Not Addressed
| Category | Title | File | Reason |
|----------|-------|------|--------|
| [category] | [title] | `[file]` | [reason] |

### Skipped
| Category | Title | File | Reason |
|----------|-------|------|--------|
| [category] | [title] | `[file]` | [reason] |

---
*Automated response from Qodo Review Handler*
```

**Notes on format:**
- Only include sections that have items (if no skipped items, omit "Skipped" section)
- Include count in header: "### Addressed (3)"
- File paths should be in backticks for code formatting

**STEP 2**: Post the reply as a new issue comment:

```bash
gh api "/repos/$OWNER/$REPO/issues/$PR_NUMBER/comments" \
  -X POST -f body="$REPLY_MESSAGE"
```

---

#### For Inline Review Suggestions

Reply to the thread AND resolve it using GraphQL:

**STEP 1**: For each addressed inline review suggestion, reply to the thread:

```bash
# Reply to the inline comment thread
gh api graphql -f query='
  mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewComment(input: {
      pullRequestReviewThreadId: $threadId,
      body: $body
    }) {
      comment { id }
    }
  }
' -f threadId="$THREAD_ID" -f body="Done"
```

**STEP 2**: Resolve the thread:

```bash
# Resolve the thread
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolvePullRequestReviewThread(input: {
      threadId: $threadId
    }) {
      thread { isResolved }
    }
  }
' -f threadId="$THREAD_ID"
```

**Where to get values:**
- `$THREAD_ID`: From suggestion's `thread_id` field
- For skipped/not addressed: Reply with reason, optionally leave unresolved

**STEP 3**: For skipped or not addressed inline reviews, reply with the reason but do NOT resolve:

```bash
gh api graphql -f query='
  mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewComment(input: {
      pullRequestReviewThreadId: $threadId,
      body: $body
    }) {
      comment { id }
    }
  }
' -f threadId="$THREAD_ID" -f body="Not addressed: [reason]"
```

---

**Where to get values (for issue comments):**
- `$OWNER`: From JSON `metadata.owner`
- `$REPO`: From JSON `metadata.repo`
- `$PR_NUMBER`: From JSON `metadata.pr_number`
- `$REPLY_MESSAGE`: The generated reply from STEP 1

**STEP 4**: Confirm all replies were posted successfully before proceeding.

**CHECKPOINT**: All replies posted (issue comment AND/OR inline thread replies)

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

### PHASE 3.5: Post Qodo Reply

- Generate summary reply from tracked outcomes
- **For issue comment suggestions**: Post NEW issue comment to PR (cannot thread or resolve)
- **For inline review suggestions**: Reply to thread AND resolve it via GraphQL
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
