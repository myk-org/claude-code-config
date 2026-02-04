---
name: ask
description: Ask questions about code changes - local or pull request
---

# Qodo Ask

Ask questions about code changes and get AI-powered answers. Works with local changes or pull requests.

## Usage

```bash
/qodo:ask "What does this change do?"                    # Ask about local changes
/qodo:ask "What does this change do?" --base main        # Compare against main
/qodo:ask "Are there security issues?" 123               # Ask about PR #123
/qodo:ask "Explain the auth flow" https://github.com/... # Ask about PR by URL
```

## Workflow

### Mode Detection

1. Parse `$ARGUMENTS` to detect mode:
   - If contains PR number or URL -> **PR mode**
   - Otherwise -> **Local mode**

### Local Mode

1. Get diff: `git diff HEAD` (or `--base <branch>`)
2. Analyze the question in context of the diff
3. Provide detailed answer based on the changes

### PR Mode

1. Resolve PR URL from number if needed
2. Get PR context: diff, description, comments
3. Run pr-agent ask:

   ```bash
   python -m pr_agent.cli --pr_url=<url> /ask "<question>"
   ```

   Or analyze directly if pr-agent unavailable.

4. Provide detailed answer

## Arguments

- `"<question>"`: The question to ask (required)
- `<PR_NUMBER>`: PR number (e.g., `123`)
- `<PR_URL>`: Full PR URL
- `--base <branch>`: Branch to compare against (local mode)

## Examples

```bash
# Local
/qodo:ask "What are the main changes?"
/qodo:ask "Are there any security concerns?" --base main
/qodo:ask "What files were modified?"

# PR
/qodo:ask "What does this PR do?" 42
/qodo:ask "Are there untested code paths?" 42
/qodo:ask "Explain the caching strategy" https://github.com/myk-org/repo/pull/42
```
