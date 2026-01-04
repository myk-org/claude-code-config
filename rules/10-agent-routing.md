# Agent Routing

## Routing Table

| Domain/Tool | Agent |
|-------------|-------|
| **Languages (by file type)** |
| Python (.py) | `python-expert` |
| Go (.go) | `go-expert` |
| Java (.java) | `java-expert` |
| Frontend (JS/TS/React/Vue) | `frontend-expert` |
| Shell scripts (.sh) | `bash-expert` |
| Markdown (.md) | `technical-documentation-writer` |
| **Infrastructure** |
| Docker | `docker-expert` |
| Kubernetes/OpenShift | `kubernetes-expert` |
| Jenkins/CI/Groovy | `jenkins-expert` |
| **Development** |
| Git operations (local) | `git-expert` |
| GitHub (PRs, issues, releases, workflows) | `github-expert` |
| Tests | `test-automator` |
| Debugging | `debugger` |
| API docs | `api-documenter` |
| Documentation fetching | `docs-fetcher` |
| **MCP Tools** |
| `mcp__chrome-devtools__*` | `chrome-devtool-manager` |
| `mcp__github-metrics__*` | `github-metrics-manager` |
| `mcp__github-webhook-logs-*__*` | `webhook-logs-manager` |
| `mcp__graphiti-memory__*` | `graphiti-memory-manager` |
| `mcp__openshift-python-wrapper__*` | `openshift-manager` |

## Routing by Intent, Not Tool

**Important:** Route based on the task intent, not just the tool being used.

Examples:
- Running Python tests? → `python-expert` (not bash-expert)
- Editing Python files? → `python-expert` (even with sed/awk)
- Shell script creation? → `bash-expert`
- Creating a PR? → `github-expert` (not git-expert)
- Committing changes? → `git-expert` (local git)
- Viewing GitHub issue? → `github-expert`

## Documentation Fetching (MANDATORY)

### Rule: NEVER Fetch Docs Directly

**The orchestrator MUST delegate ALL documentation fetching to `docs-fetcher` agent.**

❌ **FORBIDDEN** - Orchestrator using WebFetch for external docs:
```
WebFetch(https://react.dev/...)
WebFetch(https://fastapi.tiangolo.com/...)
WebFetch(https://ohmyposh.dev/...)
```

✅ **REQUIRED** - Delegate to docs-fetcher:
```
Task(subagent_type="docs-fetcher", prompt="Fetch Oh My Posh configuration docs...")
```

### Why This Matters

- docs-fetcher tries `llms.txt` first (optimized for LLMs)
- docs-fetcher extracts only relevant sections
- docs-fetcher provides structured, actionable output
- Direct WebFetch wastes tokens on full HTML pages

### When to Spawn docs-fetcher

**MUST delegate when:**
- Fetching library/framework documentation (React, FastAPI, Django, etc.)
- Looking up configuration guides (Oh My Posh, Starship, etc.)
- Getting API references or usage examples
- User asks about external tool documentation
- You need current best practices for a library

**Exceptions - Skip docs-fetcher when:**
- Standard library only (no external dependencies)
- User explicitly says "skip docs" or "I know the API"
- Simple operations with obvious patterns
- Already fetched docs for this library in current conversation

### Workflow

```
Need external docs?
       ↓
  ┌────────────────────────────────────┐
  │  DELEGATE to docs-fetcher agent    │
  │  DO NOT use WebFetch directly      │
  └────────────────────────────────────┘
       ↓
Wait for structured response
       ↓
Use context for implementation
```

## Fallback

**Fallback:** No specialist? → `general-purpose` agent
