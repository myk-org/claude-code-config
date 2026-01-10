# MCP Server Access

MCP (Model Context Protocol) servers provide access to external tools and data sources. Access is via the `mcp-cli` command.

---

## mcp-cli Commands

| Command | Purpose |
|---------|---------|
| `mcp-cli` | List all available servers and tools |
| `mcp-cli <server>` | Show server's tools with parameters |
| `mcp-cli <server>/<tool>` | Get full JSON schema for a tool |
| `mcp-cli <server>/<tool> '<json>'` | Execute tool with arguments |
| `mcp-cli grep "<pattern>"` | Search tools by name |

### Workflow

1. **Discover**: `mcp-cli` → see what servers exist
2. **Explore**: `mcp-cli <server>` → see available tools
3. **Inspect**: `mcp-cli <server>/<tool>` → get input schema
4. **Execute**: `mcp-cli <server>/<tool> '<json>'` → call the tool

### Options

| Flag | Purpose |
|------|---------|
| `-d` | Include descriptions (verbose) |
| `-j, --json` | JSON output for scripting |
| `-r, --raw` | Raw text content |

### Rules

- Run `mcp-cli` first to discover what's available
- Check schema before calling unknown tools
- Quote JSON arguments with single quotes
- Use heredoc for complex JSON:
  ```bash
  mcp-cli server/tool - <<EOF
  {"content": "Text with 'quotes'"}
  EOF
  ```

---

## For Orchestrator

- Use `mcp-cli` for discovery (list servers, explore tools)
- Delegate actual MCP tool execution to agents
- When delegating, tell agents that MCP servers are available via `mcp-cli`

## For Agents

- Use the full mcp-cli workflow above
- Execute tools as needed for your task
