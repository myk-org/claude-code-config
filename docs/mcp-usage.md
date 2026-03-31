# MCP Usage

This configuration expects all MCP server discovery and access to go through `mcpl` (MCP Launchpad). The working pattern is simple:

- Discover tools first.
- Inspect the schema if you are not sure about parameters.
- Call the tool only after you know the exact server, tool name, and JSON shape.

In other words, this setup does **not** expect users or agents to guess MCP tool names from memory.

> **Note:** MCP behavior in this repository is defined by `rules/`, enforced by `settings.json` and hooks, and checked at session start. There are no separate `.github/workflows` files for MCP in this repository.

## What you need to know first

The central rule lives in `rules/15-mcp-launchpad.md`:

```text
Use the `mcpl` command for all MCP server interactions.

MCP Launchpad is a unified CLI for discovering and executing tools from multiple MCP servers.
If a task requires functionality outside current capabilities, always check `mcpl` for available tools.
```

That same file makes the expectation explicit:

```text
## Workflow

**Never guess tool names** - always discover them first.
```

If you remember only one thing from this page, make it this:

> **Warning:** Do not guess server names, tool names, or parameter names. Use `mcpl search`, `mcpl list`, and `mcpl inspect` first.

## The discovery-first workflow

The repository already includes real examples in `rules/15-mcp-launchpad.md`. This is the intended flow.

### 1. Search for the right tool

Use `mcpl search` when you know what you want to do, but not which server or tool provides it:

```bash
mcpl search "list projects"
```

### 2. Inspect the tool before calling it

Use `mcpl inspect` when you want the schema or an example payload:

```bash
mcpl inspect sentry search_issues --example
```

### 3. Call the tool with the required JSON

Once you know the exact tool and parameters, call it directly:

```bash
mcpl call vercel list_projects '{"teamId": "team_xxx"}'
```

### 4. List tools when you already know the server

If you know the server but not the tool name, list that server's tools:

```bash
mcpl list vercel    # Shows all tools with required params
```

> **Tip:** `mcpl search` is best when you are exploring. `mcpl list <server>` is best when you already know the server.

## Common `mcpl` commands

These commands come directly from `rules/15-mcp-launchpad.md`.

| Command | Purpose |
|---|---|
| `mcpl search "<query>"` | Search all tools |
| `mcpl search "<query>" --limit N` | Search with more results |
| `mcpl list` | List all MCP servers |
| `mcpl list <server>` | List tools for one server |
| `mcpl inspect <server> <tool>` | Show full schema |
| `mcpl inspect <server> <tool> --example` | Show schema and example call |
| `mcpl call <server> <tool> '{}'` | Execute a tool with no arguments |
| `mcpl call <server> <tool> '{"param": "v"}'` | Execute a tool with arguments |
| `mcpl verify` | Check server connections |

For troubleshooting, the same rule file also documents:

| Command | Purpose |
|---|---|
| `mcpl session status` | Check daemon and connection status |
| `mcpl session stop` | Restart the daemon |
| `mcpl config` | Show current configuration |
| `mcpl call <server> <tool> '{}' --no-daemon` | Bypass the daemon for debugging |

## How roles are split in this configuration

This repository uses an orchestrator pattern. The main Claude conversation is the **orchestrator**, and specialist agents do the domain-specific work.

### Orchestrator: discover, then delegate

`rules/00-orchestrator-core.md` limits what the orchestrator should do directly:

```text
❌ **NEVER** use: Edit, Write, NotebookEdit, Bash (except `mcpl`), direct MCP calls
❌ **NEVER** delegate slash commands (`/command`) OR their internal operations - see slash command rules
✅ **ALWAYS** delegate other work to specialist agents
⚠️ Hooks will BLOCK violations
```

The allowed direct action is intentionally narrow:

```text
- Run `mcpl` (via Bash) for MCP server discovery only
```

And the routing rule is clear:

```text
❌ MCP tools → delegate to manager agents
```

In practical terms, the orchestrator should use `mcpl` to figure out what exists, then hand off MCP-backed work to the right specialist.

### Specialist agents: use the full `mcpl` workflow

The shared agent rules in `agents/00-base-rules.md` tell all specialist agents how to work with MCP:

```text
## MCP Server Access

Agents can access MCP (Model Context Protocol) servers via the `mcpl` command (MCP Launchpad).

**Key points:**

- **Never guess tool names** - always search/discover first
- Use `mcpl search "<query>"` to find tools across all servers
- Use `mcpl call <server> <tool> '<json>'` to execute tools
```

They also include this quick reference:

