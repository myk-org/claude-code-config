---
name: describe
description: Generate AI-powered pull request description using Qodo PR-Agent
---

# Qodo Describe Skill

Automatically generate a comprehensive pull request description using Qodo PR-Agent.

## Usage

```bash
/qodo-describe [PR_URL]
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

### Step 2: Run Qodo Describe

Execute the pr-agent describe command:

```bash
python -m pr_agent.cli --pr_url="<PR_URL>" /describe
```

### Step 3: Present Results

Display the generated description, which typically includes:

- Summary of changes
- Type of change (feature, fix, refactor, etc.)
- Walkthrough of modified files
- Key changes highlighted

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
# Describe current branch's PR
/qodo-describe

# Describe specific PR
/qodo-describe https://github.com/myk-org/my-repo/pull/42
```

## Notes

- The generated description will be posted as a comment on the PR
- The PR body itself is not modified (only a comment is added)
- To update the PR body, manually copy the relevant sections from the comment
