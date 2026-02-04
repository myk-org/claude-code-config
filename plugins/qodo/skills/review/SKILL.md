---
name: review
description: Review local code changes for bugs, security issues, and code quality
---

# Qodo Code Review

Review uncommitted code changes in the current repository.

## Usage

```bash
/qodo:review                    # Review all uncommitted changes
/qodo:review --base main        # Compare against main branch
/qodo:review --staged           # Review only staged changes
```

## Workflow

### Step 1: Get the Diff

Determine which diff to analyze based on arguments:

- **Default**: `git diff HEAD` (all uncommitted changes)
- **With `--base <branch>`**: `git diff <branch>...HEAD`
- **With `--staged`**: `git diff --cached`

```bash
# Default - all uncommitted changes
git diff HEAD

# Compare against specific branch
git diff origin/main...HEAD

# Only staged changes
git diff --cached
```

### Step 2: Analyze Changes

If pr-agent is available, use it for AI-powered review:

```bash
# For local review without PR
python -m pr_agent.cli --pr_url="" /review --config.publish_output=false
```

If pr-agent is not available, analyze the diff directly and provide:

- Security vulnerabilities
- Potential bugs
- Code quality issues
- Performance concerns
- Suggestions for improvement

### Step 3: Present Results

Display the review results to the user, highlighting:

- Security issues (critical priority)
- Potential bugs and logic errors
- Code quality concerns
- Performance optimizations
- Suggested improvements

## Arguments

- `--base <branch>`: Branch to compare against (default: current HEAD)
- `--staged`: Only review staged changes
- `--focus <area>`: Focus on specific area (security, performance, tests)

Supported focus areas:

- `security` - Focus on security vulnerabilities and best practices
- `performance` - Focus on performance optimizations
- `tests` - Focus on test coverage and test quality
- `docs` - Focus on documentation completeness
- Custom text is also accepted

## Environment Requirements

The following environment variables are required for pr-agent:

- `GITHUB_TOKEN` or `GITHUB_USER_TOKEN` - GitHub access token
- `OPENAI_KEY` or `ANTHROPIC_KEY` - AI provider API key

If pr-agent is not available, Claude will analyze the diff directly.

## Error Handling

- If no changes are detected, inform the user there is nothing to review
- If the specified base branch does not exist, suggest valid branch names
- If pr-agent is not installed, proceed with direct Claude analysis

## Examples

```bash
# Review all local changes
/qodo:review

# Review changes compared to main
/qodo:review --base origin/main

# Review only staged changes
/qodo:review --staged

# Focus on security issues
/qodo:review --focus security

# Combine options
/qodo:review --base main --focus performance
```
