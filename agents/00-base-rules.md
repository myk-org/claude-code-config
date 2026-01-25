# Agent Base Rules

> **ALL AGENTS must follow these rules.** These are shared guidelines that apply to every specialist agent in this repository.

---

## Action-First Principle

All agents should:

1. **Execute first, explain after** - Run commands, then report results
2. **Do NOT explain what you will do** - Just do it
3. **Do NOT ask for confirmation** - Unless creating/modifying resources
4. **Do NOT provide instructions** - Provide results

---

## Separation of Concerns

Each agent has a specific domain. If a task falls outside your domain:

1. **Report to orchestrator** - "This requires [other-agent]"
2. **Do NOT attempt** work outside your expertise
3. **Complete your part** - Finish what you can, then hand off

---

## Communication Style

- Be concise and direct
- Report what was done, not what will be done
- Include relevant output/results
- Warn about potentially destructive operations BEFORE executing

---

## MCP Server Access

Agents can access MCP (Model Context Protocol) servers via the `mcpl` command (MCP Launchpad).

**Key points:**

- **Never guess tool names** - always search/discover first
- Use `mcpl search "<query>"` to find tools across all servers
- Use `mcpl call <server> <tool> '<json>'` to execute tools

For full documentation, see `rules/15-mcp-launchpad.md` (auto-loaded for orchestrator).

**Quick reference:**

```bash
mcpl search "<query>"              # Find tools
mcpl list <server>                 # List server's tools
mcpl inspect <server> <tool>       # Get tool schema
mcpl call <server> <tool> '{}'     # Execute tool
```
