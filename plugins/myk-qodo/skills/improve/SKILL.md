---
name: improve
description: Suggest code improvements for local changes or a pull request
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

## 2. Diff Mode Selection (REQUIRED for local improve)

If NO PR number/URL was provided AND `--base` was NOT provided:

**YOU MUST use AskUserQuestion tool NOW** to ask:

- Question: "What changes would you like to improve?"
- Options:
  1. "All uncommitted changes (git diff HEAD)"
  2. "Compare against main branch"
  3. "Compare against a specific branch"

If user selects "Compare against a specific branch", follow up with another AskUserQuestion asking "Which branch?" with free text input.

DO NOT PROCEED until user selects a mode.

---

## Qodo Improve

Suggest actionable code improvements. Works with local changes or pull requests.

### Usage

```bash
/myk-qodo:improve                             # Improve local uncommitted changes
/myk-qodo:improve --base main                 # Improve changes compared to main
/myk-qodo:improve 123                         # Suggest improvements for PR #123
/myk-qodo:improve https://github.com/.../42   # Suggest improvements for PR by URL
```

### Workflow

#### Step 1: Execute Improve

Parse `$ARGUMENTS` to detect mode:

- If contains PR number or URL -> **PR mode**
- Otherwise -> **Local mode**

#### Step 2: Local Mode

1. Get diff: `git diff HEAD` (or `--base <branch>`)
2. Analyze and suggest:
   - Code simplifications
   - Better patterns or idioms
   - Performance optimizations
   - Readability improvements
   - Error handling enhancements

#### Step 3: PR Mode

1. Resolve PR URL from number if needed
2. Run pr-agent improve:

   ```bash
   python -m pr_agent.cli --pr_url=<url> /improve --config.model=<selected_model>
   ```

   Or analyze diff directly if pr-agent unavailable.

3. Present improvement suggestions

4. **Ask user**: "Do you want to apply any of these improvements?"
   - User can select which improvements to apply
   - Apply selected changes to local files

### Arguments

- `<PR_NUMBER>`: PR number (e.g., `123`)
- `<PR_URL>`: Full PR URL
- `--base <branch>`: Branch to compare against (local mode)
- `--model <name>`: AI model to use (run `qodo models` to see available options)

### Examples

```bash
# Local
/myk-qodo:improve
/myk-qodo:improve --base origin/main

# PR
/myk-qodo:improve 42
/myk-qodo:improve https://github.com/myk-org/repo/pull/42

# With model selection
/myk-qodo:improve --model claude-4-opus
/myk-qodo:improve 42 --model gpt-4
```
