---
description: Review code changes for bugs, security issues, and quality
argument-hint: [PR_NUMBER|PR_URL] [--base <branch>] [--staged] [--focus <area>] [--model <name>]
allowed-tools: Bash(qodo:*), AskUserQuestion
---

# Review Command Flow

Execute these steps in order. Use AskUserQuestion for any missing inputs.

## Step 1: Model Selection (REQUIRED)

Check `$ARGUMENTS` for `--model`:

- If found -> use specified model
- If NOT found:

  1. **Run:** `qodo models`

  2. **Display the output to the user** with numbered options, like:

     ```text
     Available models:
     1. claude-4.5-sonnet
     2. claude-4.5-haiku

     Enter the number of your choice:
     ```

  3. **Wait for user to type a number**

     Note: Use conversational input - display the prompt and the user's next message will be their selection. Do not use AskUserQuestion for model selection.

  4. **Use the selected model** for the rest of the command

## Step 2: Mode Detection

Check `$ARGUMENTS` for PR number or URL:

- If PR found -> use PR mode, skip to Step 3
- If NO PR -> continue to Step 2b

### Step 2b: Diff Mode Selection (REQUIRED for local)

Check `$ARGUMENTS` for `--base` or `--staged`:

- If found -> use specified mode
- If NOT found -> **call AskUserQuestion**:
  - Question: "What changes would you like to review?"
  - Options:
    1. "All uncommitted changes (git diff HEAD)"
    2. "Compare against main branch"
    3. "Only staged changes"
    4. "Compare against specific branch"

  If user selects "Compare against specific branch", follow up with another AskUserQuestion asking "Which branch?" with free text input.

## Step 3: Execute Review

Run the review using selected model and diff mode.

- Get the diff based on mode selection
- Analyze for: security issues, bugs, code quality, performance
- Present findings to user with severity levels

## Step 4: Address Findings (REQUIRED)

After presenting findings, **call AskUserQuestion**:

- Question: "Do you want to address these findings?"
- Options:
  - "Address all findings" -> Fix all issues automatically
  - "Select which to address" -> Show numbered list, let user pick
  - "Skip" -> No changes, end here

### If "Address all" selected

1. Delegate fixes to appropriate specialist agents
2. Apply all fixes
3. Re-run review to verify fixes
4. Return to Step 4 if new issues found

### If "Select which" selected

1. **call AskUserQuestion** with numbered list of findings
2. Let user select (e.g., "1,3,5" or "all except 2")
3. Fix only selected issues
4. Re-run review to verify
5. Return to Step 4 if new issues found

### If "Skip" selected

- Continue to Step 5 (or end if local mode)

## Step 5: Post to PR (PR mode only)

For PR mode, **call AskUserQuestion**:

- Question: "Do you want to post findings as PR review comments?"
- Options:
  - "Post as review comments" -> Add inline comments to PR
  - "Skip posting" -> End without posting

## Step 6: Complete

Summary of actions taken and review complete.
