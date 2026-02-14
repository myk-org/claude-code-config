---
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

### Step 3: Run Prompt

Execute the Cursor agent CLI with JSON output:

**With model specified:**

```bash
agent --print --trust --output-format json --model <model> '<escaped_prompt>'
```

**Without model (uses Cursor default):**

```bash
agent --print --trust --output-format json '<escaped_prompt>'
```

**Shell safety:** Single-quote the prompt to prevent shell expansion. Replace any single quotes in the prompt with `'\''` before interpolation.

**Timeout:** Set the Bash tool timeout to 300000ms (5 minutes) to prevent the command from hanging indefinitely.

**Warning:** The `--trust` flag grants Cursor full read/write access to the current workspace without a confirmation prompt.
This is required for file-aware prompts to work.

### Step 4: Parse and Display Result

The JSON output has this structure:

```json
{
  "result": "The actual response text...",
  "is_error": false
}
```

1. Parse the JSON output
2. Check `is_error` — if `true`, display the error from `result` and abort
3. If successful, display the `result` field content to the user
4. Include a note about which model was used (if `--model` was specified) or "default model" otherwise

**Error handling:**

- If the command exits with code 124, report: "Cursor agent timed out. Try a shorter prompt or check Cursor's status with \`agent status\`."
- If the command exits with a non-zero code, display the raw output as an error.
- If the output is not valid JSON, display the raw output with a note that JSON parsing failed.
- If the JSON is missing the `result` field, display the full JSON response.
