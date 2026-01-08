---
skipConfirmation: true
context: fork
---

# GitHub Review Handler

**Description:** Finds and processes human reviewer comments from the current branch's GitHub PR.

MAIN_SCRIPT = ~/.claude/commands/scripts/github-review-handler/get-human-reviews.sh

## 🚨 CRITICAL: SESSION ISOLATION & FLOW ENFORCEMENT

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

### Step 1: Get human review comments using the extraction script

### 🎯 CRITICAL: Simple Command - DO NOT OVERCOMPLICATE

**ALWAYS use this exact command format:**

```bash
$MAIN_SCRIPT $ARGUMENTS
```

**That's it. Nothing more. No script extraction. No variable assignments. Just one simple command.**

---

**If user provides input (PR number or URL):**

```bash
# User provided: 85
$MAIN_SCRIPT 85

# User provided: https://github.com/owner/repo/pull/123
$MAIN_SCRIPT "https://github.com/owner/repo/pull/123"
```

**If user provides NO input:**

```bash
# Auto-detect from current git context - requires being in a git repo with an open PR
$MAIN_SCRIPT
```

Note: The script will auto-detect the repository from the current git context when only a PR number is provided.

### Step 2: Process the JSON output

The script returns structured JSON containing:

- `metadata`: Contains `owner`, `repo`, `pr_number` for use in reply scripts
- `summary`: Total count of human review comments
- `comments`: Array of review comments from human reviewers
  - Each has: comment_id, reviewer, file, line, body

### Step 3: PHASE 1 - Collect User Decisions (COLLECTION ONLY - NO PROCESSING)

**🚨 CRITICAL: This is the COLLECTION phase. Do NOT execute, implement, or process ANY comments yet. Only ask
questions and create tasks.**

Go through ALL comments sequentially, collecting user decisions:

**IMPORTANT: Present each comment individually, WAIT for user response, but NEVER execute, implement, or
process anything during this phase.**

For each comment, present:

```text
👤 Human Review - Comment X of Y
👨‍💻 Reviewer: [reviewer name]
📁 File: [file path]
📍 Line: [line]
💬 Comment: [body]

Do you want to address this comment? (yes/no/skip/all)
```

**🔄 CRITICAL: Track Comment Outcomes for Reply**

For EVERY comment presented, track the outcome for the final reply:
- **Comment ID**: The `comment_id` from JSON (needed for threaded replies)
- **Comment number**: Sequential (1, 2, 3...)
- **Reviewer**: The reviewer name
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
- Show confirmation: "✅ Task created: [brief description]"
- **DO NOT execute the task - Continue to next comment immediately**

**For "all" response:**

- Create tasks for the current comment AND **ALL remaining comments** automatically
- **CRITICAL**: "all" means process EVERY remaining comment - do NOT skip any comments
- Show summary: "✅ Created tasks for current comment + X remaining comments"
- **Skip to Phase 2 immediately**

**For "no" or "skip" responses:**

- Show: "⏭️ Skipped"
- Continue to next comment immediately

**🚨 REMINDER: Do NOT execute, implement, fix, or process anything during this phase. Only collect decisions
and create tasks.**

### Step 4: PHASE 2 - Process All Approved Tasks (EXECUTION PHASE)

**🚨 IMPORTANT: Only start this phase AFTER all comments have been presented and decisions collected.**

After ALL comments have been reviewed in Phase 1:

1. **Show approved tasks and proceed directly:**

```text
📋 Processing X approved tasks:
1. [Task description]
2. [Task description]
...
```

Proceed directly to execution (no confirmation needed since user already approved each task in Phase 1)

1. **Process all approved tasks:**
   - **🚨 CRITICAL**: Process ALL tasks created during Phase 1
   - **NEVER skip tasks** - if a task was created in Phase 1, it MUST be executed in Phase 2
   - Route to appropriate specialists based on comment content
   - Process multiple tasks in parallel when possible
   - Mark each task as completed after finishing

