# Orchestrator Rules

`rules/` is the policy layer of `claude-code-config`. These files define how the orchestrator should behave: when to delegate work, when to create an issue first, how to choose the right specialist, how to use MCP tools, when slash commands override the normal rules, and how to report bugs in agent definitions.

For most users, the core idea is simple: the orchestrator manages work; specialists execute it. The rest of the rule set adds guardrails around that model.

> **Note:** The detailed policies live in `rules/*.md`, but the runtime behavior is implemented through `settings.json` hooks and the scripts in `scripts/`. Some rules are hard-enforced, while others are guidance the orchestrator is expected to follow.

## Rule Files At A Glance

| Rule file | Purpose |
|---|---|
| `rules/00-orchestrator-core.md` | Defines the orchestrator/specialist split and the default delegation model |
| `rules/05-issue-first-workflow.md` | Requires issue creation and issue branches before non-trivial implementation work |
| `rules/10-agent-routing.md` | Maps tasks to the right agent and clarifies built-in vs custom agents |
| `rules/15-mcp-launchpad.md` | Standardizes MCP discovery and tool execution through `mcpl` |
| `rules/20-code-review-loop.md` | Requires parallel code review and testing after changes |
| `rules/25-task-system.md` | Explains when to use persistent tasks and how to manage them |
| `rules/30-slash-commands.md` | Explains why slash commands run directly and temporarily suspend normal delegation rules |
| `rules/40-critical-rules.md` | Covers mandatory parallelism, temp files, `uv`, and external repo exploration |
| `rules/50-agent-bug-reporting.md` | Defines how to report bugs in custom agent instructions |

## How The Runtime Pieces Fit Together

The rule files are supported by Claude Code hooks in `settings.json`. Those hooks inject reminders, run startup checks, and block selected commands before they execute.

From `settings.json`:

```37:76:settings.json
    "PreToolUse": [
      {
        "matcher": "TodoWrite|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run ~/.claude/scripts/rule-enforcer.py"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run ~/.claude/scripts/git-protection.py"
          }
        ]
      }
      // ... prompt-based Bash safety hook omitted for brevity ...
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "uv run ~/.claude/scripts/rule-injector.py"
          }
        ]
      }
    ],
```

In everyday use, that means:

- `UserPromptSubmit` adds a reminder before the request is handled.
- `PreToolUse` runs `scripts/rule-enforcer.py` and `scripts/git-protection.py` on matching Bash activity.
- A separate prompt-based safety hook screens catastrophic shell commands.
- `SessionStart` runs `scripts/session-start-check.sh` to report missing prerequisites.

The injected reminder is currently a fixed string inside `scripts/rule-injector.py`:

```21:35:scripts/rule-injector.py
        rule_reminder = (
            "[SYSTEM RULES] You are a MANAGER. NEVER do work directly. ALWAYS delegate:\n"
            "- Edit/Write → language specialists (python-expert, go-expert, etc.)\n"
            "- ALL Bash commands → bash-expert or appropriate specialist\n"
            "- Git commands → git-expert\n"
            "- MCP tools → manager agents\n"
            "- Multi-file exploration → Explore agent\n"
            "HOOKS WILL BLOCK VIOLATIONS."
        )

        output = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": rule_reminder}}
```

> **Warning:** Editing a file in `rules/` does not automatically change that injected reminder. If you want the runtime reminder to change, update `scripts/rule-injector.py` as well.

The main hard block for Python and pre-commit commands is intentionally narrow:

```35:67:scripts/rule-enforcer.py
        # Block direct python/pip commands
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if is_forbidden_python_command(command):
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Direct python/pip commands are forbidden.",
                        "additionalContext": (
                            "You attempted to run python/pip directly. Instead:\n"
                            "1. Delegate Python tasks to the python-expert agent\n"
                            "2. Use 'uv run script.py' to run Python scripts\n"
                            "3. Use 'uvx package-name' to run package CLIs\n"
```

`scripts/git-protection.py` adds another layer by blocking `git commit` and `git push` on protected or already-merged branches.

> **Warning:** The Markdown rules are broader than the hard denials in `scripts/`. The code blocks some behaviors, but the full orchestration model still depends on the rule text, agent routing, and Claude Code permissions.

## Delegation Comes First

`rules/00-orchestrator-core.md` defines the operating model for the whole repository:

- The orchestrator reads, plans, asks questions, and routes work.
- Specialist agents do the direct editing, shell work, testing, and Git/GitHub operations in their own domain.
- Specialist agents explicitly ignore the orchestrator-only rules.
- The orchestrator may use `mcpl` directly for MCP discovery.
- Slash commands are a special execution mode and are handled separately.

