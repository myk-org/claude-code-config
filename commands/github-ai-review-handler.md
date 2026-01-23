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
1. Fetches suggestions from BOTH Qodo and CodeRabbit
2. Detects and marks duplicates (same file + similar issue)
3. Presents suggestions with source attribution
4. Implements approved changes (AI picks one version for duplicates)
5. Replies to ALL threads (both Qodo AND CodeRabbit)
6. Resolves ALL threads (both Qodo AND CodeRabbit)
7. Supports optional URL arguments with auto-detection of AI source

---

## Key Concepts

### Comment Sources and Reply Mechanisms

**Qodo (`qodo-code-review[bot]`):**
- **Issue comments**: URL contains `#issuecomment-XXX` - Cannot be resolved, reply is a new issue comment
- **Inline review comments**: Part of PR review threads - CAN be resolved, reply threads and resolves

**CodeRabbit (`coderabbitai[bot]`):**
- **Review body comments**: Part of the PR review body - Reply via reply script, can resolve
- **Inline review comments**: Part of PR review threads - CAN be resolved, reply threads and resolves

### Deduplication

When the same issue is flagged by BOTH AI reviewers:
- Marked as duplicate with `is_duplicate: true`
- Shows both sources in presentation
- AI picks one implementation (both are valid)
- Replies sent to BOTH Qodo AND CodeRabbit threads

---

## Instructions

### Step 1: Fetch from BOTH AI reviewers

Run extraction scripts to get comments from each AI reviewer.

**Script paths:**

```bash
QODO_SCRIPT="$HOME/.claude/commands/scripts/github-qodo-review-handler/get-qodo-comments.sh"
CODERABBIT_SCRIPT="$HOME/.claude/commands/scripts/github-coderabbitai-review-handler/get-coderabbit-comments.sh"
PR_INFO_SCRIPT="$HOME/.claude/commands/scripts/general/get-pr-info.sh"
DETECT_SCRIPT="$HOME/.claude/commands/scripts/general/get-reviewer-from-url.sh"
```

**Usage patterns:**

1. **No URL provided** - Fetches all unresolved from both:

   ```bash
   "$QODO_SCRIPT" "$PR_INFO_SCRIPT"
   "$CODERABBIT_SCRIPT" "$PR_INFO_SCRIPT"
   ```

2. **URL(s) provided** - Auto-detect source and route appropriately:

   For each URL argument:

   ```bash
   # Detect which AI reviewer authored the comment
   SOURCE=$("$DETECT_SCRIPT" "<url>")

   # Route to appropriate script
   if [ "$SOURCE" = "qodo" ]; then
     "$QODO_SCRIPT" "$PR_INFO_SCRIPT" "<url>"
   elif [ "$SOURCE" = "coderabbit" ]; then
     "$CODERABBIT_SCRIPT" "$PR_INFO_SCRIPT" "<url>"
   fi
   ```

   Then also fetch all unresolved from the OTHER source (to catch any additional comments).

**Examples:**

- `/github-ai-review-handler` - All unresolved from both
- `/github-ai-review-handler <qodo_url>` - Specific Qodo + all CodeRabbit
- `/github-ai-review-handler <coderabbit_url>` - All Qodo + specific CodeRabbit
- `/github-ai-review-handler <url1> <url2>` - Specific from each (auto-detected)

**IMPORTANT:** The scripts handle everything. Do NOT do additional bash manipulation.

### Step 2: Merge and Deduplicate

After receiving JSON from both scripts, merge and detect duplicates.

**Deduplication criteria:**
- Same file path
- Overlapping or adjacent line ranges (within 5 lines)
- Similar title/category (fuzzy match - same keywords or semantic meaning)

**For duplicates:**
- Keep both suggestions in the list but mark the second one as duplicate
- Set `is_duplicate: true` on the duplicate
- Set `duplicate_of: <id>` pointing to the original
- Include `duplicate_sources: ["qodo", "coderabbit"]` on the original

**Merged data structure:**

