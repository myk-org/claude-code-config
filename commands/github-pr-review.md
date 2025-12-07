---
skipConfirmation: true
---

# GitHub PR Review Command

**Description:** Reviews a GitHub PR and posts inline review comments on selected findings.

---

## 🚨 CRITICAL: SESSION ISOLATION & FLOW ENFORCEMENT

**THIS PROMPT DEFINES A STRICT, SELF-CONTAINED WORKFLOW THAT MUST BE FOLLOWED EXACTLY:**

1. **IGNORE ALL PREVIOUS CONTEXT**: Previous conversations, tasks, or commands in this session are IRRELEVANT
2. **START FRESH**: This prompt creates a NEW workflow that starts from Step 1 and follows the exact sequence below
3. **NO ASSUMPTIONS**: Do NOT assume any steps have been completed - follow the workflow from the beginning
4. **MANDATORY CHECKPOINTS**: Each phase MUST complete fully before proceeding to the next phase
5. **REQUIRED CONFIRMATIONS**: All user confirmations MUST be asked - NEVER skip them

**If this prompt is called multiple times in a session, treat EACH invocation as a completely independent workflow.**

---

## Usage

- `/github-pr-review` - Review PR from current branch (auto-detect)
- `/github-pr-review 123` - Review PR #123 in current repo
- `/github-pr-review https://github.com/owner/repo/pull/123` - Review from URL

---

## Instructions

### Script Paths

```bash
GET_DIFF_SCRIPT=~/.claude/commands/scripts/github-pr-review/get-pr-diff.sh
POST_COMMENT_SCRIPT=~/.claude/commands/scripts/github-pr-review/post-pr-inline-comment.sh
GET_CLAUDE_MD_SCRIPT=~/.claude/commands/scripts/github-pr-review/get-claude-md.sh
```

### Step 1: Get PR Diff and Metadata

**Run the diff script with the provided arguments:**

```bash
# Pass arguments directly - the script handles URL, PR number, or auto-detection
$GET_DIFF_SCRIPT $ARGUMENTS
```

If no arguments provided, the script will auto-detect from current git context.

**The script returns JSON with:**
- `metadata`: Contains `owner`, `repo`, `pr_number`, `head_sha`
- `diff`: Full unified diff of the PR
- `files`: Array of changed files

**Store these values for later steps:**
- `owner_repo` = metadata.owner + "/" + metadata.repo
- `pr_number` = metadata.pr_number
- `head_sha` = metadata.head_sha (required for posting comments)

**CHECKPOINT**: PR diff retrieved successfully. **On failure:** Show script error and abort.

### Step 2: Read Project CLAUDE.md Files

**Run the script to fetch CLAUDE.md (uses same args as Step 1):**

```bash
CLAUDE_CONTENT=$($GET_CLAUDE_MD_SCRIPT $ARGUMENTS)
```

The script checks local files first, then upstream GitHub. Returns empty if not found.

**Use `$CLAUDE_CONTENT` in Step 3 as review context (may be empty).**

**CHECKPOINT**: CLAUDE.md search complete. Proceed to Step 3.

### Step 3: PHASE 1 - Perform Code Review (ANALYSIS ONLY)

**Analyze the PR diff applying project rules from CLAUDE.md.**

Review the diff for:
1. Code quality and best practices
2. Potential bugs or logic errors
3. Security vulnerabilities (SQL injection, XSS, hardcoded credentials, etc.)
4. Performance issues
5. Missing error handling
6. Code that violates CLAUDE.md rules (if any were found)
7. Resource leaks or improper cleanup
8. Race conditions or concurrency issues
9. Type safety issues (missing type hints, incorrect types, mypy/typing errors)

**For each issue found, document in this format:**

```
---FINDING---
FILE: <exact file path>
LINE: <line number in the new version of the file>
SEVERITY: <CRITICAL|WARNING|SUGGESTION>
TITLE: <brief title, max 50 chars>
DESCRIPTION: <detailed description of the issue and how to fix it>
AI_PROMPT: <specific actionable instruction for AI agents to fix this issue>
SUGGESTION: <exact replacement code, or "none" if no simple fix>
---END---
```