This is the rule to keep in mind whenever a task could go more than one way. If the work involves editing files, running substantive shell commands, or using domain-specific tooling, it should usually go to the appropriate specialist.

## Issue-First Workflow

`rules/05-issue-first-workflow.md` adds a lightweight delivery process before non-trivial code changes.

Use it for:

- New features and enhancements
- Bug fixes that require code changes
- Refactors
- Multi-file changes
- Work that benefits from tracking and documentation

Skip it for:

- Tiny fixes
- Read-only questions or research
- Cases where the user explicitly says to do it directly
- Urgent hotfixes

The intended sequence is:

1. Create a GitHub issue through `github-expert`.
2. Ask whether the user wants to work on it now.
3. Create an issue branch from `origin/main`.
4. Complete the work and keep the issue updated.
5. Close the issue when the deliverables are done.

The branch naming rule is consistent and easy to scan: `feat/issue-<number>-<short-description>`, `fix/issue-<number>-<short-description>`, and similar variants for `refactor` and `docs`.

> **Tip:** This workflow is most useful when the work will take multiple steps or multiple files. For quick, obvious fixes, the rule deliberately allows you to skip it.

## Agent Routing

`rules/10-agent-routing.md` maps work to the right specialist and emphasizes a simple rule: route by intent, not by the tool being used.

A few examples from the routing table are especially important:

- Python work goes to `python-expert`.
- Frontend work goes to `frontend-expert`.
- Shell scripting goes to `bash-expert`.
- Local Git work goes to `git-expert`.
- GitHub issues, PRs, releases, and workflows go to `github-expert`.
- Markdown documentation goes to `technical-documentation-writer`.

The file also distinguishes between two kinds of documentation agents:

- `claude-code-guide` for Claude Code, hooks, settings, slash commands, MCP setup, Agent SDK, and Claude API docs
- `docs-fetcher` for external libraries and frameworks

> **Tip:** “Run Python tests” is still a Python task, even though a shell command may be involved. The routing rule prefers domain ownership over tool ownership.

> **Warning:** `rules/10-agent-routing.md` explicitly says the orchestrator should not fetch documentation directly. Use the appropriate documentation agent instead.

## MCP Discovery With `mcpl`

`rules/15-mcp-launchpad.md` standardizes MCP access around the `mcpl` CLI. The rule is clear: discover first, then inspect, then call.

From `rules/15-mcp-launchpad.md`:

```10:22:rules/15-mcp-launchpad.md
## mcpl Commands

| Command                                      | Purpose                                             |
|----------------------------------------------|-----------------------------------------------------|
| `mcpl search "<query>"`                      | Search all tools (shows required params, 5 results) |
| `mcpl search "<query>" --limit N`            | Search with more results                            |
| `mcpl list`                                  | List all MCP servers                                |
| `mcpl list <server>`                         | List tools for a server (shows required params)     |
| `mcpl inspect <server> <tool>`               | Get full schema                                     |
| `mcpl inspect <server> <tool> --example`     | Get schema + example call                           |
| `mcpl call <server> <tool> '{}'`             | Execute tool (no arguments)                         |
| `mcpl call <server> <tool> '{"param": "v"}'` | Execute tool with arguments                         |
| `mcpl verify`                                | Test all server connections                         |
```

In practice:

- The orchestrator uses `mcpl` for discovery.
- Agents use the full `mcpl` flow when they need to execute MCP tools.
- `mcpl verify` is the first troubleshooting step when a server is not responding.

## Tasks For Multi-Phase Work

`rules/25-task-system.md` makes task tracking explicit and practical.

Use tasks when work is:

- Multi-step
- Easy to interrupt
- Worth resuming later
- Organized into visible phases
- Waiting on user approval at checkpoints

Do not use tasks for:

- Simple one-off actions
- Trivial fixes
- Internal steps that the user does not need to track
- Agent-only work

Two details in this rule are especially user-friendly:

- Tasks persist on disk in `~/.claude/tasks/<session-uuid>/`, so they survive across sessions.
- Cleanup is mandatory. Before finishing a task-driven workflow, the orchestrator is expected to check for `pending` or `in_progress` tasks and close them out.

Naming is also standardized:

- `subject` should be short and imperative, such as `Run tests`.
- `activeForm` should read naturally in progress UIs, such as `Running tests`.

> **Tip:** Slash commands with multiple phases are one of the best places to use tasks. The rule file explicitly recommends them for workflows that involve dependencies, approvals, and cleanup.

## Slash Commands Override The Normal Rules

`rules/30-slash-commands.md` introduces the main exception to the normal delegation model.

When a slash command is invoked:

- The orchestrator executes the slash command directly.
- The slash command’s own instructions override the general orchestration rules for the duration of the command.
- Internal operations run directly unless the command itself says to use an agent.
- The slash command itself should never be delegated as a whole.

