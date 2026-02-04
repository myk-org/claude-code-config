---
name: ask
description: Ask questions about code changes - local or pull request
---

# STOP - MANDATORY INPUTS REQUIRED

**Before doing ANYTHING else, you MUST ask the user these questions if not provided in arguments:**

## 1. Model Selection (REQUIRED)

If `--model` was NOT provided in `$ARGUMENTS`:

1. Run `qodo models` to get the list of available models
2. Display a numbered list of models to the user
3. Ask: "Which AI model would you like to use? Enter a number:"
4. Wait for user to type a number
5. Do NOT use AskUserQuestion for model selection

DO NOT PROCEED until user selects a model.

## 2. Diff Mode Selection (REQUIRED for local ask)

If NO PR number/URL was provided AND `--base` was NOT provided:

**YOU MUST use AskUserQuestion tool NOW** to ask:

- Question: "What changes would you like to ask about?"
- Options:
  1. "All uncommitted changes (git diff HEAD)"
  2. "Compare against main branch"
  3. "Compare against a specific branch"

If user selects "Compare against a specific branch", follow up with another AskUserQuestion asking "Which branch?" with free text input.

DO NOT PROCEED until user selects a mode.

---

## Qodo Ask

Ask questions about code changes and get AI-powered answers. Works with local changes or pull requests.

### Usage

```bash
/qodo:ask "What does this change do?"                    # Ask about local changes
/qodo:ask "What does this change do?" --base main        # Compare against main
/qodo:ask "Are there security issues?" 123               # Ask about PR #123
/qodo:ask "Explain the auth flow" https://github.com/... # Ask about PR by URL
```

### Workflow

#### Step 1: Execute Ask

Parse `$ARGUMENTS` to detect mode:

- If contains PR number or URL -> **PR mode**
- Otherwise -> **Local mode**

#### Step 2: Local Mode

1. Get diff: `git diff HEAD` (or `--base <branch>`)
2. Analyze the question in context of the diff
3. Provide detailed answer based on the changes

#### Step 3: PR Mode

1. Resolve PR URL from number if needed
2. Get PR context: diff, description, comments
3. Run pr-agent ask:

   ```bash
   python -m pr_agent.cli --pr_url=<url> /ask "<question>" --config.model=<selected_model>
   ```

   Or analyze directly if pr-agent unavailable.

4. Provide detailed answer

### Arguments

- `"<question>"`: The question to ask (required)
- `<PR_NUMBER>`: PR number (e.g., `123`)
- `<PR_URL>`: Full PR URL
- `--base <branch>`: Branch to compare against (local mode)
- `--model <name>`: AI model to use (run `qodo models` to see available options)

### Examples

```bash
# Local
/qodo:ask "What are the main changes?"
/qodo:ask "Are there any security concerns?" --base main
/qodo:ask "What files were modified?"

# PR
/qodo:ask "What does this PR do?" 42
/qodo:ask "Are there untested code paths?" 42
/qodo:ask "Explain the caching strategy" https://github.com/myk-org/repo/pull/42

# With model selection
/qodo:ask "What are the main changes?" --model gpt-4
/qodo:ask "Explain this PR" 42 --model claude-4-opus
```
