---
description: Suggest code improvements for changes or pull request
argument-hint: [PR_NUMBER|PR_URL] [--base <branch>] [--model <name>]
allowed-tools: Bash(python:*), Bash(git:*), Bash(gh:*), Bash(qodo:*), AskUserQuestion
---

# Improve Command Flow

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

### Step 2b: Diff Source Selection (REQUIRED for local)

Check `$ARGUMENTS` for `--base`:

- If found -> use specified branch
- If NOT found -> **call AskUserQuestion**:
  - Question: "What changes would you like to improve?"
  - Options:
    - "All uncommitted changes"
    - "Compare against main branch"
    - "Compare against specific branch"

If "Compare against specific branch" is selected:

- Ask: "Which branch would you like to compare against?"
- Wait for user to type the branch name
- Use the provided branch name

## Step 3: Generate Improvements

Run improvement analysis using selected model.

- Analyze the diff
- Suggest: simplifications, better patterns, performance, readability

## Step 4: Apply Improvements (REQUIRED)

Present improvement suggestions to user.

**call AskUserQuestion**:

- Question: "Do you want to apply any of these improvements?"
- Options:
  - "Apply all improvements"
  - "Select which to apply"
  - "Skip"

### If "Apply all" selected

1. Delegate to appropriate specialist agents
2. Apply all suggested changes
3. Show summary of changes made

### If "Select which" selected

1. **call AskUserQuestion** with numbered list
2. Let user select which improvements
3. Apply only selected changes
4. Show summary

### If "Skip" selected

1. No changes applied
2. Display confirmation message
3. Proceed to Step 5

## Step 5: Complete

Provide a summary including:

- Number of improvements suggested
- Number of improvements applied
- Files modified
- Brief description of changes made
