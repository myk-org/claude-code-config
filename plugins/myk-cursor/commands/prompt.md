---
name: prompt
description: Run a one-shot prompt via Cursor agent CLI
argument-hint: [--model <model>] <prompt>
allowed-tools: Bash(agent:*), AskUserQuestion
---

# Cursor Agent Prompt Command

Run a one-shot prompt through Cursor's agent CLI, enabling access to models like GPT-5.3, Gemini 3 Pro, Grok, and more.

## Usage

- `/myk-cursor:prompt What are best practices for HTML parsing in Python?`
- `/myk-cursor:prompt --model gemini-3-pro Review this codebase for bugs`
- `/myk-cursor:prompt --model gpt-5.3-codex Review the file src/main.py`

## Workflow

### Step 1: Prerequisites Check

Verify the Cursor agent CLI is available:

```bash
agent --version
```

If not found, abort with message: "Cursor agent CLI not found at `agent`. Ensure Cursor is installed and the CLI is on your PATH."

### Step 2: Parse Arguments

Parse `$ARGUMENTS` to extract optional model flag and the prompt:

- If `$ARGUMENTS` starts with `--model` followed by a space, extract the model name (second word) and use the remainder as the prompt
- If `$ARGUMENTS` is exactly `--model` with no following word, abort with: "Missing model name after --model flag."
- If the word after `--model` starts with `--`, abort with: "Invalid model name. Model name cannot start with --."
- Otherwise, the entire `$ARGUMENTS` is the prompt

If no prompt text is provided (empty after parsing), abort with message: "No prompt provided. Usage: `/myk-cursor:prompt [--model <model>] <prompt>`"

### Step 2b: Enrich Prompt with Context

Before sending the prompt to Cursor, consider whether the user's prompt would
benefit from additional context that you already have from the current session.

**When to enrich:**

- First verify the current directory is a Git repository
  (`git rev-parse --is-inside-work-tree`). If not, skip all git-based enrichment.
- The prompt references "the changes", "my changes", "the diff", or similar
  → Run `git diff | wc -l` to count actual diff lines. If under ~200 lines, append the full
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

### Step 3: Run Prompt

Execute the Cursor agent CLI with JSON output:

**With model specified:**

```bash
agent --print --output-format json --model <model> '<escaped_prompt>'
```

**Without model (uses Cursor default):**

```bash
agent --print --output-format json '<escaped_prompt>'
```

**Shell safety:** Single-quote the prompt to prevent shell expansion. Replace any single quotes in the prompt with `'\''` before interpolation.

**Timeout:** Set the Bash tool timeout to 300000ms (5 minutes) to prevent the command from hanging indefinitely.

If the command fails, check Step 3b for trust errors before falling through to Step 4 error handling.

### Step 3b: Handle Trust Errors

If the command exits with a non-zero code and the error output contains trust-related phrases
(e.g., "workspace trust", "not trusted", "trust the workspace"):

1. Ask the user via AskUserQuestion:
   "Cursor needs workspace trust to access project files.
   Re-run with `--trust` flag? This grants full read/write workspace access."
2. If user confirms, re-run the same command with `--trust` added:

**With model specified:**

```bash
agent --print --trust --output-format json --model <model> '<escaped_prompt>'
```

**Without model:**

```bash
agent --print --trust --output-format json '<escaped_prompt>'
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
