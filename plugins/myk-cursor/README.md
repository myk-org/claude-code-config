# myk-cursor Plugin

> **DEPRECATED:** This plugin is deprecated in favor of
> [`myk-acpx`](../myk-acpx/README.md).
> Use `/myk-acpx:prompt cursor` instead of `/myk-cursor:prompt`.
> The myk-acpx plugin provides the same Cursor functionality plus multi-agent
> support and structured ACP protocol.

Run prompts via Cursor's [agent CLI](https://docs.cursor.com/cli) from within
Claude Code, with `--fix` mode for direct file changes and `--peer` mode for
autonomous AI-to-AI peer review.

## Why

Claude Code is the primary workflow tool, but Cursor has access to additional models (GPT-5.3, Gemini 3 Pro, Grok, etc.).
This plugin bridges the two tools, enabling cross-tool workflows like:

- Claude plans a feature, then invokes Cursor to review the plan
- Claude writes code, then sends it to a different model for review
- Route any ad-hoc prompt to a specific model via Cursor
- Two AIs review and debate code until they converge on agreement (`--peer`)

## Prerequisites

- [Cursor](https://cursor.com) installed with CLI enabled
- Cursor agent CLI (`agent`) available on PATH
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
/myk-cursor:prompt [--fix | --peer] [--model <model>] <prompt>
```

When `--fix` is passed, Cursor is allowed to apply file changes directly and
the command summarizes the resulting changes, including a git diff when
available. `--fix` and `--model` must appear before the prompt text, and can
appear in either order.

If the directory is not a Git repository, or if the worktree already has
uncommitted changes, the command asks before proceeding instead of
auto-committing your changes. `--trust` is always passed so Cursor can
access workspace files for reading; in fix mode, this also enables file writes.

When `--peer` is passed, an autonomous AI-to-AI peer review loop starts.
Cursor reviews the code, Claude evaluates the findings and fixes what it
agrees with, then responds to Cursor with what was addressed and what it
disagrees with (including technical reasoning). Cursor re-reviews, and the
loop continues until both AIs converge. `--peer` and `--fix` are mutually
exclusive.

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

# Autonomous AI-to-AI peer review
/myk-cursor:prompt --peer review

# Peer review with a specific model
/myk-cursor:prompt --peer --model gemini-3-pro Review this code
```

## Available Models

List available models with:

```bash
agent --list-models
```

Available models depend on your Cursor subscription and change over time. Use the command above to see the current list.
