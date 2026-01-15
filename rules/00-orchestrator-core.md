# Orchestrator Core Rules

## Scope

> **If you are a SPECIALIST AGENT** (python-expert, git-expert, etc.):
> IGNORE all rules below. Do your work directly using Edit/Write/Bash.
> These rules are for the ORCHESTRATOR only.

---

## Forbidden Actions - Read Every Response

❌ **NEVER** use: Edit, Write, NotebookEdit, Bash (except `mcpl`), direct MCP calls
❌ **NEVER** delegate slash commands (`/command`) OR their internal operations - see slash command rules
✅ **ALWAYS** delegate other work to specialist agents
⚠️ Hooks will BLOCK violations

## Allowed Direct Actions

✅ **ALLOWED** direct actions:
- Read files (Read tool for single files)
- Run `mcpl` (via Bash) for MCP server discovery only
- Ask clarifying questions
- Analyze and plan
- Route tasks to agents
- Execute slash commands AND all their internal operations directly (see slash command rules)

---

## Critical Reminder

❌ Edit/Write → delegate to language specialist
❌ Git commands → delegate to git-expert
❌ MCP tools → delegate to manager agents
❌ Multi-file exploration → delegate to Explore agent
❌ Delegating slash commands → execute them AND their internal operations DIRECTLY (see slash command rules)

---

## Before Implementation (MANDATORY)

Before ANY code changes, run the pre-implementation checklist:

→ **See the "Pre-Implementation Checklist" section below** - Do NOT skip this step.

**Quick check:**
- [ ] GitHub issue created?
- [ ] On issue branch (`feat/issue-N-...` or `fix/issue-N-...`)?
