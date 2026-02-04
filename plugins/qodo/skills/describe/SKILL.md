---
name: describe
description: Generate a description for code changes - local or pull request
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

## 2. Diff Mode Selection (REQUIRED for local describe)

If NO PR number/URL was provided AND `--base` was NOT provided:

**YOU MUST use AskUserQuestion tool NOW** to ask:

- Question: "What changes would you like to describe?"
- Options:
  1. "All uncommitted changes (git diff HEAD)"
  2. "Compare against main branch"
  3. "Compare against a specific branch"

If user selects "Compare against a specific branch", follow up with another AskUserQuestion asking "Which branch?" with free text input.

DO NOT PROCEED until user selects a mode.

---

## Qodo Describe

Generate a comprehensive description of code changes. Works with local changes or pull requests.

### Usage

```bash
/qodo:describe                            # Describe local uncommitted changes
/qodo:describe --base main                # Describe changes compared to main
/qodo:describe 123                        # Generate description for PR #123
/qodo:describe https://github.com/.../42  # Generate description for PR by URL
```

### Workflow

#### Step 1: Execute Describe

Parse `$ARGUMENTS` to detect mode:

- If contains PR number or URL -> **PR mode**
- Otherwise -> **Local mode**

#### Step 2: Local Mode

1. Get diff: `git diff HEAD` (or `--base <branch>`)
2. Analyze changes and generate:
   - Summary of what changed
   - Type of change (feature, fix, refactor, etc.)
   - Key files modified
   - Impact description

#### Step 3: PR Mode

1. Resolve PR URL from number if needed
2. Run pr-agent describe:

   ```bash
   python -m pr_agent.cli --pr_url=<url> /describe --config.model=<selected_model>
   ```

   Or analyze diff directly if pr-agent unavailable.

3. Present generated description

4. **Ask user**: "Do you want to update the PR description with this?"
   - If YES: Update PR via `gh pr edit <number> --body "..."`
   - If NO: Just show the description

### Arguments

- `<PR_NUMBER>`: PR number (e.g., `123`)
- `<PR_URL>`: Full PR URL
- `--base <branch>`: Branch to compare against (local mode)
- `--model <name>`: AI model to use (run `qodo models` to see available options)

### Examples

```bash
# Local
/qodo:describe
/qodo:describe --base origin/main

# PR
/qodo:describe 42
/qodo:describe https://github.com/myk-org/repo/pull/42

# With model selection
/qodo:describe --model gpt-4
/qodo:describe 42 --model claude-4-opus
```
