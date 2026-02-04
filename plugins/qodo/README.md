# Qodo Review Plugin for Claude Code

AI-powered code review integration using [Qodo PR-Agent](https://github.com/Codium-ai/pr-agent).

## Overview

All skills support **dual mode**:

- **Local mode** (default): Operate on uncommitted changes in your working directory
- **PR mode**: Operate on a pull request when you provide a PR number or URL

## Prerequisites

### Option 1: pip installation (recommended)

```bash
pip install pr-agent
```

### Option 2: Docker

```bash
docker pull codiumai/pr-agent:latest
```

Note: When using Docker, you'll need to modify the commands to use:

```bash
docker run -e GITHUB_TOKEN -e OPENAI_KEY codiumai/pr-agent:latest --pr_url="<PR_URL>" /review
```

## Environment Variables

Set the following environment variables before using the plugin:

### Required

```bash
# GitHub authentication
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
# OR
export GITHUB_USER_TOKEN="ghp_xxxxxxxxxxxx"

# AI Provider (choose one)
export OPENAI_KEY="sk-xxxxxxxxxxxx"
# OR
export ANTHROPIC_KEY="sk-ant-xxxxxxxxxxxx"
```

### Optional

```bash
# Custom configuration file
export PR_AGENT_CONFIG="/path/to/.pr_agent.toml"
```

## Installation

### From Marketplace

```bash
/plugin marketplace add myk-org/claude-code-config
```

### Manual Installation

Clone the repository and symlink the plugin:

```bash
git clone https://github.com/myk-org/claude-code-config.git
ln -s /path/to/claude-code-config/plugins/qodo ~/.claude/plugins/qodo
```

## Available Skills

### /qodo:review

Review code changes for bugs, security issues, and code quality.

```bash
# Local mode (default) - review uncommitted changes
/qodo:review
/qodo:review --base origin/main    # Compare against specific branch
/qodo:review --staged              # Review only staged changes
/qodo:review --focus security      # Focus on specific area

# PR mode - review a pull request
/qodo:review 123                              # Review PR #123
/qodo:review https://github.com/owner/repo/pull/123
```

**Features:**

- Security vulnerabilities detection
- Bug and edge case identification
- Code quality analysis
- Performance concerns
- Test coverage gaps

**PR mode behavior:** After reviewing, asks if you want to post findings as inline comments on the PR.

### /qodo:describe

Generate a comprehensive description of code changes.

```bash
# Local mode (default) - describe uncommitted changes
/qodo:describe
/qodo:describe --base origin/main

# PR mode - generate description for a pull request
/qodo:describe 123
/qodo:describe https://github.com/owner/repo/pull/123
```

**Features:**

- Automatic summary generation
- Change type classification (feature, fix, refactor)
- File-by-file walkthrough
- Key changes highlighting

**PR mode behavior:** After generating, asks if you want to update the PR description with the generated content.

### /qodo:improve

Get actionable code improvement suggestions.

```bash
# Local mode (default) - improve uncommitted changes
/qodo:improve
/qodo:improve --base origin/main

# PR mode - suggest improvements for a pull request
/qodo:improve 123
/qodo:improve https://github.com/owner/repo/pull/123
```

**Features:**

- Code simplifications
- Better patterns and idioms
- Performance optimizations
- Readability improvements
- Error handling enhancements

**PR mode behavior:** After suggestions, asks which improvements you want to apply to local files.

### /qodo:ask

Ask questions about code changes and get AI-powered answers.

```bash
# Local mode (default) - ask about uncommitted changes
/qodo:ask "What are the main changes?"
/qodo:ask "Are there any security concerns?" --base main

# PR mode - ask about a pull request
/qodo:ask "What does this PR do?" 123
/qodo:ask "Are there untested code paths?" 123
/qodo:ask "Explain the caching strategy" https://github.com/owner/repo/pull/123
```

**Common questions:**

- "What are the main changes?"
- "Are there any breaking changes?"
- "What tests should be added?"
- "Are there any security concerns?"
- "What's the impact on performance?"

## Configuration

Create a `.pr_agent.toml` file in your repository root for custom configuration:

```toml
[pr_reviewer]
require_tests_review = true
require_security_review = true
require_focused_review = true

[pr_description]
publish_labels = true
publish_description_as_comment = false

[pr_code_suggestions]
num_code_suggestions = 4
```

See [PR-Agent Configuration](https://pr-agent-docs.codium.ai/usage-guide/configuration_options/) for all options.

## Troubleshooting

### "pr-agent not found"

Install pr-agent:

```bash
pip install pr-agent
```

### "GITHUB_TOKEN not set"

Set your GitHub token:

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
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
/qodo:review 123
/qodo:describe https://github.com/owner/repo/pull/123
```

### "API key not configured"

Set your AI provider key:

```bash
export OPENAI_KEY="sk-xxxxxxxxxxxx"
# or
export ANTHROPIC_KEY="sk-ant-xxxxxxxxxxxx"
```

## License

MIT