**Rules:**
1. LINE must be the line number in the NEW version of the file (right side of diff)
2. Only include findings for lines that are part of the diff (added or modified lines)
3. Include specific code suggestions when applicable
4. AI_PROMPT must provide precise, actionable instructions
5. SUGGESTION should contain exact replacement code only when a simple fix is possible
6. Prioritize critical issues and security vulnerabilities over style suggestions
7. Be specific about what needs to change and why

**Parse all findings from your analysis and store:**
- `file`: File path
- `line`: Line number (in new version)
- `severity`: CRITICAL, WARNING, or SUGGESTION
- `title`: Brief title
- `description`: Detailed description
- `ai_prompt`: Specific actionable fix instructions for AI agents
- `suggestion`: Exact replacement code (or null/empty if not applicable)

**CHECKPOINT**: All findings documented and parsed. **On failure:** Abort workflow.

### Step 4: PHASE 2 - Present Findings to User (SELECTION PHASE)

## ⛔ STOP - MANDATORY USER INTERACTION ⛔

**YOU MUST STOP HERE AND WAIT FOR USER INPUT.**

Do NOT proceed to Step 5 or Step 6 until the user has responded.
Do NOT post any comments without user selection.

---

**🚨 CRITICAL: This is the SELECTION phase. Do NOT post ANY comments yet. Only present and collect decisions.**

**If no findings were found:**
```text
✅ No issues found in PR #<pr_number>

The code-reviewer agent did not identify any critical issues, warnings, or suggestions.
```
Stop here - workflow complete.

**If findings exist, present as a simple numbered list:**

```text
📋 Found X issues in PR #<pr_number> (<owner>/<repo>):

CRITICAL Issues:
1. [CRITICAL] src/main.py:42 - SQL injection vulnerability
2. [CRITICAL] src/auth.py:15 - Hardcoded credentials

WARNINGS:
3. [WARNING] src/utils.py:88 - Missing error handling
4. [WARNING] src/api.py:120 - Unchecked null pointer

SUGGESTIONS:
5. [SUGGESTION] src/handlers.py:200 - Consider using async
6. [SUGGESTION] src/db.py:55 - Could cache this query

Which findings should be posted as PR comments?
Options:
- 'all' = Post all findings
- 'none' = Skip posting (just review)
- Specific numbers = Post only those (e.g., "1 4 3" or "1,4,10,3")

Your choice:
```

**MANDATORY**: Wait for user response before proceeding.

---

## ⛔ DO NOT PROCEED WITHOUT USER RESPONSE ⛔

**You MUST wait for user to type their selection before continuing.**
**This is NOT optional. The workflow STOPS here until user responds.**

**CHECKPOINT**: User has made a selection. **On failure:** Re-prompt user for valid input.

### Step 5: Parse User Selection

**User input options:**

**"all" or "ALL":**
- Select ALL findings for posting
- Proceed to Step 6

**"none" or "NONE":**
- Skip posting phase entirely
- Jump to Step 7 (summary) with "no comments posted"

**Specific numbers (e.g., "1 4 10 3" or "1,4,10,3"):**
- Parse numbers (split by spaces or commas)
- Validate each number exists in findings list
- Select only those findings
- If any invalid numbers, show error and ask again
- Proceed to Step 6

**Invalid input:**
- Show error: "Invalid input. Please enter 'all', 'none', or specific numbers like '1 3 5'"
- Ask again

**CHECKPOINT**: Valid selection parsed. **On failure:** Re-prompt user for valid input.

### Step 6: PHASE 3 - Post Inline Comments (EXECUTION PHASE)

**🚨 CRITICAL: Only proceed if user selected findings in Step 5.**

**Post all selected findings as a single review (like CodeRabbit):**

1. Build a JSON array of comments
2. Write to temp file
3. Call the script with the file path

**Comment format template for each finding:**

