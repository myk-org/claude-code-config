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
/myk-acpx:prompt <agent>[,agent2,...] [--fix | --peer | --exec] [--model <model>] <prompt>
```

**Supported agents:** pi, openclaw, codex, claude, gemini, cursor, copilot, droid, iflow, kilocode, kimi, kiro, opencode, qwen

**Examples:**

```bash
# Fix tests with Codex
/myk-acpx:prompt codex fix the failing tests

# Review code with Gemini
/myk-acpx:prompt gemini review this codebase for security issues

# One-shot summary with Codex
/myk-acpx:prompt codex --exec summarize this repo

# Use a specific model
/myk-acpx:prompt codex --model o3-pro review the architecture

# Fix code with Codex (agent gets write access)
/myk-acpx:prompt codex --fix fix the code quality issues

# AI-to-AI peer review with Gemini
/myk-acpx:prompt gemini --peer review this code

# Peer review with specific model
/myk-acpx:prompt codex --peer --model o3-pro review the architecture

# Multi-agent review (parallel)
/myk-acpx:prompt cursor,codex review this code

# 3-way peer review debate
/myk-acpx:prompt cursor,gemini,codex --peer review the architecture
```

## Modes

| Mode | Flag | Description |
|------|------|-------------|
| Default | (none) | Agent reads and reviews, no file changes |
| Fix | `--fix` | Agent can modify files directly, diff shown after |
| Peer | `--peer` | AI-to-AI debate loop between Claude and the agent |
| Exec | `--exec` | One-shot stateless execution, no session persistence |

`--fix`, `--peer`, and `--exec` are mutually exclusive.

Multiple agents can be specified as a comma-separated list. `--fix` requires a single agent; all other modes support multiple agents running in parallel.

## Known Issues

- Cursor persistent sessions may fail with acpx v0.3.x due to a `session/load` protocol mismatch
  ([#152](https://github.com/openclaw/acpx/issues/152),
  [#161](https://github.com/openclaw/acpx/issues/161)).
  The plugin automatically falls back to one-shot mode when this occurs.
  For full Cursor session support, use `/myk-cursor:prompt` instead.
