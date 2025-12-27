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
| Git operations | `git-expert` |
| Tests | `test-automator` |
| Debugging | `debugger` |
| API docs | `api-documenter` |
| Documentation fetching | `docs-fetcher` |
| **MCP Tools** |
| `mcp__github-webhook-logs-*__*` | `webhook-logs-manager` |
| `mcp__openshift-python-wrapper__*` | `openshift-manager` |
| `mcp__chrome-devtools__*` | `chrome-devtool-manager` |
| `mcp__github-metrics__*` | `github-metrics-manager` |

## Routing by Intent, Not Tool

**Important:** Route based on the task intent, not just the tool being used.

Examples:
- Running Python tests? → `python-expert` (not bash-expert)
- Editing Python files? → `python-expert` (even with sed/awk)
- Shell script creation? → `bash-expert`

## Documentation Fetching (MANDATORY)

BEFORE writing code that uses external libraries/frameworks:
1. SPAWN `docs-fetcher` agent to get current best practices
2. WAIT for docs context before implementing

**Triggers - MUST fetch docs when:**
- User mentions a framework by name (FastAPI, Django, React, Express, etc.)
- Task involves library-specific patterns (OAuth, WebSockets, ORM, etc.)
- You're unsure about current API or best practices
- Working with a library you haven't used recently in this conversation

**Exceptions - Skip docs fetching when:**
- Standard library only (no external dependencies)
- User explicitly says "skip docs" or "I know the API"
- Simple operations with obvious patterns
- Already fetched docs for this library in current conversation

## Fallback

**Fallback:** No specialist? → `general-purpose` agent
