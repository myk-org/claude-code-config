---
skipConfirmation: true
---

# GitHub PR Review Command

**Description:** Reviews a GitHub PR and posts inline review comments on selected findings using a multi-agent architecture.

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

## Architecture Overview

```text
PHASE 1a: Data Fetching (bash-expert agent)
  → Run scripts to fetch PR diff and CLAUDE.md
  → Return JSON with metadata, diff, files, claude_md_content

PHASE 1b: Code Analysis (code-reviewer agent)
  → Receive diff + CLAUDE.md from Phase 1a
  → Perform full code review analysis
  → Return JSON with findings array

PHASE 2: User Selection (MAIN CONVERSATION - cannot delegate)
  → Present findings list to user
  → Wait for user selection (all/none/specific numbers)
  → Parse selection

PHASE 3: Post Comments (bash-expert agent)
  → Receive selected findings + metadata
  → Write JSON to /tmp/claude/pr-review-comments.json
  → Run post-pr-inline-comment.sh
  → Return success/failure for each

PHASE 4: Summary (MAIN CONVERSATION)
  → Display final summary
```

---

## Task Tracking

This workflow uses Claude Code's task system for progress tracking. Tasks are created at each phase with dependencies to ensure proper ordering.

**Task visibility:** Use `/tasks` to see all tasks or `Ctrl+T` to toggle task panel.

**Task phases:**

- Phase 1a: Data fetching (bash-expert)
- Phase 1b: Code analysis (blockedBy 1a)
- Phase 2: User selection (main conversation, no task)
- Phase 3: Post comments (blockedBy user selection)
- Phase 4: Summary (main conversation, no task)

---

## Instructions

### PHASE 1a: Data Fetching (DELEGATE TO bash-expert)

**Create Phase 1a task:**

```text
TaskCreate: "Fetch PR data and diff"
  - activeForm: "Fetching PR data"
  - Status: in_progress
```

**Route to `bash-expert` agent with this prompt:**

```markdown
# PR Data Fetching Task

Execute these scripts to fetch PR information and project CLAUDE.md files.

### Script Paths

```bash
GET_DIFF_SCRIPT=~/.claude/commands/scripts/github-pr-review/get-pr-diff.sh
GET_CLAUDE_MD_SCRIPT=~/.claude/commands/scripts/github-pr-review/get-claude-md.sh
```

### Step 1: Get PR Diff and Metadata

Run the diff script with the provided arguments:

```bash
$GET_DIFF_SCRIPT {ARGUMENTS}
```

Arguments to pass: `{ARGUMENTS}`

If no arguments provided, the script will auto-detect from current git context.

The script returns JSON with:

- `metadata`: Contains `owner`, `repo`, `pr_number`, `head_sha`
- `diff`: Full unified diff of the PR
- `files`: Array of changed files

Store the complete JSON output.

### Step 2: Read Project CLAUDE.md Files

Run the script to fetch CLAUDE.md (uses same args as Step 1):

```bash
CLAUDE_CONTENT=$($GET_CLAUDE_MD_SCRIPT {ARGUMENTS})
```

The script checks local files first, then upstream GitHub. Returns empty if not found.

### Output Format

Return a single JSON object combining both outputs:

```json
{
  "metadata": {
    "owner": "...",
    "repo": "...",
    "pr_number": 123,
    "head_sha": "abc123..."
  },
  "diff": "<full unified diff>",
  "files": ["path/to/file1.py", "path/to/file2.js"],
  "claude_md_content": "<content from CLAUDE.md or empty string>"
}
```

If either script fails, include an "error" field with the error message.

**Replace `{ARGUMENTS}` with:** `$ARGUMENTS` (the actual arguments passed to this command)

**Store the agent's JSON response for Phase 1b.**

**If agent returns malformed JSON:**

- Show error: "Failed to parse agent response. Expected valid JSON."
- Display first 500 characters of raw agent output
- Abort workflow

**CHECKPOINT**: PR data retrieved successfully.

- **On failure:** Show error and abort.
- **On empty diff (no files changed):** Show "PR has no changes to review" and complete workflow.

---

### PHASE 1b: Code Analysis (DELEGATE TO code-reviewer)

**Create Phase 1b task:**

```text
TaskCreate: "Analyze code for issues"
  - activeForm: "Analyzing code"
  - blockedBy: [Phase 1a task]
  - Status: in_progress