A concrete example is `plugins/myk-github/commands/review-handler.md`, which declares its own tool access in frontmatter:

```1:5:plugins/myk-github/commands/review-handler.md
---
description: Process ALL review sources (human, Qodo, CodeRabbit) from current PR
argument-hint: [--autorabbit] [REVIEW_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task, Agent
---
```

That frontmatter is why slash commands can run direct tool-based workflows that would normally be delegated in regular orchestrator mode.

> **Note:** If a slash command says to use an agent at a specific step, follow the slash command. The command prompt is in charge while that command is running.

## Critical Operational Rules

`rules/40-critical-rules.md` collects several cross-cutting rules that make the whole setup behave predictably.

### Parallelism

Parallel execution is mandatory whenever there is no real dependency between operations. The rule asks the orchestrator to check for parallelism before every response and to group independent work into one turn whenever possible.

This matters most for:

- Spawning multiple review agents
- Running independent lookups
- Handling unrelated subtasks at the same phase of a workflow

### Temp Files

Temporary files belong in `/tmp/claude/`, not in the project tree. This keeps the repo clean and avoids accidental commits of scratch files.

One concrete example appears in `plugins/myk-github/commands/pr-review.md`, which writes its review comment JSON to `/tmp/claude/pr-review-comments.json` before posting it.

> **Warning:** If a workflow needs scratch files, do not leave them in the repository directory. `rules/40-critical-rules.md` treats `/tmp/claude/` as the only safe default.

### Python Execution With `uv`

The rule file requires `uv` or `uvx` instead of direct `python`, `pip`, or `pre-commit` commands. That guidance is reinforced by `scripts/rule-enforcer.py`, which denies direct `python`/`pip`/`pre-commit` Bash commands and points users to `uv`, `uvx`, and `prek`.

### External Repository Exploration

When this configuration needs to inspect a different Git repository, `rules/40-critical-rules.md` prefers a shallow local clone into `/tmp/claude/` over browsing files through web fetches. The goal is speed, better file access, and fewer accidental project-directory side effects.

## Agent Bug Reporting

`rules/50-agent-bug-reporting.md` is specifically about bugs in the custom agent definitions shipped by this repository.

The workflow is intentionally cautious:

1. Confirm that the bug is in a custom agent from `agents/`, not in a built-in Claude Code agent, user code, or an external tool.
2. Ask the user whether to create a GitHub issue.
3. If the user says yes, delegate issue creation to `github-expert`.
4. Continue with the original task after the issue decision is handled.

The title format is standardized as `bug(agents): [agent-name] - brief description`.

This rule is not for routine coding bugs or runtime failures. It exists so the repository can improve its agent instructions when those instructions produce incorrect or misleading behavior.

> **Note:** Built-in Claude Code agents are explicitly out of scope for this rule. It only applies to custom agents defined in this repository.

## Related Review Rule

Although this page focuses on orchestration behavior, `rules/20-code-review-loop.md` sits alongside these rules and matters in day-to-day use.

After any code change, it requires:

- All three review agents to run in parallel
- Findings to be merged and deduplicated
- Tests to run after review is clean
- The loop to repeat until both review and tests pass

`scripts/session-start-check.sh` treats the three review plugins as critical prerequisites: `pr-review-toolkit`, `superpowers`, and `feature-dev`.

## Setup And Verification

This repository verifies the runtime pieces locally rather than through an in-repo GitHub Actions workflow.

A few practical points matter here:

- `scripts/session-start-check.sh` runs at session start and checks for tools such as `uv`, `gh`, `jq`, `gawk`, `prek`, and `mcpl`, plus required review plugins.
- The startup check is advisory, not blocking: it reports problems but exits successfully.
- `tests/test_rule_enforcer.py` and `tests/test_git_protection.py` cover the main enforcement hooks.
- `tox.toml` runs the test suite through `uv`.

From `tox.toml`:

```1:7:tox.toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

> **Warning:** No `.github/` workflow is present in this repository, so the rule and hook behavior shown here is validated through local hooks and local tests, not an in-repo CI pipeline.

> **Tip:** If setup problems appear at session start, install `uv` first. It is the foundation for the Python-based hooks and the local test runner.

## If You Extend This Configuration

Two repository conventions are easy to miss:

- `rules/`, `scripts/`, `agents/`, and `plugins/` are tracked through a whitelist-style `.gitignore`. New shared files in those directories must be whitelisted there or they will remain ignored.
- New hook scripts should be added to both `permissions.allow` and `allowedTools` in `settings.json`.

That keeps the orchestrator rules understandable at the policy level and predictable at runtime.
