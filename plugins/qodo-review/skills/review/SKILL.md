---
name: review
description: Run comprehensive Qodo AI code review on a pull request
---

# Qodo Review Skill

Perform a comprehensive code review on a pull request using Qodo PR-Agent.

## Usage

```bash
/qodo-review [PR_URL] [--focus "area"]
```

## Arguments

- `PR_URL` (optional): GitHub pull request URL. If not provided, detects from current branch.
- `--focus "area"` (optional): Focus the review on specific areas (e.g., "security", "performance", "tests").

## Execution Steps

### Step 1: Determine PR URL

If a PR URL is provided as an argument, use it directly.

Otherwise, detect the PR from the current branch:

```bash
gh pr view --json url --jq '.url'
```

If no PR is found, inform the user they need to create a PR first or provide a URL.

### Step 2: Parse Focus Areas

If `--focus` argument is provided, extract the focus area to pass as extra instructions.

Supported focus areas:

- `security` - Focus on security vulnerabilities and best practices
- `performance` - Focus on performance optimizations
- `tests` - Focus on test coverage and test quality
- `docs` - Focus on documentation completeness
- Custom text is also accepted

### Step 3: Run Qodo Review

Execute the pr-agent review command:

```bash
python -m pr_agent.cli --pr_url="<PR_URL>" /review
```

If focus areas are specified, include them as extra instructions:

```bash
python -m pr_agent.cli --pr_url="<PR_URL>" /review --pr_agent.extra_instructions="Focus on: <focus_area>"
```

### Step 4: Present Results

Display the review results to the user, highlighting:

- Security issues (critical priority)
- Test coverage gaps
- Code quality concerns
- Suggested improvements

## Environment Requirements

The following environment variables must be set:

- `GITHUB_TOKEN` or `GITHUB_USER_TOKEN` - GitHub access token
- `OPENAI_KEY` or `ANTHROPIC_KEY` - AI provider API key

## Error Handling

- If pr-agent is not installed, suggest: `pip install pr-agent`
- If environment variables are missing, list required variables
- If PR URL is invalid, show expected format: `https://github.com/owner/repo/pull/123`

## Examples

```bash
# Review current branch's PR
/qodo-review

# Review specific PR
/qodo-review https://github.com/myk-org/my-repo/pull/42

# Review with security focus
/qodo-review --focus "security"

# Review specific PR with performance focus
/qodo-review https://github.com/myk-org/my-repo/pull/42 --focus "performance"
```
