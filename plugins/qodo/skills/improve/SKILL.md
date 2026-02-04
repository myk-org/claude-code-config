---
name: improve
description: Get AI-powered code improvement suggestions using Qodo PR-Agent
---

# Qodo Improve Skill

Get actionable code improvement suggestions for a pull request using Qodo PR-Agent.

## Usage

```bash
/qodo:improve [PR_URL]
```

## Arguments

- `PR_URL` (optional): GitHub pull request URL. If not provided, detects from current branch.

## Execution Steps

### Step 1: Determine PR URL

If a PR URL is provided as an argument, use it directly.

Otherwise, detect the PR from the current branch:

```bash
gh pr view --json url --jq '.url'
```

If no PR is found, inform the user they need to create a PR first or provide a URL.

### Step 2: Run Qodo Improve

Execute the pr-agent improve command:

```bash
python -m pr_agent.cli --pr_url="<PR_URL>" /improve
```

### Step 3: Present Results

Display the improvement suggestions, which typically include:

- Code quality improvements
- Performance optimizations
- Best practice recommendations
- Refactoring suggestions
- Each suggestion includes the file, line number, and proposed change

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
# Get improvements for current branch's PR
/qodo:improve

# Get improvements for specific PR
/qodo:improve https://github.com/myk-org/my-repo/pull/42
```

## Notes

- Suggestions are posted as inline comments on the PR
- Each suggestion is actionable with specific code changes
- Focus is on improvements, not bugs (use `/qodo:review` for bug detection)
