# Claude Code Config

Pre-configured Claude Code setup with specialized agents and workflow automation.

## Requirements

- [uv](https://docs.astral.sh/uv/) - Fast Python package manager (used for running hook scripts)

## Quick Start

```bash
git clone https://github.com/myk-org/claude-code-config ~/.claude
```

## What's Included

- **23 specialized agents** for different domains (Python, Go, Java, Docker, Kubernetes, Git, etc.)
- **Orchestrator pattern** with automatic agent routing via CLAUDE.md
- **Pre-commit hooks** for rule enforcement
- **Status line** integration

## Agents

| Agent | Purpose |
|-------|---------|
| `python-expert` | Python development, testing, async patterns |
| `go-expert` | Go development, goroutines, modules |
| `java-expert` | Java/Spring Boot development |
| `frontend-expert` | JS/TS/React/Vue/Angular |
| `bash-expert` | Shell scripting and automation |
| `docker-expert` | Dockerfile, container orchestration |
| `kubernetes-expert` | K8s/OpenShift, Helm, GitOps |
| `jenkins-expert` | CI/CD pipelines, Jenkinsfiles |
| `git-expert` | Git operations, branching strategies |
| `test-automator` | Test suites, CI pipelines |
| `debugger` | Error analysis, debugging |
| `code-reviewer` | Code quality, security review |
| `technical-documentation-writer` | Documentation |
| `api-documenter` | OpenAPI/Swagger specs |
| `general-purpose` | Fallback for unspecified tasks |

## MCP Servers

The `.claude/servers/` directory contains MCP (Model Context Protocol) server implementations.

### Code Execution Server

Located at `.claude/servers/code-execution/`, this server wraps MCP connections through a **code execution layer** using UTCP.

**Why not connect MCP servers directly?**

| Approach | API Calls | Flexibility | Performance |
|----------|-----------|-------------|-------------|
| **Direct MCP** | 1 call per tool | Single tool per request | Many round-trips |
| **Code Execution** | 1 call for entire workflow | Chain tools with TypeScript | Single round-trip |

**Key advantages:**

1. **Tool Chaining in One Call**
   ```typescript
   // Direct MCP: 3 separate API calls
   // Code Execution: 1 call with this code:
   const repos = await github.listRepos();
   const metrics = await Promise.all(
     repos.map(r => github.getMetrics(r.id))
   );
   return summarize(metrics);
   ```

2. **Custom Logic Between Tools**
   - Conditional branching based on results
   - Loops and iterations
   - Data transformation and filtering
   - Error handling and retries

3. **Reduced Token Usage**
   - One tool call instead of many
   - Results aggregated before returning
   - No intermediate results in conversation

4. **Better Performance**
   - Single round-trip to API
   - Parallel execution with Promise.all
   - No waiting for Claude to process each step

**Setup:**
```bash
cd ~/.claude/servers/code-execution
npm install
```

### Adding Server Configs

1. Create a config file in `.claude/servers/code-execution/configs/`:

```json
{
  "manual_call_templates": [
    {
      "name": "my-service",
      "call_template_type": "mcp",
      "config": {
        "mcpServers": {
          "my-server": {
            "transport": "http",
            "url": "http://localhost:8080/mcp"
          }
        }
      }
    }
  ],
  "tool_repository": {
    "tool_repository_type": "in_memory"
  },
  "tool_search_strategy": {
    "tool_search_strategy_type": "tag_and_description_word_match"
  }
}
```

2. Add the MCP server to Claude by editing `~/.claude.json`:

```json
{
  "mcpServers": {
    "my-service": {
      "command": "npx",
      "args": ["@utcp/code-mode-mcp"],
      "env": {
        "UTCP_CONFIG_FILE": "~/.claude/servers/code-execution/configs/my-service.json"
      }
    }
  }
}
```

3. Restart Claude Code for the changes to take effect.

See `configs/example.json.example` for a config template.

### Creating an Agent for Your MCP Server

After adding an MCP server, you'll want a specialized agent to manage it. Ask Claude to create one:

**Example prompt:**
```
Create an agent for my new MCP server called "my-service" that handles [describe what your server does].
The agent should be saved to ~/.claude/agents/my-service-manager.md
```

**Agent file structure:**
```markdown
---
name: my-service-manager
description: Use this agent for [your MCP server purpose]
---

You are a specialist agent for managing the my-service MCP server...

## Available Tools
- mcp__my-service__tool_name
- ...
```

The agent will be automatically available in Claude Code after creation.

## Why Agent-Based Workflow?

This configuration implements an **orchestrator pattern** where Claude acts as a manager delegating to specialist agents. Here's why:

### Context Preservation
- **Main conversation stays lean** - The orchestrator only tracks high-level progress
- **Specialists work in isolation** - Each agent handles its task without bloating the main context
- **Parallel execution** - Multiple agents can work simultaneously on independent tasks

### Expertise Separation
- **Domain knowledge** - Each agent has specialized instructions for its domain (Python best practices, Git workflows, Docker patterns)
- **Tool restrictions** - Agents only use tools relevant to their specialty
- **Consistent patterns** - Same agent = same coding style and conventions

### Quality Assurance
- **Mandatory code review** - Every code change goes through `code-reviewer`
- **Automated testing** - `test-automator` runs after changes
- **Review loop** - Changes iterate until approved

### Workflow Example

```
User: "Add a new feature to handle user auth"
         │
         ▼
   ┌─────────────────┐
   │  ORCHESTRATOR   │  (main Claude - manages, doesn't code)
   └────────┬────────┘
            │
   ┌────────┼────────────────┐
   │        │                │
   ▼        ▼                ▼
┌──────┐ ┌──────┐      ┌──────────┐
│python│ │ git  │      │test-auto │
│expert│ │expert│      │  mator   │
└──────┘ └──────┘      └──────────┘
   │        │                │
   └────────┴────────────────┘
            │
            ▼
    ┌──────────────┐
    │code-reviewer │
    └──────────────┘
            │
            ▼
       ✅ Done
```

### Benefits
- **Reduced token usage** - Specialist context is discarded after task completion
- **Better code quality** - Domain experts produce better code
- **Faster execution** - Parallel agents vs sequential operations
- **Maintainability** - Easy to add/modify agents for new domains

## How It Works

The `CLAUDE.md` file defines an orchestrator pattern where:

1. The main Claude instance acts as a **manager/orchestrator**
2. It delegates tasks to **specialist agents** based on the domain
3. After code changes, automatic **code review** and **test** loops run

## Customization

- **Edit `CLAUDE.md`** to customize orchestrator rules and agent routing
- **Edit `.claude/settings.json`** to modify hooks and allowed tools
- **Edit agents in `.claude/agents/`** to customize agent behavior

## File Structure

```
~/.claude/
├── agents/           # Specialist agent definitions
├── scripts/          # Helper scripts for hooks
├── settings.json     # Hooks and tool permissions
└── statusline.sh     # Status line script
```

## License

MIT
