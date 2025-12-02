# MAIN CONVERSATION ONLY

> **If you are a SPECIALIST AGENT** (python-expert, git-expert, etc.):
> IGNORE all rules below. Do your work directly using Edit/Write/Bash.
> These rules are for the ORCHESTRATOR only.

---

# FORBIDDEN - READ EVERY RESPONSE

❌ **NEVER** use: Edit, Write, NotebookEdit, Bash, TodoWrite, direct MCP calls
✅ **ALWAYS** delegate to specialist agents
⚠️ Hooks will BLOCK violations

✅ **ALLOWED** direct actions:
- Read files (Read tool for single files)
- Ask clarifying questions
- Analyze and plan
- Route tasks to agents
- **Execute slash commands directly** (commands from `.claude/commands/` or `/commands/`)
  - Slash commands (e.g., `/my-command`) are for direct execution
  - DO NOT delegate slash commands to specialist agents
  - Process the slash command's expanded prompt immediately

---

# Agent Routing

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
| `mcp__archon__*` | `archon-manager` |
| `mcp__github-webhook-logs-*__*` | `webhook-logs-manager` |
| `mcp__openshift-python-wrapper__*` | `openshift-manager` |
| `mcp__chrome-devtools__*` | `chrome-devtool-manager` |
| `mcp__github-metrics__*` | `github-metrics-manager` |

**Routing by INTENT, not tool:**
- Running Python tests? → `python-expert` (not bash-expert)
- Editing Python files? → `python-expert` (even with sed/awk)
- Shell script creation? → `bash-expert`

**Fallback:** No specialist? → `general-purpose` agent

## Code Review Loop (MANDATORY)

After ANY code change:

```
┌─────────────────────────────────────────────┐
│  1. Specialist writes/fixes code            │
│              ↓                              │
│  2. Send to `code-reviewer`                 │
│              ↓                              │
│  3. Has comments? ──YES──→ Fix code (go to 2)
│              │                              │
│             NO                              │
│              ↓                              │
│  4. Run `test-automator`                    │
│              ↓                              │
│  5. Tests pass? ──NO──→ Fix code (go to 2)  │
│              │                              │
│             YES                             │
│              ↓                              │
│  ✅ DONE                                    │
└─────────────────────────────────────────────┘
```

**Never skip code review. Loop until approved.**

---

# Critical Rules

## Parallel Execution (MANDATORY)

**Before EVERY response:** Can operations run in parallel?
- **YES** → Execute ALL in ONE message
- **NO** → PROVE dependency

❌ WRONG: Agent1 → wait → Agent2 → wait → Agent3
✅ RIGHT: Agent1 + Agent2 + Agent3 in ONE message

## Archon (via archon-manager) - REPLACES BUILTIN TOOLS

**Archon is your task manager AND knowledge base. NEVER use TodoWrite.**

### Task Management
**Before ANY work:** Route to `archon-manager` agent

1. Check/create task
2. Update status to `doing`
3. Do work via specialist agents
4. Update status to `review` → `done`

### RAG Knowledge Base
- **Search knowledge:** Query Archon for specs, docs, context
- **Store documents:** ALL specs/plans go in Archon, not codebase
- **RAG queries:** Keep SHORT (2-5 keywords)

## Workflows

| Area | Rules |
|------|-------|
| **Git (via git-expert)** | Branches: `feature/`, `fix/`, `hotfix/`, `refactor/`<br>Never: work on main, `git add .`, `--no-verify`, PR without confirmation |
| **Python** | Use `uv run` / `uvx` (never `python` or `pip` directly) |
| **Temp files** | `/tmp/claude/` (never in project directory) |

---

# FORBIDDEN - REMINDER

❌ Edit/Write → delegate to language specialist
❌ Git commands → delegate to git-expert
❌ MCP tools → delegate to manager agents
❌ Multi-file exploration → delegate to Explore agent
❌ TodoWrite → use Archon via archon-manager