1. **Post-execution workflow (PHASES 2.5, 3 & 4 - MANDATORY CHECKPOINTS):**

   **PHASE 2.5: Post Review Reply**
   - **STEP 1** (REQUIRED): Generate reply message using this format:

   ```markdown
   ## Review Response

   ### Addressed
   | Reviewer | Title/Comment | File |
   |----------|---------------|------|
   | [reviewer] | [brief summary] | `[file]` |

   ### Not Addressed
   | Reviewer | Title/Comment | File | Reason |
   |----------|---------------|------|--------|
   | [reviewer] | [brief summary] | `[file]` | [reason] |

   ### Skipped
   | Reviewer | Title/Comment | File | Reason |
   |----------|---------------|------|--------|
   | [reviewer] | [brief summary] | `[file]` | [reason] |

   ---
   *Automated response from Review Handler*
   ```

   **Notes on format:**
   - Only include sections that have items (if no skipped items, omit "Skipped" section)
   - Include count in header: "### Addressed (3)"
   - File paths should be in backticks for code formatting

   - **STEP 2** (REQUIRED): Post threaded replies to ALL comments:

   **For ADDRESSED comments** - reply with "Done" and resolve:
   ```bash
   ~/.claude/scripts/reply-to-pr-review.sh "<owner>/<repo>" "<pr_number>" "Done" --comment-id <comment_id> --resolve
   ```

   **For NOT ADDRESSED comments** - reply with reason (NO resolve):
   ```bash
   ~/.claude/scripts/reply-to-pr-review.sh "<owner>/<repo>" "<pr_number>" "<reason>" --comment-id <comment_id>
   ```

   **For SKIPPED comments** - reply with reason (NO resolve):
   ```bash
   ~/.claude/scripts/reply-to-pr-review.sh "<owner>/<repo>" "<pr_number>" "<reason>" --comment-id <comment_id>
   ```

   **Where to get values:**
   - `<owner>/<repo>`: From JSON `metadata.owner` + "/" + `metadata.repo`
   - `<pr_number>`: From JSON `metadata.pr_number`
   - `<comment_id>`: From each comment's `comment_id` field
   - `<reason>`: The tracked reason for not_addressed or skipped outcomes

   **Key difference from CodeRabbit handler:** Human reviewer comments that are not addressed or skipped do NOT get resolved - only replied to. This allows the human reviewer to follow up.

   - **CHECKPOINT**: Replies posted to PR

   **PHASE 3: Testing & Commit**
   - **STEP 1** (REQUIRED): Run all tests
   - **STEP 2** (REQUIRED): If tests pass, MUST ask: "All tests pass. Do you want to commit the changes?
     (yes/no)"
     - If user says "yes": Commit changes with descriptive message
     - If user says "no": Acknowledge and proceed to Phase 4 checkpoint (ask about push anyway)
   - **STEP 3** (REQUIRED): If tests fail:
     - Analyze and fix failures
     - Re-run tests until they pass
   - **CHECKPOINT**: Must reach this point before Phase 4 - commit confirmation MUST be asked

   **PHASE 4: Push to Remote**
   - **STEP 1** (REQUIRED): After successful commit (or commit decline), MUST ask: "Changes committed
     successfully. Do you want to push the changes to remote? (yes/no)"
     - If no commit was made, ask: "Do you want to push any existing commits to remote? (yes/no)"
   - **STEP 2** (REQUIRED): If user says "yes": Push changes to remote
   - **CHECKPOINT**: Push confirmation MUST be asked - this is the final step of the workflow

**🚨 CRITICAL WORKFLOW - STRICT PHASE SEQUENCE:**

This workflow has **5 MANDATORY PHASES** that MUST be executed in order. Each phase has **REQUIRED CHECKPOINTS**
that CANNOT be skipped:

### PHASE 1: Collection Phase

- ONLY collect decisions (yes/no/skip/all) and create tasks - NO execution
- **CHECKPOINT**: ALL comments have been presented and user decisions collected

### PHASE 2: Execution Phase

- ONLY execute tasks after ALL comments reviewed - NO more questions
- Process ALL approved tasks
- **CHECKPOINT**: ALL approved tasks have been completed

### PHASE 2.5: Post Review Reply

- Generate summary reply from tracked outcomes
- Post threaded replies to addressed comments
- **CHECKPOINT**: Replies posted successfully

### PHASE 3: Testing & Commit Phase

- **MANDATORY STEP 1**: Run all tests
- **MANDATORY STEP 2**: If tests pass, MUST ask user: "All tests pass. Do you want to commit the changes?
  (yes/no)"
- **MANDATORY STEP 3**: If user says yes: Commit changes with descriptive message
- **CHECKPOINT**: Tests completed AND commit confirmation asked (even if user declined)

### PHASE 4: Push Phase

- **MANDATORY STEP 1**: After successful commit, MUST ask user: "Changes committed successfully. Do you want to
  push the changes to remote? (yes/no)"
- **MANDATORY STEP 2**: If user says yes: Push changes to remote
- **CHECKPOINT**: Push confirmation asked (even if user declined)

**🚨 ENFORCEMENT RULES:**

- **NEVER skip phases** - all 5 phases are mandatory
- **NEVER skip checkpoints** - each phase must reach its checkpoint before proceeding
- **NEVER skip confirmations** - commit and push confirmations are REQUIRED even if previously discussed
- **NEVER assume** - always ask for confirmation, never assume user wants to commit/push
- **COMPLETE each phase fully** before starting the next phase

**If tests fail**:

- Analyze and fix failures
- Re-run tests until they pass before proceeding to Phase 3's commit confirmation.

Note: Human review comments are treated equally (no priority system like CodeRabbit).