```json
{
  "metadata": {
    "owner": "...",
    "repo": "...",
    "pr_number": "..."
  },
  "summary": {
    "qodo": { "count": 5, "high": 2, "medium": 1, "low": 2 },
    "coderabbit": { "count": 4, "actionable": 2, "nitpicks": 2 },
    "duplicates": 2,
    "total_unique": 7
  },
  "suggestions": [
    {
      "id": 1,
      "ai_source": "qodo",
      "is_duplicate": false,
      "duplicate_of": null,
      "duplicate_sources": ["qodo", "coderabbit"],
      "source": "inline_review",
      "thread_id": "PRRT_xxx",
      "comment_id": "123456",
      "priority": "HIGH",
      "category": "Bug Fix",
      "title": "Missing null check",
      "file": "src/main.py",
      "line_range": "42-45",
      "description": "...",
      "suggested_diff": "..."
    },
    {
      "id": 2,
      "ai_source": "coderabbit",
      "is_duplicate": true,
      "duplicate_of": 1,
      "source": "inline_review",
      "thread_id": "PRRT_yyy",
      "comment_id": "789012",
      "priority": "HIGH",
      "title": "Potential null reference",
      "file": "src/main.py",
      "line_range": "42",
      "description": "...",
      "body": "..."
    }
  ]
}
```

### Step 2.5: Filter Positive Comments

#### CRITICAL: Filter Positive Comments Before Presentation

Before presenting MEDIUM priority comments to user, classify each duplicate/positive comment.

For each comment, analyze the title and body to filter out positive feedback:

**POSITIVE (Filter Out) - Comments that are:**
- Praise/acknowledgment: Contains words like "good", "great", "nice", "excellent", "perfect", "well done", "correct"
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
Source: [Inline Review | Issue Comment | Review Body]
File: [file path]
Lines: [line_range]
Title: [title]
Description: [description]

Suggested Diff (if available):
[suggested_diff or "No diff provided"]

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

**CRITICAL: Track Suggestion Outcomes for Reply**

