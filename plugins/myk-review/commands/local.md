---
description: Review uncommitted changes or changes compared to a branch
argument-hint: [BRANCH]
allowed-tools: Bash(git:*), Task, AskUserQuestion
---

# Local Code Review Command

Review uncommitted changes or changes compared to a specified branch.

**MANDATORY: This command MUST use the `code-reviewer` agent via Task tool.**

## Usage

- `/myk-review:local` - Review uncommitted changes (staged + unstaged)
- `/myk-review:local main` - Review changes compared to main branch
- `/myk-review:local feature/branch` - Review changes compared to specified branch

## Workflow

### Step 1: Get the diff

**If argument is provided (`$ARGUMENTS` is not empty):**

Compare current branch against the specified branch:

```bash
git diff "$ARGUMENTS"...HEAD
```

**If no argument provided:**

Get all uncommitted changes (staged + unstaged):

```bash
git diff HEAD
```

### Step 2: Route to code-reviewer agent (MANDATORY)

**CRITICAL: You MUST use the Task tool with `code-reviewer` agent.**

Delegate to `code-reviewer` with the diff and ask it to analyze for:

1. Code quality and best practices
2. Potential bugs or logic errors
3. Security vulnerabilities
4. Performance issues
5. Naming conventions and readability
6. Missing error handling
7. Code duplication
8. Suggestions for improvement

### Step 3: Present the review

Display the code-reviewer agent's findings grouped by:

- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (nice to have)
- Positive observations (good patterns found)
