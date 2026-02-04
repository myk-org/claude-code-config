---
name: review
description: Review code changes - local uncommitted changes or a pull request
---

# Qodo Code Review

Review code changes for bugs, security issues, and code quality. Works with local changes or pull requests.

## Usage

```bash
/qodo:review                              # Review local uncommitted changes
/qodo:review --base main                  # Compare local changes against main
/qodo:review --staged                     # Review only staged changes
/qodo:review 123                          # Review PR #123
/qodo:review https://github.com/.../42    # Review PR by URL
```

## Workflow

### Mode Detection

1. Parse `$ARGUMENTS` to detect mode:
   - If contains PR number (e.g., `123`) or URL -> **PR mode**
   - Otherwise -> **Local mode**

### Local Mode (no PR specified)

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

### PR Mode (PR number or URL specified)

1. Resolve PR URL:
   - If number: `gh pr view <number> --json url -q '.url'`
   - If URL: use directly

2. Get PR diff: `gh pr diff <number>`

3. Run pr-agent review if available:

   ```bash
   python -m pr_agent.cli --pr_url=<url> /review
   ```

   Or analyze diff directly if pr-agent unavailable.

4. Present findings to user

5. **Ask user**: "Do you want to post these findings as review comments on the PR?"
   - If YES: Post inline comments using GitHub API
   - If NO: Done (findings shown locally only)

## Arguments

- `<PR_NUMBER>`: PR number to review (e.g., `123`)
- `<PR_URL>`: Full PR URL
- `--base <branch>`: Branch to compare against (local mode)
- `--staged`: Only staged changes (local mode)
- `--focus <area>`: Focus area (security, performance, tests)

## Examples

```bash
# Local review
/qodo:review
/qodo:review --base origin/main
/qodo:review --staged

# PR review
/qodo:review 42
/qodo:review https://github.com/myk-org/repo/pull/42
/qodo:review 42 --focus security
```

## Posting Comments (PR mode only)

After reviewing a PR, you'll be asked:

> Found X issues. Do you want to post these as review comments on PR #N?

If you confirm, comments are posted as inline review comments on the PR using:

```bash
gh api repos/{owner}/{repo}/pulls/{number}/comments -f body="..." -f path="..." -f line=N
```