```
### [SEVERITY] Title

Description of the issue.

---

<details>
<summary>📝 Committable suggestion</summary>

‼️ **IMPORTANT:** Carefully review the code before committing.

```suggestion
<replacement code here>
```

</details>

<details>
<summary>🤖 Prompt for AI Agents</summary>

<AI prompt instructions here>

</details>
```

**Rules for building comment bodies:**
- Only include "Committable suggestion" section if suggestion is NOT "none"
- Always include "Prompt for AI Agents" section
- Escape quotes and special characters for JSON

**Step-by-step execution:**

**STEP 1**: Build JSON array with this structure:
```json
[
  {
    "path": "src/main.py",
    "line": 42,
    "body": "### [CRITICAL] SQL Injection Vulnerability\n\nDescription..."
  },
  {
    "path": "src/utils.py",
    "line": 15,
    "body": "### [WARNING] Missing error handling\n\nDescription..."
  }
]
```

**STEP 2**: Write the JSON to a temp file using the Write tool:
- File path: `/tmp/claude/pr-review-comments.json`
- Content: The JSON array you built in STEP 1

**STEP 3**: Call the script with the temp file path:
```bash
$POST_COMMENT_SCRIPT "$owner_repo" "$pr_number" "$head_sha" /tmp/claude/pr-review-comments.json
```

**🚨 CRITICAL**:
- Use the Write tool to create the temp file - do NOT use bash heredoc or echo
- Do NOT use stdin (`-`) - always use a file path
- The Write tool reliably creates the file without interference

**Show progress:**
```text
📤 Posting review with X comment(s) to PR #<pr_number>
✅ Review posted successfully

Comments posted:
  - src/main.py:42 - SQL injection vulnerability
  - src/utils.py:15 - Missing error handling
```

**Or if error:**
```text
❌ Failed to post review: [error message]
```

**Track results:**
- Store which findings were posted
- Note any failures

**CHECKPOINT**: Review with all selected comments posted. **On failure:** Show errors in summary.

### Step 7: Summary

**Show final summary:**

```text
## ✅ PR Review Complete

**PR**: #<pr_number> (<owner>/<repo>)

**Review Results:**
- Total findings: X
- Comments posted: Y
- Skipped: Z
- Failed: W (if any)

**Posted comments:**
✅ [CRITICAL] src/main.py:42 - SQL injection vulnerability
✅ [WARNING] src/utils.py:88 - Missing error handling

**Skipped:**
⏭️ [SUGGESTION] src/api.py:200 - Consider using async
⏭️ [SUGGESTION] src/db.py:55 - Could cache this query

**Failed (if any):**
❌ [WARNING] src/handlers.py:120 - Failed: [error message]
```

**Workflow complete.**

---

## 🚨 ENFORCEMENT RULES

**NEVER skip phases** - all phases are mandatory:
1. Phase 1: Code Review (direct analysis)
2. Phase 2: Present Findings and Get User Selection
3. Phase 3: Post Selected Comments (only if user selected findings)
4. Summary

**NEVER post comments without user approval** - user MUST explicitly select which findings to post

**NEVER modify files** - this is a review-only command (no code changes, no commits)

**ALWAYS wait for user selection** before posting any comments

**ALWAYS use the exact FINDING FORMAT** specified in Step 3 for documenting issues

**ALWAYS validate line numbers** - only comment on lines that are part of the diff (new or modified lines)

**ALWAYS include head_sha** when posting comments - required for GitHub API

---

## Error Handling

**If PR parsing fails:**
- Show error message
- Ask user to verify PR exists and is accessible
- Abort workflow

**If get-pr-diff.sh fails:**
- Show error message
- Ask user to verify PR number and permissions
- Abort workflow

**If code review analysis fails:**
- Show error message
- Ask user if they want to retry
- Do not proceed to posting phase

**If posting individual comment fails:**
- Log the failure
- Continue posting other comments
- Show all failures in summary

**If all comment posts fail:**
- Show error summary
- Suggest checking GitHub permissions
- Suggest checking head_sha validity