```

**Route to `code-reviewer` agent with this prompt:**

```markdown
ultrathink

# PR Code Review Analysis Task

Perform a comprehensive code review of this pull request.

### PR Information

**Metadata:**

```json
{METADATA}
```

**Changed Files:**

```text
{FILES}
```

**Project CLAUDE.md Rules:**

```text
{CLAUDE_MD_CONTENT}
```

**Full PR Diff:**

```diff
{DIFF}
```

### Review Criteria

#### CRITICAL Priority

- Security vulnerabilities (injection attacks, auth bypass, data exposure)
- Hardcoded secrets, credentials, API keys, tokens
- Logic errors that cause incorrect behavior or data corruption
- Breaking changes to public APIs without proper handling
- **ANY violation of project CLAUDE.md rules is CRITICAL severity**

#### WARNING Priority

- Missing error handling or input validation
- Resource leaks (files, connections, handles not closed)
- Race conditions or concurrency issues
- Unhandled edge cases or boundary conditions
- Type mismatches or unsafe type operations
- Incorrect exception handling (swallowing errors, wrong types)

#### SUGGESTION Priority

- Duplicate code that should be refactored
- Misleading or unclear variable/function names
- Dead code or unused variables
- Missing documentation for public APIs or complex logic
- Inconsistent naming conventions
- Performance improvements (N+1 queries, unnecessary iterations)
- Overly complex code that could be simplified

### CLAUDE.md Rules Enforcement (STRICT)

- Project-specific rules OVERRIDE general suggestions
- If CLAUDE.md says "never do X" - finding X is CRITICAL
- If CLAUDE.md says "always do Y" - missing Y is CRITICAL
- Enforce all rules defined in the CLAUDE.md content provided above

### Analysis Rules

1. LINE must be the line number in the NEW version of the file (right side of diff)
2. Only include findings for lines that are part of the diff (added or modified lines with `+` prefix)
3. Include specific code suggestions when applicable
4. AI_PROMPT must provide precise, actionable instructions for AI agents to fix the issue
5. SUGGESTION should contain exact replacement code only when a simple fix is possible
6. Prioritize critical issues and security vulnerabilities over style suggestions
7. Be specific about what needs to change and why

### JSON Output Format

Return a JSON object with this structure:

```json
{
  "findings": [
    {
      "id": 1,
      "file": "path/to/file.py",
      "line": 42,
      "severity": "CRITICAL",
      "title": "SQL injection vulnerability",
      "description": "The query concatenates user input directly without parameterization, allowing SQL injection attacks. Use parameterized queries instead.",
      "ai_prompt": "Replace the string concatenation in the SQL query with parameterized query using placeholders. Use the database driver's parameter binding mechanism to safely pass the user_input value.",
      "suggestion": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_input,))"
    },
    {
      "id": 2,
      "file": "path/to/file.py",
      "line": 88,
      "severity": "WARNING",
      "title": "Missing error handling",
      "description": "The file operation does not handle potential IOError exceptions, which could crash the application if the file is locked or permissions are denied.",
      "ai_prompt": "Wrap the file operation in a try-except block to catch IOError and handle it gracefully by logging the error and returning an appropriate error response.",
      "suggestion": "try:\n    with open(filename, 'r') as f:\n        return f.read()\nexcept IOError as e:\n    logger.error(f'Failed to read file: {e}')\n    raise"
    },
    {
      "id": 3,
      "file": "path/to/utils.js",
      "line": 120,
      "severity": "SUGGESTION",
      "title": "Consider using async/await",
      "description": "The Promise chain could be more readable using async/await syntax.",
      "ai_prompt": "Convert the Promise chain to use async/await syntax. Declare the function as async and use await for the fetch call and json parsing.",
      "suggestion": ""
    }
  ],
  "summary": {
    "critical": 1,
    "warning": 1,
    "suggestion": 1,
    "total": 3
  }
}
```

