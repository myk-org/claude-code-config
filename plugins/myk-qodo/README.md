# myk-qodo Review Plugin for Claude Code

AI-powered code review integration using [Qodo](https://qodo.ai).

## Overview

All skills support **dual mode**:

- **Local mode** (default): Operate on uncommitted changes in your working directory
- **PR mode**: Operate on a pull request when you provide a PR number or URL

## Prerequisites

Install the Qodo CLI:

```bash
npm install -g @qodo/command
```

## Installation

### From Marketplace

```bash
/plugin marketplace add myk-org/claude-code-config
```

## Available Skills

### /myk-qodo:review

Review code changes for bugs, security issues, and code quality.

```bash
# Local mode (default) - review uncommitted changes
/myk-qodo:review
/myk-qodo:review --base origin/main    # Compare against specific branch
/myk-qodo:review --staged              # Review only staged changes
/myk-qodo:review --focus security      # Focus on specific area
/myk-qodo:review --model claude-4-opus # Use a specific model

# PR mode - review a pull request
/myk-qodo:review 123                              # Review PR #123
/myk-qodo:review https://github.com/owner/repo/pull/123
```

**Features:**

- Security vulnerabilities detection
- Bug and edge case identification
- Code quality analysis
- Performance concerns
- Test coverage gaps

**PR mode behavior:** After reviewing, asks if you want to post findings as inline comments on the PR.

### /myk-qodo:describe

Generate a comprehensive description of code changes.

```bash
# Local mode (default) - describe uncommitted changes
/myk-qodo:describe
/myk-qodo:describe --base origin/main
/myk-qodo:describe --model gpt-4       # Use a specific model

# PR mode - generate description for a pull request
/myk-qodo:describe 123
/myk-qodo:describe https://github.com/owner/repo/pull/123
```

**Features:**

- Automatic summary generation
- Change type classification (feature, fix, refactor)
- File-by-file walkthrough
- Key changes highlighting

**PR mode behavior:** After generating, asks if you want to update the PR description with the generated content.

### /myk-qodo:improve

Get actionable code improvement suggestions.

```bash
# Local mode (default) - improve uncommitted changes
/myk-qodo:improve
/myk-qodo:improve --base origin/main
/myk-qodo:improve --model claude-4-opus # Use a specific model

# PR mode - suggest improvements for a pull request
/myk-qodo:improve 123
/myk-qodo:improve https://github.com/owner/repo/pull/123
```

**Features:**

- Code simplifications
- Better patterns and idioms
- Performance optimizations
- Readability improvements
- Error handling enhancements

**PR mode behavior:** After suggestions, asks which improvements you want to apply to local files.

### /myk-qodo:ask

Ask questions about code changes and get AI-powered answers.

```bash
# Local mode (default) - ask about uncommitted changes
/myk-qodo:ask "What are the main changes?"
/myk-qodo:ask "Are there any security concerns?" --base main
/myk-qodo:ask "Explain this code" --model gpt-4  # Use a specific model

# PR mode - ask about a pull request
/myk-qodo:ask "What does this PR do?" 123
/myk-qodo:ask "Are there untested code paths?" 123
/myk-qodo:ask "Explain the caching strategy" https://github.com/owner/repo/pull/123
```

**Common questions:**

- "What are the main changes?"
- "Are there any breaking changes?"
- "What tests should be added?"
- "Are there any security concerns?"
- "What's the impact on performance?"

## Model Selection

List available models:

```bash
qodo models
```

Use a specific model:

```bash
/myk-qodo:review --model claude-4.5-sonnet
/myk-qodo:describe 123 --model gpt-4
```

## Troubleshooting

### "qodo not found"

Install the Qodo CLI:

```bash
npm install -g @qodo/command
```

### Authentication issues

Login to Qodo:

```bash
qodo login
```

### "No changes found"

For local mode, ensure you have uncommitted changes:

```bash
git status
git diff HEAD
```

### "No PR found for current branch"

When using PR mode, provide the PR number or URL directly:

```bash
/myk-qodo:review 123
/myk-qodo:describe https://github.com/owner/repo/pull/123
```

## License

MIT
