# myk-cursor Plugin

Run prompts via Cursor's [agent CLI](https://docs.cursor.com/cli) from within Claude Code, with optional `--fix` mode for direct file changes.

## Why

Claude Code is the primary workflow tool, but Cursor has access to additional models (GPT-5.3, Gemini 3 Pro, Grok, etc.).
This plugin bridges the two tools, enabling cross-tool workflows like:

- Claude plans a feature, then invokes Cursor to review the plan
- Claude writes code, then sends it to a different model for review
- Route any ad-hoc prompt to a specific model via Cursor

## Prerequisites

- [Cursor](https://cursor.com) installed with CLI enabled
- Cursor agent CLI available on PATH (default: `~/.local/bin/agent`)
- Authenticated in Cursor (`agent status` to verify)

## Installation

```bash
/plugin marketplace add myk-org/claude-code-config
/plugin install myk-cursor@myk-org
```

## Commands

### `/myk-cursor:prompt`

Run a prompt through Cursor's agent CLI.

**Syntax:**

```text
/myk-cursor:prompt [--fix] [--model <model>] <prompt>
```

When `--fix` is passed, Cursor applies file changes directly instead of only
returning text output. `--fix` and `--model` can appear in either order before
the prompt text. If the worktree is already dirty, the command asks before
proceeding instead of auto-committing your changes.

**Examples:**

```bash
# Ask a question using the default model
/myk-cursor:prompt What are best practices for HTML parsing in Python?

# Review a file with a specific model
/myk-cursor:prompt --model gemini-3-pro Review plugins/myk-cursor/README.md for issues

# Get a second opinion on architecture
/myk-cursor:prompt --model gpt-5.3-codex Analyze the plugin architecture in this codebase

# Review a plan file
/myk-cursor:prompt Review the implementation plan at /tmp/claude/my-plan.md

# Fix failing tests (applies file changes)
/myk-cursor:prompt --fix Fix the failing tests

# Review and fix code quality issues with a specific model
/myk-cursor:prompt --model gemini-3-pro --fix Review and fix code quality issues
```

## Available Models

List available models with:

```bash
agent --list-models
```

Available models depend on your Cursor subscription and change over time. Use the command above to see the current list.