**Rules for findings:**

- Each finding MUST have a unique sequential id
- file: Exact path from the diff
- line: Line number in NEW version (right side of diff)
- severity: One of "CRITICAL", "WARNING", "SUGGESTION"
- title: Brief title (max 50 chars)
- description: Detailed description of the issue and how to fix it
- ai_prompt: Specific actionable instruction for AI agents to fix this issue
- suggestion: Exact replacement code if simple fix exists, otherwise empty string

**If no issues found, return:**

```json
{
  "findings": [],
  "summary": {
    "critical": 0,
    "warning": 0,
    "suggestion": 0,
    "total": 0
  }
}
```

Return ONLY the JSON object, no additional commentary.

**Replace placeholders:**

- `{METADATA}` = metadata object from Phase 1a
- `{FILES}` = files array from Phase 1a (joined with newlines)
- `{CLAUDE_MD_CONTENT}` = claude_md_content from Phase 1a (or "No CLAUDE.md found" if empty)
- `{DIFF}` = diff content from Phase 1a

**Parse the agent's JSON response.**

**If agent returns malformed JSON:**

- Show error: "Failed to parse agent response. Expected valid JSON."
- Display first 500 characters of raw agent output
- Abort workflow

**CHECKPOINT**: Code review analysis complete. **On failure:** Show error and abort.

---

### PHASE 2: User Selection (MAIN CONVERSATION - DO NOT DELEGATE)

### STOP - MANDATORY USER INTERACTION

**YOU MUST STOP HERE AND WAIT FOR USER INPUT.**

Do NOT proceed to Phase 3 until the user has responded.
Do NOT post any comments without user selection.

---

**If findings array is empty:**

```text
✅ No issues found in PR #{pr_number}

The code-reviewer agent did not identify any critical issues, warnings, or suggestions.
```

Stop here - workflow complete.

---

**If findings exist, present findings with full details:**

Display each finding grouped by severity (CRITICAL first, then WARNING, then SUGGESTION):

```text
📋 Found {total} issue(s) in PR #{pr_number} ({owner}/{repo}):

───────────────────────────
[{id}] {severity}
───────────────────────────
FILE: {file}
LINE: {line}
TITLE: {title}
DESCRIPTION: {description}
AI_PROMPT: {ai_prompt}
SUGGESTION: {suggestion or "none"}
───────────────────────────

───────────────────────────
[{id}] {severity}
───────────────────────────
FILE: {file}
LINE: {line}
TITLE: {title}
DESCRIPTION: {description}
AI_PROMPT: {ai_prompt}
SUGGESTION: {suggestion or "none"}
───────────────────────────

... (repeat for each finding)

───────────────────────────
📋 Summary: {critical} CRITICAL, {warning} WARNING, {suggestion} SUGGESTION

Which findings should be posted as PR comments?
Options:
- 'all' = Post all findings
- 'none' = Skip posting (just review)
- Specific numbers = Post only those (e.g., "1 4 3" or "1,4,10,3")

Your choice:
```

**Display rules:**

- Group findings by severity (all CRITICAL, then all WARNING, then all SUGGESTION)
- Show complete details for each finding
- If suggestion field is empty string, display "none"
- Preserve line breaks in description and ai_prompt fields

**MANDATORY**: Wait for user response before proceeding.

---

### DO NOT PROCEED WITHOUT USER RESPONSE

**You MUST wait for user to type their selection before continuing.**
**This is NOT optional. The workflow STOPS here until user responds.**

**CHECKPOINT**: User has made a selection. **On failure:** Re-prompt user for valid input.

---

### Parse User Selection

**User input options:**

**"all" or "ALL":**

- Select ALL findings for posting
- Proceed to Phase 3

**"none" or "NONE":**

- Skip posting phase entirely
- Jump to Phase 4 (summary) with "no comments posted"

**Specific numbers (e.g., "1 4 10 3" or "1,4,10,3"):**

