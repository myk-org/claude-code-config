---
name: review
description: Review code changes - local uncommitted changes or a pull request
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

## 2. Diff Mode Selection (REQUIRED for local review)

If NO PR number/URL was provided AND `--base`/`--staged` was NOT provided:

**YOU MUST use AskUserQuestion tool NOW** to ask:

- Question: "What changes would you like to review?"
- Options:
  - "All uncommitted changes (git diff HEAD)"
  - "Compare against main branch"
  - "Only staged changes"
  - "Compare against a specific branch"

If user selects "Compare against a specific branch":

- Ask: "Which branch would you like to compare against?"
- Wait for user to type the branch name
- Use the provided branch name for the comparison

DO NOT PROCEED until user selects a mode.

---

## Qodo Code Review

Review code changes for bugs, security issues, and code quality. Works with local changes or pull requests.

### Usage

```bash
/qodo:review                              # Review local uncommitted changes
/qodo:review --base main                  # Compare local changes against main
/qodo:review --staged                     # Review only staged changes
/qodo:review 123                          # Review PR #123
/qodo:review https://github.com/.../42    # Review PR by URL
```

### Workflow

#### Step 1: Execute Review

Parse `$ARGUMENTS` to detect mode:

- If contains PR number (e.g., `123`) or URL -> **PR mode**
- Otherwise -> **Local mode**

#### Step 2: Local Mode (no PR specified)

1. Get diff based on arguments:
   - Default: `git diff HEAD` (all uncommitted)
   - `--base <branch>`: `git diff <branch>...HEAD`
   - `--staged`: `git diff --cached`

2. Analyze the diff for:
   - Security vulnerabilities
   - Potential bugs and edge cases
   - Code quality issues
   - Performance concerns
   - Test coverage gaps

3. Present findings to user

#### Step 3: PR Mode (PR number or URL specified)

1. Resolve PR URL:
   - If number: `gh pr view <number> --json url -q '.url'`
   - If URL: use directly

2. Get PR diff: `gh pr diff <number>`

3. Run pr-agent review if available:

   ```bash
   python -m pr_agent.cli --pr_url=<url> /review --config.model=<selected_model>
   ```

   Or analyze diff directly if pr-agent unavailable.

4. Present findings to user

#### Step 4: Address Findings (Interactive)

After presenting the review findings to the user, ask if they want to address them:

**Use AskUserQuestion tool** with options:

- "Address all findings" - Fix all issues automatically
- "Select which to address" - Let user pick specific findings
- "Skip" - Just show findings, don't fix anything

**If user selects "Address all":**

1. For each finding, delegate to appropriate specialist agent (python-expert, go-expert, etc.)
2. Apply fixes to the code
3. After all fixes, run review again to verify

**If user selects "Select which to address":**

1. Present numbered list of findings
2. Ask user which ones to fix (e.g., "1,3,5" or "all except 2")
3. Fix only selected findings
4. After fixes, run review again to verify

**If user selects "Skip":**

1. End the review session
2. Findings are shown but no changes made

#### Step 5: Post to PR (PR mode only)

After addressing findings (or if user skipped), for PR mode ask:

**Use AskUserQuestion tool** with options:

- "Post findings as PR comments" - Add inline comments to the PR
- "Skip posting" - Don't post anything

If posting, use GitHub API to add inline review comments.

### Arguments

- `<PR_NUMBER>`: PR number to review (e.g., `123`)
- `<PR_URL>`: Full PR URL
- `--base <branch>`: Branch to compare against (local mode)
- `--staged`: Only staged changes (local mode)
- `--focus <area>`: Focus area (security, performance, tests)
- `--model <name>`: AI model to use (run `qodo models` to see available options)

### Examples

```bash
# Local review
/qodo:review
/qodo:review --base origin/main
/qodo:review --staged

# PR review
/qodo:review 42
/qodo:review https://github.com/myk-org/repo/pull/42
/qodo:review 42 --focus security

# With model selection
/qodo:review --model claude-4-opus
/qodo:review 42 --model gpt-4
```

### Interactive Flow Example

A typical review session with the interactive workflow:

```text
User: /qodo:review 42

Claude: Which AI model would you like to use for this review?

        1. claude-4-opus
        2. gpt-4
        3. gemini-pro

        Enter the number of your choice:

User: 1

Claude: ## Review Findings for PR #42

        Found 3 issues:

        1. [Security] SQL injection vulnerability in user_query.py:45
        2. [Bug] Null pointer dereference in parser.go:128
        3. [Quality] Missing error handling in api/handler.py:67

        How would you like to proceed?
        [Address all findings] [Select which to address] [Skip]

User: Select which to address

Claude: Which findings would you like to fix?
        Enter numbers (e.g., "1,3" or "all except 2"):

User: 1,3

Claude: Fixing 2 findings...
        - Fixed SQL injection in user_query.py
        - Added error handling in api/handler.py

        Re-running review to verify...
        All selected issues resolved.

        Would you like to post findings as PR comments?
        [Post findings as PR comments] [Skip posting]

User: Post findings as PR comments

Claude: Posted 3 inline comments to PR #42.
```

### Posting Comments (PR mode only)

Comments are posted as inline review comments on the PR using:

```bash
gh api repos/{owner}/{repo}/pulls/{number}/comments -f body="..." -f path="..." -f line=N
```
