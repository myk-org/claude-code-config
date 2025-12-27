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

## Fallback

**Fallback:** No specialist? → `general-purpose` agent