- Parse numbers (split by spaces or commas, trim whitespace)
- Validate each number exists in findings list (1 to total)
- Select only those findings
- If any invalid numbers, show error and ask again:

  ```text
  Invalid selection. Found invalid numbers: {invalid_list}
  Valid range is 1-{total}. Please try again:
  ```

- Proceed to Phase 3

**Invalid input:**

- Show error: "Invalid input. Please enter 'all', 'none', or specific numbers like '1 3 5'"
- Ask again

**Parsing Rules (for specific numbers):**

1. Trim whitespace from input
2. Split by BOTH comma AND space (regex: `/[,\s]+/`)
3. Remove empty strings from result
4. Convert each to integer
5. Deduplicate if user enters same number twice
6. Validate all are in range [1, total]
7. If ANY is invalid, reject entire input and re-prompt

**CHECKPOINT**: Valid selection parsed. **On failure:** Re-prompt user for valid input.

---

### PHASE 3: Post Comments (DELEGATE TO bash-expert)

**Only proceed if user selected findings (not "none").**

**Create Phase 3 task:**

```text
TaskCreate: "Post review comments to PR"
  - activeForm: "Posting comments"
  - Status: in_progress
```

**Route to `bash-expert` agent with this prompt:**

```markdown
# Post PR Review Comments Task

Post inline review comments to GitHub PR using the provided findings.

### Metadata

```json
{
  "owner_repo": "{owner}/{repo}",
  "pr_number": {pr_number},
  "head_sha": "{head_sha}"
}
```

### Selected Findings

```json
{SELECTED_FINDINGS}
```

### Comment Posting Instructions

#### Step 1: Build Comment Bodies

For each finding, build a comment body using this template:

**If finding has non-empty suggestion:**

````markdown
### [{severity}] {title}

{description}

---

<details>
<summary>Committable suggestion</summary>

**IMPORTANT:** Carefully review the code before committing.

```suggestion
{suggestion}
```

</details>

<details>
<summary>Prompt for AI Agents</summary>

{ai_prompt}

</details>
````

**If finding has empty suggestion:**

````markdown
### [{severity}] {title}

{description}

---

<details>
<summary>Prompt for AI Agents</summary>

{ai_prompt}

</details>
````

#### Step 2: Build JSON Array

Create a JSON array with this structure:

```json
[
  {
    "path": "path/to/file.py",
    "line": 42,
    "body": "<comment body from template>"
  },
  {
    "path": "path/to/file.js",
    "line": 88,
    "body": "<comment body from template>"
  }
]
```

**CRITICAL**: Properly escape all special characters for JSON (quotes, newlines, backslashes).

#### Step 3: Write JSON to Temp File

Use the Write tool to create the file:

- Path: `/tmp/claude/pr-review-comments.json`
- Content: The JSON array from Step 2

**IMPORTANT**: Use the Write tool directly (not bash commands like heredoc or echo) to ensure proper JSON escaping.

#### Step 4: Post Comments

Run the post script:

```bash
POST_SCRIPT=~/.claude/commands/scripts/github-pr-review/post-pr-inline-comment.sh
$POST_SCRIPT "{owner_repo}" "{pr_number}" "{head_sha}" /tmp/claude/pr-review-comments.json
```

#### Result Format

Return a JSON object with the results:

```json
{
  "status": "success",
  "posted": [
    {"id": 1, "file": "path/to/file.py", "line": 42, "status": "success"},
    {"id": 2, "file": "path/to/file.js", "line": 88, "status": "success"}
  ],
  "failed": [],
  "review_url": "https://github.com/{owner}/{repo}/pull/{pr_number}"
}
```

**If any comments fail, include them in the "failed" array:**

```json
{
  "status": "partial",
  "posted": [...],
  "failed": [
    {"id": 3, "file": "path/to/file.py", "line": 120, "status": "failed", "error": "Line not part of diff"}
  ],
  "review_url": "..."
}
```

**If all comments fail:**

```json
{
  "status": "failed",
  "posted": [],
  "failed": [...],
  "error": "Full error message from script"
}
```

Show progress while working:

```text
Posting review with {count} comment(s) to PR #{pr_number}
```

Return ONLY the JSON object after completion.

**Replace placeholders:**

- `{owner}`, `{repo}`, `{pr_number}`, `{head_sha}` from metadata
- `{SELECTED_FINDINGS}` = JSON array of selected findings

**Parse the agent's JSON response.**

**If agent returns malformed JSON:**

- Show error: "Failed to parse agent response. Expected valid JSON."
- Display first 500 characters of raw agent output
- Abort workflow

**CHECKPOINT**: Comments posted. **On failure:** Show errors in summary.

---

### PHASE 4: Summary (MAIN CONVERSATION)

**Display final summary based on results:**

```text
## ✅ PR Review Complete

