---
description: Generate description for code changes or pull request
argument-hint: [PR_NUMBER|PR_URL] [--base <branch>] [--model <name>]
allowed-tools: Bash(qodo *), AskUserQuestion
---

# Describe Command Flow

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

  4. **Use the selected model** for the rest of the command

**Note:** Do NOT use AskUserQuestion for model selection. Just display the list and wait for user input.

## Step 2: Mode Detection

Check `$ARGUMENTS` for PR number or URL:

- If PR found -> use PR mode, skip to Step 3
- If NO PR -> continue to Step 2b

### Step 2b: Diff Source Selection (REQUIRED for local)

Check `$ARGUMENTS` for `--base`:

- If found -> use specified branch
- If NOT found -> **call AskUserQuestion**:
  - Question: "What changes would you like to describe?"
  - Options:
    - "All uncommitted changes"
    - "Compare against main branch"
    - "Compare against specific branch"

## Step 3: Generate Description

Run description generation using selected model.

- Analyze the diff
- Generate: summary, type of change, key files, impact

## Step 4: Present and Apply (PR mode)

Present generated description to user.

For PR mode, **call AskUserQuestion**:

- Question: "Do you want to update the PR description with this?"
- Options:
  - "Update PR description" -> Apply via `gh pr edit`
  - "Skip" -> Just show, don't apply

## Step 5: Complete

Summary of actions taken.
