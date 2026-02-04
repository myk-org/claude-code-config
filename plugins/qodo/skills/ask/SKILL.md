---
name: ask
description: Ask questions about a pull request using Qodo PR-Agent
---

# Qodo Ask Skill

Ask questions about a pull request and get AI-powered answers using Qodo PR-Agent.

## Usage

```bash
/qodo:ask "<question>" [PR_URL]
```

## Arguments

- `question` (required): The question to ask about the PR. Must be quoted.
- `PR_URL` (optional): GitHub pull request URL. If not provided, detects from current branch.

## Execution Steps

### Step 1: Parse Question

Extract the question from the arguments. The question should be enclosed in quotes.

If no question is provided, prompt the user to provide one.

### Step 2: Determine PR URL

If a PR URL is provided as an argument, use it directly.

Otherwise, detect the PR from the current branch:

```bash
gh pr view --json url --jq '.url'
```

If no PR is found, inform the user they need to create a PR first or provide a URL.

### Step 3: Run Qodo Ask

Execute the pr-agent ask command:

```bash
python -m pr_agent.cli --pr_url="<PR_URL>" /ask "<question>"
```

### Step 4: Present Results

Display the answer to the user's question. The response will be based on:

- The PR diff and changes
- File context and history
- Code relationships and dependencies

## Environment Requirements

The following environment variables must be set:

- `GITHUB_TOKEN` or `GITHUB_USER_TOKEN` - GitHub access token
- `OPENAI_KEY` or `ANTHROPIC_KEY` - AI provider API key

## Error Handling

- If pr-agent is not installed, suggest: `pip install pr-agent`
- If environment variables are missing, list required variables
- If PR URL is invalid, show expected format: `https://github.com/owner/repo/pull/123`
- If question is missing, prompt user to provide one

## Examples

```bash
# Ask about current branch's PR
/qodo:ask "What are the main changes in this PR?"

# Ask about testing
/qodo:ask "Are there any untested code paths?"

# Ask about specific functionality
/qodo:ask "How does the new authentication flow work?"

# Ask about specific PR
/qodo:ask "What security implications does this have?" https://github.com/myk-org/my-repo/pull/42
```

## Common Questions

- "What are the main changes?"
- "Are there any breaking changes?"
- "What tests should be added?"
- "Are there any security concerns?"
- "What's the impact on performance?"
- "Does this follow our coding standards?"
