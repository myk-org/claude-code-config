---
name: describe
description: Generate a description for code changes - local or pull request
---

# Qodo Describe

Generate a comprehensive description of code changes. Works with local changes or pull requests.

## Usage

```bash
/qodo:describe                            # Describe local uncommitted changes
/qodo:describe --base main                # Describe changes compared to main
/qodo:describe 123                        # Generate description for PR #123
/qodo:describe https://github.com/.../42  # Generate description for PR by URL
```

## Workflow

### Mode Detection

1. Parse `$ARGUMENTS` to detect mode:
   - If contains PR number or URL -> **PR mode**
   - Otherwise -> **Local mode**

### Local Mode

1. Get diff: `git diff HEAD` (or `--base <branch>`)
2. Analyze changes and generate:
   - Summary of what changed
   - Type of change (feature, fix, refactor, etc.)
   - Key files modified
   - Impact description

### PR Mode

1. Resolve PR URL from number if needed
2. Run pr-agent describe:

   ```bash
   python -m pr_agent.cli --pr_url=<url> /describe
   ```

   Or analyze diff directly if pr-agent unavailable.

3. Present generated description

4. **Ask user**: "Do you want to update the PR description with this?"
   - If YES: Update PR via `gh pr edit <number> --body "..."`
   - If NO: Just show the description

## Arguments

- `<PR_NUMBER>`: PR number (e.g., `123`)
- `<PR_URL>`: Full PR URL
- `--base <branch>`: Branch to compare against (local mode)

## Examples

```bash
# Local
/qodo:describe
/qodo:describe --base origin/main

# PR
/qodo:describe 42
/qodo:describe https://github.com/myk-org/repo/pull/42
```
