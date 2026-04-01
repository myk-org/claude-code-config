# myk-acpx Plugin

Run prompts to any ACP-compatible coding agent via [acpx](https://github.com/openclaw/acpx).

## Why

Access multiple coding agents (Codex, Cursor, Gemini, Copilot, and more) through a single unified interface
using the Agent Client Protocol (ACP). No PTY scraping — structured protocol with typed messages.

## Prerequisites

- [acpx](https://github.com/openclaw/acpx) — the plugin prompts to install if missing
- The underlying coding agent you want to use (e.g., Codex CLI, Cursor CLI)

## Installation

```bash
/plugin marketplace add myk-org/claude-code-config
/plugin install myk-acpx@myk-org
```

## Commands

### `/myk-acpx:prompt`

Run a prompt through acpx to any supported agent.

**Syntax:**

```text
/myk-acpx:prompt <agent[:model]>[,agent2[:model2],...] [--fix | --peer] <prompt>
```

**Supported agents:** pi, openclaw, codex, claude, gemini, cursor, copilot, droid, iflow, kilocode, kimi, kiro, opencode, qwen

**Examples:**

```bash
# Fix tests with Codex
/myk-acpx:prompt codex fix the failing tests

# Review code with Gemini
/myk-acpx:prompt gemini review this codebase for security issues

# Use a specific model
/myk-acpx:prompt codex:o3-pro review the architecture

# Fix code with Codex (agent gets write access)
/myk-acpx:prompt codex --fix fix the code quality issues

# Fix with specific model
/myk-acpx:prompt codex:gpt-4o --fix fix the code quality issues

# AI-to-AI peer review with Gemini
/myk-acpx:prompt gemini --peer review this code

# Multi-agent peer review (group conversation)
/myk-acpx:prompt cursor,claude --peer review this code

# 3-way peer review with per-agent models
/myk-acpx:prompt cursor:gpt-4o,gemini,codex:o3-pro --peer review the architecture

# Multi-agent review (parallel, non-peer)
/myk-acpx:prompt cursor,codex review this code
```

## Modes

| Mode | Flag | Description |
|------|------|-------------|
| Default | (none) | Agent reads and reviews, no file changes |
| Fix | `--fix` | Agent can modify files directly, diff shown after |
| Peer | `--peer` | AI-to-AI debate loop between Claude and the agent(s) |

`--fix` and `--peer` are mutually exclusive.

Multiple agents can be specified as a comma-separated list. `--fix` requires a single agent.
In `--peer` mode with multiple agents, a group conversation is created
where each peer sees all other peers' responses.

## Known Issues

- Cursor persistent sessions may fail with acpx v0.3.x due to a `session/load` protocol mismatch
  ([#152](https://github.com/openclaw/acpx/issues/152),
  [#161](https://github.com/openclaw/acpx/issues/161)).
  The command displays the error and aborts when this occurs.
  If you need the native Cursor CLI with persistent sessions and acpx session setup keeps failing,
  use the Cursor `agent` tool directly.
