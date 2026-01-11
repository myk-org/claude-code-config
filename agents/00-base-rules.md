# Agent Base Rules

> **ALL AGENTS must follow these rules.** These are shared guidelines that apply to every specialist agent in this repository.

---

## Git Command Rules

### NEVER USE `git -C` (STRICT RULE)

When running git commands:

🚨 **YOU ARE ALREADY IN THE REPOSITORY. RUN GIT COMMANDS DIRECTLY.**

```bash
# ✅ CORRECT - Run directly in current directory
git status
git diff
git log --oneline -10
git show HEAD

# ❌ FORBIDDEN - Never use -C for current repository
git -C /path/to/repo status
git -C . diff
git -C "$PWD" log
```

**The `-C` flag is FORBIDDEN unless:**
1. The orchestrator **EXPLICITLY** asks you to operate on an external repository
2. The repository is at a **DIFFERENT PATH** than the current working directory (e.g., `/tmp/claude/some-other-repo`)

**If no external repository is mentioned, NEVER use `-C`.**

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
