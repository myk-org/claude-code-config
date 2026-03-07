---
description: Run a prompt via Cursor agent CLI
argument-hint: [--fix] [--model <model>] <prompt>
allowed-tools: Bash(agent:*), Bash(git:*), AskUserQuestion
---

# Cursor Agent Prompt Command

Run a prompt through Cursor's agent CLI, enabling access to models like GPT-5.3, Gemini 3 Pro, Grok, and more.

## Usage

- `/myk-cursor:prompt What are best practices for HTML parsing in Python?`
- `/myk-cursor:prompt --model gemini-3-pro Review this codebase for bugs`
- `/myk-cursor:prompt --model gpt-5.3-codex Review the file src/main.py`
- `/myk-cursor:prompt --fix Review and fix the code quality issues`
- `/myk-cursor:prompt --fix --model gemini-3-pro Fix the failing tests`

## Workflow

### Step 1: Prerequisites Check

Verify the Cursor agent CLI is available:

```bash
agent --version
```

If not found, abort with message: "Cursor agent CLI not found at `agent`. Ensure Cursor is installed and the CLI is on your PATH."

### Step 2: Parse Arguments

Parse leading flags from `$ARGUMENTS` before the prompt text:

- Starting at the beginning of `$ARGUMENTS`, consume only these recognized
  flags until you reach the first token that is not a supported flag:
  - `--fix` -- enable fix mode
  - `--model <model>` -- select a model
- Flags must appear before the prompt text. Once you reach the first
  non-flag token, stop parsing flags and treat the rest as prompt text.
- `--fix` and `--model` may appear in either order before the prompt
  (e.g., `--fix --model gemini-3-pro Fix this`
  or `--model gemini-3-pro --fix Fix this`)
- After the first non-flag token, treat the rest of `$ARGUMENTS` as the
  prompt verbatim, even if it contains strings like `--fix` or `--model`
- If `--fix` appears more than once, abort with:
  "Duplicate --fix flag. Pass --fix at most once."
- If `--model` appears more than once, abort with:
  "Duplicate --model flag. Pass at most one model."
- If `$ARGUMENTS` ends with `--model` and no following word, abort with:
  "Missing model name after --model flag."
- If the word after `--model` starts with `--`, abort with:
  "Invalid model name. Model name cannot start with --."
- Otherwise, if no recognized flags are present, the entire `$ARGUMENTS` is
  the prompt

If no prompt text is provided (empty after parsing), abort with message: "No prompt provided. Usage: `/myk-cursor:prompt [--fix] [--model <model>] <prompt>`"

### Step 2b: Enrich Prompt with Context

Before sending the prompt to Cursor, consider whether the user's prompt would
benefit from additional context that you already have from the current session.

**When to enrich:**

- First verify the current directory is a Git repository
  (`git rev-parse --is-inside-work-tree`). If not, skip all git-based enrichment.
- The prompt references "the changes", "my changes", "the diff", or similar
  → Run `git diff --stat` first. If the diff looks reasonably small
    (roughly under ~200 lines when viewed as a full diff), append the full
    `git diff` output. Otherwise, append only the `--stat` summary and note
    that the full diff was too large to include.
- The prompt references "this file" or "the file" without specifying a path
  → Identify the file from conversation context and include its path
- The prompt says "review", "check", or "analyze" without specifying a target
  → Include the current branch name and recent git context
- The prompt is about the current project but lacks specifics
  → Add the repository name and working directory path

**How to enrich:**

Prepend context to the user's original prompt. Format:

```text
[Context: repository=<repo>, branch=<branch>]
[Additional context if applicable: git diff output, file paths, etc.]

Original prompt: <user's prompt>
```

**When NOT to enrich:**

- The prompt is self-contained with all necessary details
- The prompt is a general knowledge question unrelated to the project
- The prompt already includes file paths, diffs, or specific references

**Keep enrichment minimal** — only add context that directly helps Cursor
understand and respond to the prompt. Do not dump entire files or
excessive diff output.

### Step 2c: Session Continuation

Check the current conversation history for any previous successful `agent`
command in the same mode:

- **Non-fix mode:** A prior `agent --print` call in non-fix mode counts as
  successful if it returned valid JSON with `is_error: false`
  (or omitted `is_error`)
- **Fix mode:** A prior `agent --print` call in fix mode
  (that is, the `--print --trust` variant described in Step 3)
  counts as successful if it returned valid JSON with `is_error: false`
  (or omitted `is_error`)
- **If a previous successful `agent` call exists in the same mode:** Add
  `--continue` to the command. This resumes the last compatible Cursor
  session, preserving context from earlier interactions.
- **If no previous successful call exists in the same mode:** Run without
  `--continue` (fresh session).

Use `--continue` only when the prior successful `agent` call used the same
mode (both non-fix or both `--fix`). Do not use `--continue` when switching
between modes.

### Step 2d: Workspace Safety Check (--fix mode only)

**Skip this step if --fix was NOT passed.**

Before calling Cursor in fix mode, inspect the workspace state first.

```bash
git rev-parse --is-inside-work-tree
git status --short
```

Follow this decision process:

1. If the current directory is not a Git repository, ask the user via
   AskUserQuestion:
   "This directory is not a Git repository. Continue with `--fix` anyway?
   I won't be able to show a git diff or provide an easy rollback point."
2. If the current directory is a Git repository and `git status --short`
   shows any output (modified, staged, or untracked files), ask the user via
   AskUserQuestion:
   "The working tree already has uncommitted changes. Continue with
   `/myk-cursor:prompt --fix` anyway? Cursor may modify the same files,
   and the final diff summary may include pre-existing edits. Recommended:
   create your own checkpoint commit first if you want clean isolation."
