---
description: Ask questions about code changes or pull request
argument-hint: "<question>" [PR_NUMBER|PR_URL] [--base <branch>] [--model <name>]
allowed-tools: Bash(qodo *), AskUserQuestion
---

# Ask Command Flow

## Step 1: Question Check (REQUIRED)

Check `$ARGUMENTS` for a question:

- If found -> use the question
- If NOT found -> **call AskUserQuestion**:
  - Question: "What would you like to know about the code changes?"
  - Free text input

## Step 2: Model Selection (REQUIRED)

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

## Step 3: Mode Detection

Check `$ARGUMENTS` for PR number or URL:

- If PR found -> use PR mode, skip to Step 4
- If NO PR -> continue to Step 3b

### Step 3b: Diff Source Selection (REQUIRED for local)

Check `$ARGUMENTS` for `--base`:

- If found -> use specified branch
- If NOT found -> **call AskUserQuestion**:
  - Question: "What code changes should I analyze to answer your question?"
  - Options:
    1. "All uncommitted changes"
    2. "Compare against main branch"
    3. "Compare against specific branch"

  If user selects "Compare against specific branch", follow up with another AskUserQuestion asking "Which branch?" with free text input.

## Step 4: Answer Question

Analyze the code changes and answer the user's question.

## Step 5: Follow-up

**call AskUserQuestion**:

- Question: "Do you have any follow-up questions?"
- Options:
  - "Ask another question" -> Return to Step 1
  - "Done" -> End

## Step 6: Complete

End of Q&A session.
