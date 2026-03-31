# Architecture

`claude-code-config` is built around one core separation: the main Claude instance orchestrates, and specialist agents execute. The orchestrator reads the request, chooses the workflow, routes work to the right expert, and keeps the overall process moving. Specialists handle the hands-on work in focused domains such as Python, Git, frontend, testing, or documentation.

That split is what makes the repository predictable. It keeps the top-level conversation focused, makes parallel work practical, and gives the project a clear place to enforce safety rules, task tracking, and the required review loop.

## At A Glance

| Layer | Purpose |
| --- | --- |
| Orchestrator | Read the request, ask questions, plan, route work, and run slash commands |
| Specialist agents | Do the actual implementation work in their domain |
| Slash commands | Run end-to-end workflows that can temporarily override normal delegation |
| Hooks and permissions | Enforce safety rules around Bash, Git, and tool usage |
| Tasks | Track long, multi-step workflows across phases and sessions |
| Review loop | Require parallel review and testing after code changes |

## Orchestrator vs Specialist

The orchestrator is intentionally narrow. It is supposed to coordinate, not do hands-on implementation. Specialists are the execution layer.

```md
> **If you are a SPECIALIST AGENT** (python-expert, git-expert, etc.):
> IGNORE all rules below. Do your work directly using Edit/Write/Bash.
> These rules are for the ORCHESTRATOR only.

❌ **NEVER** use: Edit, Write, NotebookEdit, Bash (except `mcpl`), direct MCP calls
❌ **NEVER** delegate slash commands (`/command`) OR their internal operations - see slash command rules
✅ **ALWAYS** delegate other work to specialist agents
```

In day-to-day use, that means the orchestrator should do things like:

- read files and gather context
- ask clarifying questions
- analyze and plan
- choose the right specialist
- coordinate multi-step workflows
- execute slash commands directly

Work is routed by intent, not just by the tool involved. A few examples from `rules/10-agent-routing.md`:

- Python work goes to `python-expert`
- local Git work goes to `git-expert`
- GitHub PRs, issues, and releases go to `github-expert`
- Markdown work goes to `technical-documentation-writer`
- tests go to `test-automator`

The same routing file also distinguishes between built-in agents such as `claude-code-guide` and `general-purpose`, and custom agents defined in `agents/`.

> **Note:** The split is deliberate. The orchestrator keeps the big picture. Specialists keep the domain-specific context.

## Slash Commands Run In A Different Mode

Slash commands are the biggest exception to the normal delegation model. In normal mode, the orchestrator should delegate implementation work. During a slash command, the orchestrator runs the command itself and follows that command's own instructions from start to finish.

```md
1. **EXECUTE IT DIRECTLY YOURSELF** - NEVER delegate to any agent
2. **ALL internal operations run DIRECTLY** - scripts, bash commands, everything
3. **Slash command prompt takes FULL CONTROL** - its instructions override general CLAUDE.md rules
4. **General delegation rules are SUSPENDED** for the duration of the slash command
```

> **Warning:** Slash commands are not just shortcuts. They temporarily change how execution works.

You can see that direct-execution model in the command definitions themselves. For example, `plugins/myk-github/commands/review-handler.md` explicitly declares the tools it may use:

```md
---
description: Process ALL review sources (human, Qodo, CodeRabbit) from current PR
argument-hint: [--autorabbit] [REVIEW_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task, Agent
---
```

That is why commands such as `/myk-github:review-handler` and `/myk-github:pr-review` can directly use `git`, `gh`, `uv`, `Task`, and `myk-claude-tools` while they run. The command definition becomes the active workflow.

Several slash commands are powered by the local `myk-claude-tools` package. In `myk_claude_tools/cli.py`, the CLI registers `coderabbit`, `db`, `pr`, `release`, and `reviews` command groups, which the plugin commands then call.

> **Tip:** Temporary working files belong in `/tmp/claude`. That rule appears in `rules/40-critical-rules.md`, and the CLI commands follow the same pattern when they write JSON artifacts.

