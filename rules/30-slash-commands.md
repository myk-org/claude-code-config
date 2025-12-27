# Slash Command Execution - Strict Rules

🚨 **CRITICAL: Slash commands (`/command`) have SPECIAL execution rules**

## When a Slash Command is Invoked

1. **EXECUTE IT DIRECTLY YOURSELF** - NEVER delegate to any agent
2. **ALL internal operations run DIRECTLY** - scripts, bash commands, everything
3. **Slash command prompt takes FULL CONTROL** - its instructions override general CLAUDE.md rules
4. **General delegation rules are SUSPENDED** for the duration of the slash command

## Execution Mode Comparison

| Scenario | Normal Mode | During Slash Command |
|----------|-------------|---------------------|
| Run bash script | ❌ Delegate to bash-expert | ✅ Run directly |
| Execute git command | ❌ Delegate to git-expert | ✅ Run directly |
| Any shell command | ❌ Delegate to specialist | ✅ Run directly |

## Why These Rules Exist

- Slash commands define their OWN workflow and agent routing
- The slash command prompt specifies exactly when/how to use agents
- Delegating the slash command itself breaks its internal logic
- The orchestrator must maintain control to follow the slash command's phases

## Enforcement

❌ **VIOLATION**: `/mycommand` → delegate to agent → agent runs the prompt
✅ **CORRECT**: `/mycommand` → orchestrator executes prompt directly → follows its internal rules

**If a slash command's internal instructions say to use an agent, THEN use an agent. Otherwise, do it directly.**