For EVERY suggestion presented, track the outcome for the final reply:
- **Suggestion ID**: The unique ID from merged data
- **AI Source(s)**: Which AI reviewer(s) flagged this (qodo, coderabbit, or both)
- **Thread ID(s)**: The GraphQL thread ID(s) for replying/resolving
- **Comment ID(s)**: The specific comment ID(s) for each source
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
   - Use the `suggested_diff` or `body` as guidance when implementing changes
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

  1. [PRIORITY] Priority - File: [file] - Line: [line_range]
     AI Source: [Qodo | CodeRabbit | Both]
     Title: [title]
     Reason AI did not implement: [Explain why no changes were made - e.g., "Current code already
     implements the suggestion", "Suggestion is not applicable", "Suggested change would break existing
     functionality"]

  2. [PRIORITY] Priority - File: [file] - Line: [line_range]
     AI Source: [Qodo | CodeRabbit | Both]
     Title: [title]
     Reason AI did not implement: [Explain why no changes were made]
  ...
  ```

- **MANDATORY**: Ask user for confirmation:

  ```text
  Do you approve proceeding without these changes? (yes/no)
  - yes: Proceed to Phase 3.5 (Post AI Review Replies)
  - no: Reconsider and implement the changes
  ```

- **If user says "no"**: Re-implement the changes as requested
- **If user says "yes"**: Proceed to Phase 3.5

**If ALL approved tasks were implemented**: Proceed directly to Phase 3.5

**CHECKPOINT**: User has reviewed and approved all unimplemented changes OR all approved tasks were implemented

### Step 6: PHASE 3.5 - Post Replies to ALL AI Sources

**MANDATORY**: After Phase 3 approval (or if all tasks were implemented), generate and post replies to
ALL AI reviewers that flagged each suggestion.

**CRITICAL: For duplicates, reply to BOTH Qodo AND CodeRabbit threads**

---

#### Qodo Issue Comment Suggestions

Post a **NEW issue comment** as the reply (cannot thread or resolve):

**Reply format:**

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
*Automated response from AI Review Handler*
```

**Post command:**

```bash
gh api "/repos/$OWNER/$REPO/issues/$PR_NUMBER/comments" \
  -X POST -f body="$REPLY_MESSAGE"
```

---

#### Qodo Inline Review Suggestions

Reply to thread AND resolve using GraphQL:

**For ADDRESSED suggestions:**

```bash
# Reply to the inline comment thread
gh api graphql -f query='
  mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: $threadId,
      body: $body
    }) {
      comment { id }
    }
  }
' -f threadId="$THREAD_ID" -f body="Done"

# Resolve the thread
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {
      threadId: $threadId
    }) {
      thread { isResolved }
    }
  }
' -f threadId="$THREAD_ID"
```

**For SKIPPED or NOT ADDRESSED suggestions:**

```bash
# Reply with reason
gh api graphql -f query='
  mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: $threadId,
      body: $body
    }) {
      comment { id }
    }
  }
' -f threadId="$THREAD_ID" -f body="Not addressed: [reason]"

# ALWAYS resolve the thread (even for skipped/not addressed)
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {
      threadId: $threadId
    }) {
      thread { isResolved }
    }
  }
' -f threadId="$THREAD_ID"
```

---

#### CodeRabbit Review Body Comments

Post threaded replies using the reply script:

**For ADDRESSED comments:**

```bash
~/.claude/scripts/reply-to-pr-review.sh "<owner>/<repo>" "<pr_number>" "Done" --comment-id <comment_id> --resolve
```

**For NOT ADDRESSED or SKIPPED comments:**

```bash
~/.claude/scripts/reply-to-pr-review.sh "<owner>/<repo>" "<pr_number>" "<reason>" --comment-id <comment_id> --resolve
```

---

#### CodeRabbit Inline Review Comments

Reply to thread AND resolve using GraphQL (same as Qodo inline):

**For ADDRESSED comments:**

```bash
# Reply to the inline comment thread
gh api graphql -f query='
  mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: $threadId,
      body: $body
    }) {
      comment { id }
    }
  }
' -f threadId="$THREAD_ID" -f body="Done"

# Resolve the thread
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {
      threadId: $threadId
    }) {
      thread { isResolved }
    }
  }
' -f threadId="$THREAD_ID"
```

**For SKIPPED or NOT ADDRESSED comments:**

```bash
# Reply with reason
gh api graphql -f query='
  mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: $threadId,
      body: $body
    }) {
      comment { id }
    }
  }
' -f threadId="$THREAD_ID" -f body="Not addressed: [reason]"

# ALWAYS resolve the thread (even for skipped/not addressed)
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {
      threadId: $threadId
    }) {
      thread { isResolved }
    }
  }
' -f threadId="$THREAD_ID"
```

---

#### Handling Duplicates

**CRITICAL: For suggestions flagged by BOTH AI reviewers, reply to BOTH threads:**

1. Reply to Qodo thread (using Qodo's thread_id)
2. Reply to CodeRabbit thread (using CodeRabbit's thread_id)
3. Resolve BOTH threads if addressed

**Example for duplicate that was addressed:**

```bash
# Reply to Qodo thread
gh api graphql -f query='...' -f threadId="$QODO_THREAD_ID" -f body="Done"
gh api graphql -f query='...' -f threadId="$QODO_THREAD_ID"  # Resolve

# Reply to CodeRabbit thread
gh api graphql -f query='...' -f threadId="$CODERABBIT_THREAD_ID" -f body="Done"
gh api graphql -f query='...' -f threadId="$CODERABBIT_THREAD_ID"  # Resolve
```

---

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

- Fetch from BOTH Qodo and CodeRabbit
- Merge and deduplicate suggestions
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

### PHASE 3.5: Post AI Review Replies

- Generate summary reply from tracked outcomes
- **For Qodo issue comments**: Post NEW issue comment to PR
- **For Qodo inline reviews**: Reply to thread AND resolve via GraphQL
- **For CodeRabbit review body**: Reply using reply script
- **For CodeRabbit inline reviews**: Reply to thread AND resolve via GraphQL
- **For duplicates**: Reply to BOTH Qodo AND CodeRabbit threads
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
- **NEVER forget duplicate threads** - if a suggestion was flagged by both AI reviewers, reply to BOTH
- **COMPLETE each phase fully** before starting the next phase

**If tests OR coverage fail**:
- Analyze and fix failures (add tests for coverage gaps)
- Re-run tests with coverage until BOTH pass before proceeding to Phase 4's commit confirmation.