```bash
mcpl search "<query>"              # Find tools
mcpl list <server>                 # List server's tools
mcpl inspect <server> <tool>       # Get tool schema
mcpl call <server> <tool> '{}'     # Execute tool
```

## What this means for end users

If you are using this configuration, the safest way to request MCP-backed work is to describe the outcome you want and let the system discover the exact tool through `mcpl`.

Good requests:

- "Use `mcpl` to find the right tool for listing projects."
- "Search available MCP tools first, then call the correct one."
- "Inspect the tool schema before making the call."

Less helpful requests:

- Naming a server/tool combination you have not verified.
- Assuming parameter names without checking the schema.
- Treating MCP tools as if they were built-in commands.

> **Tip:** If you are unsure whether a tool exists, ask for discovery first. That matches how this configuration is designed to work.

## How the configuration enforces this

This behavior is not just documentation. It is built into the repository configuration.

### `settings.json` explicitly allows `mcpl`

In `settings.json`, `Bash(mcpl:*)` is allowed in both `permissions.allow` and `allowedTools`:

```json
"allow": [
  "Read(/tmp/claude/**)",
  "Edit(/tmp/claude/**)",
  "Write(/tmp/claude/**)",
  "Bash(mkdir -p /tmp/claude*)",
  "Bash(claude:*)",
  "Bash(sed -n:*)",
  "Bash(grep:*)",
  "Bash(mcpl:*)",
  "Bash(git -C:*)",
  "Bash(prek:*)"
]
```

```json
"allowedTools": [
  "Edit(/tmp/claude/**)",
  "Write(/tmp/claude/**)",
  "Read(/tmp/claude/**)",
  "Bash(mkdir -p /tmp/claude*)",
  "Bash(claude:*)",
  "Bash(sed -n:*)",
  "Bash(grep:*)",
  "Bash(mcpl:*)",
  "Bash(git -C:*)",
  "Bash(prek:*)"
]
```

This is why `mcpl` is the approved path for MCP discovery in this configuration.

### Session start checks whether `mcpl` is installed

`settings.json` runs `scripts/session-start-check.sh` on `SessionStart`:

```json
"SessionStart": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "~/.claude/scripts/session-start-check.sh",
        "timeout": 5000
      }
    ]
  }
]
```

That script always checks for `mcpl`:

```bash
# OPTIONAL: mcpl - MCP Launchpad (always check)
if ! command -v mcpl &>/dev/null; then
  missing_optional+=("[OPTIONAL] mcpl - MCP Launchpad for MCP server access
  Install: https://github.com/kenneth-liao/mcp-launchpad")
fi
```

> **Note:** The startup check labels `mcpl` as optional because not every task needs MCP. If you want MCP-backed workflows, treat it as required.

You can install MCP Launchpad here: [https://github.com/kenneth-liao/mcp-launchpad](https://github.com/kenneth-liao/mcp-launchpad)

### Prompt injection reinforces the rule on every request

`scripts/rule-injector.py` injects a reminder into every prompt:

```python
rule_reminder = (
    "[SYSTEM RULES] You are a MANAGER. NEVER do work directly. ALWAYS delegate:\n"
    "- Edit/Write → language specialists (python-expert, go-expert, etc.)\n"
    "- ALL Bash commands → bash-expert or appropriate specialist\n"
    "- Git commands → git-expert\n"
    "- MCP tools → manager agents\n"
    "- Multi-file exploration → Explore agent\n"
    "HOOKS WILL BLOCK VIOLATIONS."
)
```

That reminder works together with `rules/00-orchestrator-core.md` and `rules/15-mcp-launchpad.md` to keep the MCP workflow consistent.

## Troubleshooting

If MCP access is not working, start with the commands already documented in `rules/15-mcp-launchpad.md`:

```bash
mcpl verify
mcpl session status
mcpl session stop
mcpl config
mcpl call <server> <tool> '{}' --no-daemon
```

The same file also gives these recovery hints:

- If a server is not connecting, run `mcpl verify`.
- If connections look stale, run `mcpl session stop` and try again.
- If you hit timeouts, increase `MCPL_CONNECTION_TIMEOUT=120`.

> **Warning:** If a call fails because a tool is missing or parameters are wrong, do not switch to guessing. Go back to `mcpl search`, `mcpl list`, or `mcpl inspect --example`.

## Quick checklist

Before using an MCP tool in this configuration:

1. Make sure `mcpl` is installed.
2. Search or list tools before calling anything.
3. Inspect the tool if the parameters are not obvious.
4. Use the orchestrator for discovery.
5. Let the appropriate agent perform MCP-backed execution when needed.

If you keep discovery-first as your default, you will be using MCP the way this repository expects.