## Enforcement Is Layered

The project does not rely on a single enforcement mechanism. Instead, it uses three layers together:

1. human-readable rules in `rules/`
2. runtime configuration in `settings.json`
3. hook scripts in `scripts/`

### Prompt-Time Guidance

On every user prompt, `scripts/rule-injector.py` injects a short reminder that keeps the orchestrator in manager mode:

```python
rule_reminder = (
    "[SYSTEM RULES] You are a MANAGER. NEVER do work directly. ALWAYS delegate:\n"
    "- Edit/Write → language specialists (python-expert, go-expert, etc.)\n"
    "- ALL Bash commands → bash-expert or appropriate specialist\n"
    "- Git commands → git-expert\n"
    "- MCP tools → manager agents\n"
    "- Multi-file exploration → Explore agent\n"
    "HOOKS WILL BLOCK VIOLATIONS."
)
```

This injected reminder is short on purpose. It reinforces the architecture at runtime without replacing the fuller policy described in `rules/`.

### Hook Registration And Allowlists

`settings.json` is where the runtime guardrails are wired together. It defines tool allowlists and registers the hooks that run before tools and prompts.

```json
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
]
```

The same file also scopes direct `Read`, `Edit`, and `Write` permissions to `/tmp/claude/**` and allowlists specific command prefixes such as `mcpl`, `git -C`, `myk-claude-tools`, and the hook scripts themselves.

It also includes a prompt-based Bash safety gate that asks for confirmation or blocks clearly destructive OS-level commands.

> **Tip:** `settings.json` includes a maintenance note saying hook scripts must be listed in both `permissions.allow` and `allowedTools`. If you add a new script-based hook, update both places.

### Bash Policy Enforcement

The most concrete checked-in shell enforcement lives in `scripts/rule-enforcer.py`. It blocks direct Python and `pip` usage, allows `uv` and `uvx`, and blocks raw `pre-commit` so the wrapper tool is used instead.

```python
# Allow uv/uvx commands
if cmd.startswith(("uv ", "uvx ")):
    return False

# Block direct python/pip
forbidden = ("python ", "python3 ", "pip ", "pip3 ")
return cmd.startswith(forbidden)
```

When it blocks a command, the script tells the user what to do instead:

- use `uv run` for Python execution
- use `uvx` for package CLIs
- use `prek` instead of raw `pre-commit`

The behavior is backed by `tests/test_rule_enforcer.py`, which includes explicit cases for allowed `uv run`, allowed `uvx`, allowed `prek`, and denied direct `python`, `pip`, and `pre-commit` commands.

### Git Protection

`scripts/git-protection.py` adds a stricter safety layer for version-control operations. It blocks `git commit` or `git push` when the branch is unsafe to use, including cases like:

- committing directly on `main` or `master`
- committing on a branch whose PR is already merged
- committing on a branch already merged into the main branch
- committing in detached HEAD state

The companion test suite in `tests/test_git_protection.py` covers those cases, along with GitHub PR detection via `gh`, amend behavior on unpushed commits, and edge cases around command parsing.

### Session Start Validation

Before work begins, `scripts/session-start-check.sh` checks whether critical tools are installed. Two items stand out:

- `uv` is treated as critical because the hook system depends on it
- the three review plugins are treated as critical because the review loop depends on them

The script makes that requirement explicit:

```bash
critical_marketplace_plugins=(
  pr-review-toolkit
  superpowers
  feature-dev
)
```

> **Warning:** `pr-review-toolkit`, `superpowers`, and `feature-dev` are not optional if you want the full architecture to work as designed. They are required for the mandatory review loop.

## Task Tracking Is For Real Workflows

The task system is not meant for every small action. It is there for workflows that are long enough, staged enough, or interruption-prone enough that progress should survive beyond the current turn.

`rules/25-task-system.md` defines tasks as persistent data on disk:

