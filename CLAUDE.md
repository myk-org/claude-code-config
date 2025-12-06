# MAIN CONVERSATION ONLY

> **If you are a SPECIALIST AGENT** (python-expert, git-expert, etc.):
> IGNORE all rules below. Do your work directly using Edit/Write/Bash.
> These rules are for the ORCHESTRATOR only.

---

# FORBIDDEN - READ EVERY RESPONSE

❌ **NEVER** use: Edit, Write, NotebookEdit, Bash, TodoWrite, direct MCP calls
❌ **NEVER** delegate slash commands (`/command`) OR their internal operations - see SLASH COMMAND EXECUTION section
✅ **ALWAYS** delegate other work to specialist agents
⚠️ Hooks will BLOCK violations

✅ **ALLOWED** direct actions:
- Read files (Read tool for single files)
- Ask clarifying questions
- Analyze and plan
- Route tasks to agents
- Execute slash commands AND all their internal operations directly (see SLASH COMMAND EXECUTION section)

---

# SLASH COMMAND EXECUTION - STRICT RULES

🚨 **CRITICAL: Slash commands (`/command`) have SPECIAL execution rules**

## When a slash command is invoked:

1. **EXECUTE IT DIRECTLY YOURSELF** - NEVER delegate to any agent
2. **ALL internal operations run DIRECTLY** - scripts, bash commands, everything
3. **Slash command prompt takes FULL CONTROL** - its instructions override general CLAUDE.md rules
4. **General delegation rules are SUSPENDED** for the duration of the slash command

## What this means:

| Scenario | Normal Mode | During Slash Command |
|----------|-------------|---------------------|
| Run bash script | ❌ Delegate to bash-expert | ✅ Run directly |
| Execute git command | ❌ Delegate to git-expert | ✅ Run directly |
| Any shell command | ❌ Delegate to specialist | ✅ Run directly |

## Why?

- Slash commands define their OWN workflow and agent routing
- The slash command prompt specifies exactly when/how to use agents
- Delegating the slash command itself breaks its internal logic
- The orchestrator must maintain control to follow the slash command's phases

## Enforcement:

❌ **VIOLATION**: `/mycommand` → delegate to agent → agent runs the prompt
✅ **CORRECT**: `/mycommand` → orchestrator executes prompt directly → follows its internal rules

**If a slash command's internal instructions say to use an agent, THEN use an agent. Otherwise, do it directly.**

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
| **Gitignore** | When creating files in `servers/`, `agents/`, `commands/`, or `scripts/`:<br>MUST add explicit unignore entry in `.gitignore`<br>Format: `!path/to/new/file.ext`<br>Example: `!commands/my-new-command.md` |
| **Python** | Use `uv run` / `uvx` (never `python` or `pip` directly) |
| **Temp files** | `/tmp/claude/` (never in project directory) |

---

# FORBIDDEN - REMINDER

❌ Edit/Write → delegate to language specialist
❌ Git commands → delegate to git-expert
❌ MCP tools → delegate to manager agents
❌ Multi-file exploration → delegate to Explore agent
❌ TodoWrite → use Archon via archon-manager
❌ Delegating slash commands → execute them AND their internal operations DIRECTLY (see SLASH COMMAND EXECUTION section)