**PR**: #{pr_number} ({owner}/{repo})

**Review Results:**
- Total findings: {total_findings}
- Comments posted: {posted_count}
- Skipped: {skipped_count}
- Failed: {failed_count} (if any)

**Posted comments:**
✅ [CRITICAL] src/main.py:42 - SQL injection vulnerability
✅ [WARNING] src/utils.py:88 - Missing error handling

**Skipped:**
⏭️ [SUGGESTION] src/api.py:200 - Consider using async
⏭️ [SUGGESTION] src/db.py:55 - Could cache this query

**Failed (if any):**
❌ [WARNING] src/handlers.py:120 - Failed: Line not part of diff
```

**Calculate counts:**

- `total_findings` = total from Phase 1b summary
- `posted_count` = length of posted array from Phase 3 (or 0 if user selected "none")
- `skipped_count` = findings NOT selected by user
- `failed_count` = length of failed array from Phase 3

**Workflow complete.**

---

### Final Cleanup

**MANDATORY**: Before completing the workflow, ensure all tasks are properly closed.

1. Run `TaskList` to check for any tasks still in `pending` or `in_progress` status
2. Mark all completed tasks as `completed`
3. Verify all tasks show `completed` status

### Task Tracking Throughout Workflow

Tasks are created and managed automatically:

| Phase | Tasks Created         | Dependencies               |
| ----- | --------------------- | -------------------------- |
| 1a    | 1 (data fetching)     | None                       |
| 1b    | 1 (code analysis)     | blockedBy: Phase 1a        |
| 2     | 0 (user interaction)  | -                          |
| 3     | 1 (post comments)     | blockedBy: user selection  |
| 4     | 0 (summary)           | -                          |

Use `TaskList` to check progress. Use `TaskUpdate` to mark tasks completed.

---

## ENFORCEMENT RULES

**NEVER skip phases** - all phases are mandatory:

1. Phase 1a: Data Fetching (bash-expert agent)
2. Phase 1b: Code Analysis (code-reviewer agent)
3. Phase 2: User Selection (main conversation - CANNOT delegate)
4. Phase 3: Post Comments (bash-expert agent - only if user selected findings)
5. Phase 4: Summary (main conversation)

**NEVER delegate Phase 2** - user interaction must happen in main conversation

**NEVER post comments without user approval** - user MUST explicitly select which findings to post

**NEVER modify files** - this is a review-only command (no code changes, no commits)

**ALWAYS wait for user selection** in Phase 2 before proceeding to Phase 3

**ALWAYS validate agent responses** - ensure JSON is properly formatted before parsing

**ALWAYS use Write tool for temp file** in Phase 3 - never bash heredoc or echo

---

## Error Handling

**If Phase 1a (data fetching) fails:**

- Show error message from bash-expert agent
- Ask user to verify PR exists and is accessible
- Abort workflow

**If Phase 1b (code review) fails:**

- Show error message from code-reviewer agent
- Ask user if they want to retry
- Do not proceed to posting phase

**If Phase 3 (posting) fails partially:**

- Continue workflow
- Show failed comments in Phase 4 summary
- Suggest checking GitHub permissions

**If Phase 3 (posting) fails completely:**

- Show error summary in Phase 4
- Suggest checking GitHub permissions
- Suggest checking head_sha validity

**If user provides invalid selection:**

- Re-prompt with clear error message
- Show valid options again
- Wait for corrected input
