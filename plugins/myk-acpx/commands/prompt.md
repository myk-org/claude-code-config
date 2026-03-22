---
description: Run a prompt via acpx to any supported coding agent
argument-hint: <agent> [--exec] [--model <model>] <prompt>
allowed-tools: Bash(acpx:*), AskUserQuestion, Agent, Edit, Write, Read, Glob, Grep
---

# acpx Multi-Agent Prompt Command

Run a prompt through [acpx](https://github.com/openclaw/acpx) to any ACP-compatible coding agent.

## Supported Agents

| Agent | Wraps |
|-------|-------|
| `pi` | Pi Coding Agent |
| `openclaw` | OpenClaw ACP bridge |
| `codex` | Codex CLI (OpenAI) |
| `claude` | Claude Code |
| `gemini` | Gemini CLI |
| `cursor` | Cursor CLI |
| `copilot` | GitHub Copilot CLI |
| `droid` | Factory Droid |
| `iflow` | iFlow CLI |
| `kilocode` | Kilocode |
| `kimi` | Kimi CLI |
| `kiro` | Kiro CLI |
| `opencode` | OpenCode |
| `qwen` | Qwen Code |

## Usage

- `/myk-acpx:prompt codex fix the tests`
- `/myk-acpx:prompt cursor review this code`
- `/myk-acpx:prompt gemini explain this function`
- `/myk-acpx:prompt codex --exec summarize this repo`
- `/myk-acpx:prompt codex --model o3-pro review the architecture`

## Workflow

### Step 1: Prerequisites Check

#### 1a: Check acpx

```bash
acpx --version
```

If not found, ask the user via AskUserQuestion:

"acpx is not installed. It provides structured access to multiple coding agents (Codex, Cursor, Gemini, etc.) via the Agent Client Protocol.

Install it now?"

Options:

- **Yes (Recommended)** — Install globally with `npm install -g acpx@latest`
- **No** — Abort

If user selects Yes, run:

```bash
npm install -g acpx@latest
```

Verify installation:

```bash
acpx --version
```

If installation fails, display the error and abort.

#### 1b: Verify Agent Prerequisite

The underlying coding agent must be installed separately. acpx auto-downloads ACP adapters, but the agent itself (e.g., Codex CLI, Cursor CLI) must be available.

### Step 2: Parse Arguments

Parse `$ARGUMENTS` to extract the agent name and prompt:

1. The **first token** is the agent name (required). Must be one of the supported agents listed above.
2. After the agent name, consume optional flags:
   - `--exec` — one-shot mode (no session persistence, stateless)
   - `--model <model>` — select a specific model (agent-dependent)
3. Everything after flags is the prompt text.

**Flag validation:**

- If `--exec` appears more than once, abort with: "Duplicate --exec flag."
- If `--model` appears more than once, abort with: "Duplicate --model flag."
- If the input ends with `--model` and no following word, abort with:
  "Missing model name after --model flag."
- If the word after `--model` starts with `--`, abort with:
  "Invalid model name. Model name cannot start with --."

If no agent name is provided, abort with:
"No agent specified. Usage: `/myk-acpx:prompt <agent> [--exec] [--model <model>] <prompt>`

Supported agents: pi, openclaw, codex, claude, gemini, cursor, copilot, droid, iflow, kilocode, kimi, kiro, opencode, qwen"

If the agent name is not recognized, abort with:
"Unknown agent: `<name>`. Supported agents: pi, openclaw, codex, claude, gemini, cursor, copilot, droid, iflow, kilocode, kimi, kiro, opencode, qwen"

If no prompt is provided after the agent name, abort with:
"No prompt provided. Usage: `/myk-acpx:prompt <agent> [--exec] [--model <model>] <prompt>`"

### Step 3: Session Management

**If `--exec` was passed, skip this step** (exec mode is stateless).

Ensure a session exists for the current directory:

```bash
acpx <agent> sessions ensure
```

If this fails, try creating a new session:

```bash
acpx <agent> sessions new
```

If session creation also fails, check the error output:

- If the error contains "Invalid params" or "session" and "not found", display:

  "acpx session management failed for `<agent>`. This is a known issue — see:
  - <https://github.com/openclaw/acpx/issues/152>
  - <https://github.com/openclaw/acpx/issues/161>

  Falling back to one-shot mode (`--exec`)."

  Then proceed with exec mode for this invocation.

- For any other error, display the error and abort.

### Step 4: Run Prompt

Build and execute the acpx command:

**Exec mode (stateless):**

```bash
acpx --approve-reads <agent> exec '<prompt>'
acpx --approve-reads <agent> exec --model <model> '<prompt>'
```

**Session mode (persistent):**

```bash
acpx --approve-reads <agent> '<prompt>'
acpx --approve-reads <agent> --model <model> '<prompt>'
```

```text
# Replace --approve-reads with --approve-all if prompt contains action words:
# fix, modify, change, edit, update, create, delete
```

**Shell safety:** Single-quote the prompt to prevent shell expansion. Replace any single quotes in the prompt with `'\''` before interpolation.

**Timeout:** Set the Bash tool timeout to 300000ms (5 minutes).

**Permissions:** Use `--approve-reads` by default (allows the agent to read
files). If the prompt contains action words like "fix", "modify", "change",
"edit", "update", "create", or "delete", use `--approve-all` instead.

If the command exits with a non-zero code, display the raw output as an error.

### Step 5: Display Result

Display the output from acpx to the user. acpx formats output as a readable stream with tool updates by default.

After successful execution, display:

```text
Agent: <agent>
Mode: [session | exec (one-shot)]
```

If in session mode, also show:

```text
Session active. Send follow-up prompts with: /myk-acpx:prompt <agent> <follow-up>
```
