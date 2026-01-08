# Agent Routing

## Routing Table

| Domain/Tool | Agent |
|-------------|-------|
| **Languages (by file type)** | |
| Python (.py) | `python-expert` |
| Go (.go) | `go-expert` |
| Java (.java) | `java-expert` |
| Frontend (JS/TS/React/Vue) | `frontend-expert` |
| Shell scripts (.sh) | `bash-expert` |
| Markdown (.md) | `technical-documentation-writer` |
| **Infrastructure** | |
| Docker | `docker-expert` |
| Kubernetes/OpenShift | `kubernetes-expert` |
| Jenkins/CI/Groovy | `jenkins-expert` |
| **Development** | |
| Git operations (local) | `git-expert` |
| GitHub (PRs, issues, releases, workflows) | `github-expert` |
| Tests | `test-automator` |
| Debugging | `debugger` |
| API docs | `api-documenter` |
| Claude Code docs (features, hooks, settings, commands, MCP, IDE, Agent SDK, Claude API) | `claude-code-guide` (built-in) |
| External library/framework docs (React, FastAPI, Django, etc.) | `docs-fetcher` |
| **MCP Tools** | |
| `mcp__chrome-devtools__*` | `chrome-devtool-manager` |
| `mcp__github-metrics__*` | `github-metrics-manager` |
| `mcp__github-webhook-logs-*__*` | `webhook-logs-manager` |
| `mcp__graphiti-memory__*` | `graphiti-memory-manager` |
| `mcp__openshift-python-wrapper__*` | `openshift-manager` |

### Built-in vs Custom Agents

**Built-in agents** are provided by Claude Code itself and do NOT require definition files in `agents/`:
- `claude-code-guide` - Has current Claude Code documentation built into Claude Code

**Custom agents** are defined in this repository's `agents/` directory and require definition files:
- All other agents in the routing table above (e.g., `python-expert`, `docs-fetcher`, `git-expert`)

## Routing by Intent, Not Tool

**Important:** Route based on the task intent, not just the tool being used.

Examples:
- Running Python tests? → `python-expert` (not bash-expert)
- Editing Python files? → `python-expert` (even with sed/awk)
- Shell script creation? → `bash-expert`
- Creating a PR? → `github-expert` (not git-expert)
- Committing changes? → `git-expert` (local git)
- Viewing GitHub issue? → `github-expert`
- Claude Code hooks question? → `claude-code-guide` (not docs-fetcher)
- React documentation? → `docs-fetcher` (not claude-code-guide)

## Documentation Routing (MANDATORY)

### Two Documentation Agents

| Documentation Type | Agent | Notes |
|--------------------|-------|-------|
| Claude Code, Agent SDK, Claude API | `claude-code-guide` | Built-in agent (no definition file needed) |
| External libraries/frameworks | `docs-fetcher` | Custom agent (defined in `agents/docs-fetcher.md`) |

### claude-code-guide (Built-in)

> **Note:** `claude-code-guide` is a **built-in Claude Code agent** provided by Claude Code itself.
> It does NOT have a definition file in the `agents/` directory - it is part of Claude Code's core functionality.
> This is different from custom agents like `docs-fetcher` which require definition files.

**Use for Claude Code ecosystem documentation:**
- Claude Code features, hooks, settings
- Slash commands and custom commands
- MCP server configuration
- IDE integrations (VS Code, JetBrains)
- Agent SDK usage
- Claude API reference

**This is a built-in agent** - no definition file needed, no web fetching required, has current documentation.

### docs-fetcher (External Docs)

**Use for external library/framework documentation:**
- React, Vue, Angular, FastAPI, Django, etc.
- Third-party tools (Oh My Posh, Starship, etc.)
- Any documentation not part of Claude Code ecosystem

### Rule: NEVER Fetch Docs Directly

**The orchestrator MUST NEVER fetch documentation directly.**

❌ **FORBIDDEN** - Orchestrator using WebFetch for external docs:
```text
WebFetch(https://react.dev/...)
WebFetch(https://fastapi.tiangolo.com/...)
WebFetch(https://ohmyposh.dev/...)
```

✅ **REQUIRED** - Delegate to the appropriate agent:
```text
# For Claude Code docs:
Task(subagent_type="claude-code-guide", prompt="How do I configure hooks in Claude Code?")

# For external library docs:
Task(subagent_type="docs-fetcher", prompt="Fetch Oh My Posh configuration docs...")
```

### Why This Matters

- `claude-code-guide` has built-in, current Claude Code documentation
- `docs-fetcher` tries `llms.txt` first (optimized for LLMs)
- `docs-fetcher` extracts only relevant sections
- Direct WebFetch wastes tokens on full HTML pages

### When to Spawn Each Agent

**Use `claude-code-guide` when:**
- Questions about Claude Code features or configuration
- How to use hooks, settings.json, slash commands
- MCP server setup for Claude Code
- Agent SDK or Claude API usage
- IDE integration questions

**Use `docs-fetcher` when:**
- Fetching library/framework documentation (React, FastAPI, Django, etc.)
- Looking up configuration guides for external tools
- Getting API references for third-party services
- User asks about external tool documentation

**Exceptions - Skip both when:**
- Standard library only (no external dependencies)
- User explicitly says "skip docs" or "I know the API"
- Simple operations with obvious patterns
- Already fetched docs in current conversation

### Workflow

```text
Need documentation?
       ↓
  Is it Claude Code / Agent SDK / Claude API?
       │
   ┌───┴───┐
  YES      NO
   │        │
   ↓        ↓
┌──────────────────┐  ┌──────────────────┐
│ claude-code-guide │  │   docs-fetcher   │
│   (built-in)      │  │  (web fetching)  │
└──────────────────┘  └──────────────────┘
       │                      │
       └──────────┬───────────┘
                  ↓
       Use context for implementation
```

## Fallback

**Fallback:** No specialist? → `general-purpose` agent