3. If the user declines either prompt, abort.
4. Never auto-stage or auto-commit changes as part of `--fix`.
5. If the user confirms despite an already dirty worktree, remember that
   state so Steps 5 and 6 can explicitly warn that the final diff may include
   pre-existing staged or unstaged edits.

### Step 3: Run Prompt

Execute the Cursor agent CLI. Use `--continue` only when Step 2c found a
previous successful `agent` command in the same mode.

**Non-fix mode (default):**

Run with JSON output:

**First call (no prior session):**

```bash
agent --print --output-format json '<escaped_prompt>'
agent --print --output-format json --model <model> '<escaped_prompt>'
```

**Subsequent calls (with --continue):**

```bash
agent --print --continue --output-format json '<escaped_prompt>'
agent --print --continue --output-format json --model <model> '<escaped_prompt>'
```

**Fix mode (--fix):**

Use `--print` with `--trust` so Cursor can modify files AND we capture its response.

**First call (no prior session):**

```bash
agent --print --trust --output-format json '<escaped_prompt>'
agent --print --trust --output-format json --model <model> '<escaped_prompt>'
```

**Subsequent calls (with --continue):**

```bash
agent --print --continue --trust --output-format json '<escaped_prompt>'
agent --print --continue --trust --output-format json --model <model> '<escaped_prompt>'
```

**Additional prompt enrichment for fix mode:**

Append to the user's prompt:

```text
You have full permission to modify, create, and delete files as needed
to fix this. Make all necessary changes directly.
```

`--trust` is always included in fix mode since Cursor needs file write
access.

**Shell safety:** Single-quote the prompt to prevent shell expansion. Replace any single quotes in the prompt with `'\''` before interpolation.

**Timeout:** Set the Bash tool timeout to 300000ms (5 minutes) to prevent the command from hanging indefinitely.

If a non-fix command fails, check Step 3b for trust errors before falling
through to Step 4 error handling.

If a fix-mode command exits with a non-zero code, display the raw output as
an error and stop. Do not continue to Steps 4, 5, or 6.

### Step 3b: Handle Trust Errors (non-fix mode only)

**Skip this step if --fix was passed.** Fix mode already includes `--trust`.

If the command exits with a non-zero code and the error output contains trust-related phrases
(e.g., "workspace trust", "not trusted", "trust the workspace"):

1. Ask the user via AskUserQuestion:
   "Cursor needs workspace trust to access project files.
   Re-run with `--trust` flag? This grants full read/write workspace access."
2. If user confirms, re-run the same command with `--trust` added. Include `--continue` when applicable (see Step 2c):

**First call (no prior session):**

```bash
agent --print --trust --output-format json '<escaped_prompt>'
agent --print --trust --output-format json --model <model> '<escaped_prompt>'
```

**Subsequent calls (with --continue):**

```bash
agent --print --continue --trust --output-format json '<escaped_prompt>'
agent --print --continue --trust --output-format json --model <model> '<escaped_prompt>'
```

If user declines, display the original error and abort.

### Step 4: Parse and Display Result

The JSON output has this structure:

```json
{
  "result": "The actual response text...",
  "is_error": false
}
```

In fix mode, still parse and display the `result` field first. Proceed to
Steps 5 and 6 only if the JSON indicates success.

1. Parse the JSON output
2. Check `is_error` — if `true`, display the error from `result` and abort.
   If `is_error` is missing from the JSON, treat it as `false`.
3. If successful, display the `result` field content to the user
4. Include a note about which model was used (if `--model` was specified) or "default model" otherwise

**Error handling:**

- If the Bash tool reports a timeout, report: "Cursor agent timed out. Try a shorter prompt or check Cursor's status with `agent status`."
- If the command exits with a non-zero code, display the raw output as an error.
- If the output is not valid JSON, display the raw output with a note that JSON parsing failed.
- If the JSON is missing the `result` field, display the full JSON response.

### Step 5: Read Diff (--fix mode only)

**Skip this step if --fix was NOT passed, if the fix-mode `agent`
command exited non-zero, or if Step 4 reported an error.**

After Cursor completes successfully in fix mode, inspect what changed.

If the current directory is a Git repository, read the resulting workspace
state:

```bash
git status --short
git diff --stat
git diff
git diff --cached --stat
git diff --cached
```

If either the unstaged diff or staged diff is empty, omit that section from
the report.

If the combined diff output is too large (over ~200 lines), use the
available `--stat` summaries only and note the full diff was too large to
display inline.

If the workspace was already dirty before running `--fix`, explicitly note
that the final diff may include pre-existing staged or unstaged edits in
addition to Cursor's changes.

If the current directory is not a Git repository, report that git diff is
unavailable and summarize Cursor's output instead.

Report to the user:

- Which files were modified/created/deleted
- A summary of the changes
- The unstaged diff and any staged diff (or stat summaries if too large)

### Step 6: Summary (--fix mode only)

**Skip this step if --fix was NOT passed, if the fix-mode `agent`
command exited non-zero, or if Step 4 reported an error.**

Present a clear summary of what Cursor changed:

1. **Files changed** — List each file with what was modified
2. **What was done** — Brief description of the changes in plain language
3. **Impact** — Note any behavioral changes, new dependencies,
   or things the user should verify

If the workspace was already dirty before the run, or the current directory
is not a Git repository, call out that limitation in the summary.

Example format:

```text
Cursor made the following changes:

Files changed (3):
  M src/auth.py — Added input validation to login handler
  M tests/test_auth.py — Added 2 new test cases for validation
  A src/validators.py — New file with email/password validators

Summary: Added input validation to the login handler with email
format and password length checks. Added corresponding tests.

Verify: Run `pytest tests/test_auth.py` to confirm new tests pass.
```