```md
Tasks are saved to disk and persist across sessions:

- **Location:** `~/.claude/tasks/<session-uuid>/`
- **Format:** Each task is a JSON file (1.json, 2.json, etc.)
- **Contents:** Full task structure including subject, description, status, blockedBy
```

The same rule file also shows the expected shape of a task:

```text
TaskCreate:
  - subject: "Run tests with coverage"
  - activeForm: "Running tests"
  - description: "Execute test suite and verify coverage thresholds"
```

This is an orchestrator feature, not an agent feature. The rules explicitly say tasks are useful for:

- complex work that might be interrupted
- multi-step workflows with visible progress
- approval gates
- slash commands with dependent phases

They also explicitly say tasks are **not** for:

- simple one-off actions
- agent work
- trivial fixes
- internal processing steps

> **Tip:** If a workflow has phases, dependencies, or a chance of waiting on the user, create tasks and connect them with `blockedBy`. If it is simple and immediate, skip the task system.

One more detail matters in practice: tasks must be cleaned up. The rules require a final `TaskList` and `TaskUpdate` pass so stale tasks do not linger between sessions. `plugins/myk-github/commands/review-handler.md` is called out as the reference example for a multi-phase task-aware workflow.

## The Review Loop Is Mandatory

This repository treats code review as part of the architecture, not as an optional follow-up step. After any code change, the required path is:

1. a specialist makes the change
2. three review agents run in parallel
3. findings are merged and deduplicated
4. any issues are fixed and re-reviewed
5. `test-automator` runs
6. only then is the work considered done

The core rule is written directly in `rules/20-code-review-loop.md`:

```text
1. Specialist writes/fixes code
2. Send to ALL 3 review agents IN PARALLEL:
   - `superpowers:code-reviewer`
   - `pr-review-toolkit:code-reviewer`
   - `feature-dev:code-reviewer`
3. Merge findings from all 3 reviewers
4. Has comments from ANY reviewer? ──YES──→ Fix code
5. Run `test-automator`
6. Tests pass? ──NO──→ Fix code
```

The same file also requires that all three reviewers be launched in the **same assistant turn**, not one after another.

Those reviewers have distinct responsibilities:

- `superpowers:code-reviewer` focuses on general code quality and maintainability
- `pr-review-toolkit:code-reviewer` checks project guidelines and style adherence
- `feature-dev:code-reviewer` focuses on bugs, logic errors, and security issues

This is not just a theory document. Plugin commands repeat the same architecture. For example, `plugins/myk-review/commands/local.md` and `plugins/myk-github/commands/pr-review.md` both state that the three reviewers must be invoked in parallel.

> **Warning:** The review loop is designed to repeat until reviewers are satisfied. A failing review does not end the workflow; it sends the work back around the loop.

### Testing And Local Quality Gates

The checked-in repository does not include a GitHub Actions workflow under `.github/workflows`. Instead, its quality gates are defined locally through hook scripts, `tox`, and pre-commit configuration.

`tox.toml` shows the expected unit-test entrypoint:

```toml
[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

`.pre-commit-config.yaml` adds additional local checks, including Ruff, Flake8, mypy, detect-secrets, gitleaks, and markdown linting.

> **Note:** In this repository, quality assurance is mostly enforced through local automation and command workflows rather than a checked-in CI pipeline definition.

## How The Pieces Fit Together

A typical end-to-end flow looks like this:

1. The orchestrator reads the request and decides whether it is normal delegated work or a slash-command workflow.
2. For normal work, it routes by intent to the best specialist.
3. For slash commands, it runs the command directly and follows that command's own rules.
4. Hook scripts and allowlists keep Bash, Git, and prompt behavior inside safe boundaries.
5. If the workflow is long or multi-phase, the orchestrator creates persistent tasks.
6. Any code changes must pass the three-reviewer loop and automated tests before the workflow is considered complete.

That combination is what gives `claude-code-config` its character: the orchestrator stays focused on coordination, specialists stay focused on execution, slash commands can run practical end-to-end workflows, and review plus testing are treated as part of the system design rather than an afterthought.
