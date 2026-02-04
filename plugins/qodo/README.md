# Qodo Review Plugin for Claude Code

AI-powered code review integration using [Qodo PR-Agent](https://github.com/Codium-ai/pr-agent).

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

Review local uncommitted code changes.

```bash
# Review all uncommitted changes
/qodo:review

# Compare against a specific branch
/qodo:review --base origin/main

# Review only staged changes
/qodo:review --staged

# Focus on specific area
/qodo:review --focus security
```

**Features:**

- Reviews local uncommitted changes
- Supports comparing against any branch
- Can review only staged changes
- Focus areas: security, performance, tests

### /qodo:describe

Generate AI-powered PR description.

```bash
# Describe current branch's PR
/qodo:describe

# Describe specific PR
/qodo:describe https://github.com/owner/repo/pull/123
```

**Features:**

- Automatic summary generation
- Change type classification
- File-by-file walkthrough
- Key changes highlighting

### /qodo:improve

Get actionable code improvement suggestions.

```bash
# Get improvements for current PR
/qodo:improve

# Get improvements for specific PR
/qodo:improve https://github.com/owner/repo/pull/123
```

**Features:**

- Inline code suggestions
- Performance optimizations
- Refactoring recommendations
- Best practice enforcement

### /qodo:ask

Ask questions about a pull request.

```bash
# Ask about current PR
/qodo:ask "What are the main changes?"

# Ask security questions
/qodo:ask "Are there any security concerns?"

# Ask about specific PR
/qodo:ask "What tests should be added?" https://github.com/owner/repo/pull/123
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

### "No PR found for current branch"

For `/qodo:describe`, `/qodo:improve`, and `/qodo:ask`:

1. Push your branch and create a PR first
2. Provide the PR URL directly: `/qodo:describe https://github.com/...`

Note: `/qodo:review` works with local changes and does not require a PR.

### "API key not configured"

Set your AI provider key:

```bash
export OPENAI_KEY="sk-xxxxxxxxxxxx"
# or
export ANTHROPIC_KEY="sk-ant-xxxxxxxxxxxx"
```

## License

MIT
