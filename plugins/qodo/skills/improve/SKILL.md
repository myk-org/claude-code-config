---
name: improve
description: Suggest code improvements for local changes or a pull request
---

# Qodo Improve

Suggest actionable code improvements. Works with local changes or pull requests.

## Usage

```bash
/qodo:improve                             # Improve local uncommitted changes
/qodo:improve --base main                 # Improve changes compared to main
/qodo:improve 123                         # Suggest improvements for PR #123
/qodo:improve https://github.com/.../42   # Suggest improvements for PR by URL
```

## Workflow

### Mode Detection

1. Parse `$ARGUMENTS` to detect mode:
   - If contains PR number or URL -> **PR mode**
   - Otherwise -> **Local mode**

### Local Mode

1. Get diff: `git diff HEAD` (or `--base <branch>`)
2. Analyze and suggest:
   - Code simplifications
   - Better patterns or idioms
   - Performance optimizations
   - Readability improvements
   - Error handling enhancements

### PR Mode

1. Resolve PR URL from number if needed
2. Run pr-agent improve:

   ```bash
   python -m pr_agent.cli --pr_url=<url> /improve
   ```

   Or analyze diff directly if pr-agent unavailable.

3. Present improvement suggestions

4. **Ask user**: "Do you want to apply any of these improvements?"
   - User can select which improvements to apply
   - Apply selected changes to local files

## Arguments

- `<PR_NUMBER>`: PR number (e.g., `123`)
- `<PR_URL>`: Full PR URL
- `--base <branch>`: Branch to compare against (local mode)

## Examples

```bash
# Local
/qodo:improve
/qodo:improve --base origin/main

# PR
/qodo:improve 42
/qodo:improve https://github.com/myk-org/repo/pull/42
```
