# Repository Structure

This repository is organized around one practical goal: turning a Claude Code setup into a reusable, versioned workspace with specialist agents, policy files, hook scripts, installable plugins, reusable skills, and a companion Python CLI.

The easiest way to understand it is to treat the repository as a control plane plus execution layers. `settings.json` turns features on, `scripts/` implements runtime behavior, `agents/` and `rules/` describe how work should be routed, `plugins/` exposes slash commands, and `myk_claude_tools/` provides deterministic CLI commands that those workflows can call.

> **Note:** The live paths in `settings.json` point at `~/.claude/...`, so this repository is meant to be copied or symlinked into a Claude home directory. The checkout is the source of truth; the installed `~/.claude` path is what Claude Code executes.

## At a glance

| Path | What it contains | Why it matters |
| --- | --- | --- |
| `settings.json` and root config files | Hooks, permissions, plugin enablement, packaging, linting, review-tool config | These files wire the rest of the repository together |
| `agents/` | Custom specialist agent definitions | This is where the project’s reusable expert personas live |
| `rules/` | Long-form orchestration and workflow policy | This directory explains how work should be routed and reviewed |
| `scripts/` | Hook implementations and shell helpers | These files enforce and support runtime behavior |
| `plugins/` | Installable slash-command plugins | These become user-invokable commands inside Claude Code |
| `skills/` | Reusable tool-specific playbooks | These capture procedural workflows without becoming plugins or agents |
| `myk_claude_tools/` | Python package and CLI | This is the deterministic execution engine behind many workflows |
| `tests/` | Pytest coverage for hooks and CLI modules | This is where behavior is verified |
| `docs/plans/` | Design and planning notes | Useful background, but not part of the runtime |
| `state/` | Runtime snapshot storage | Keeps local state out of version control |

```text
settings.json
├── hooks ----------------------> scripts/
├── enabledPlugins -------------> plugins/
├── statusLine -----------------> statusline.sh
└── permissions/allowedTools --> what Claude can invoke

agents/ + rules/ ---------------> delegation and workflow behavior
plugins/*/commands/*.md --------> myk_claude_tools/
tests/ + tox + pre-commit ------> verification
```

## Root configuration

If you only read one file first, read `settings.json`. It is the switchboard for the entire repository: it registers hooks, enables both official and repo-local plugins, defines the status line, and limits which tools Claude Code may use.

```25:55:settings.json
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/my-notifier.sh"
          }
        ]
      }
    ],
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
      },
```

Beyond `settings.json`, the root also carries the rest of the project-wide configuration:

- `pyproject.toml` packages `myk-claude-tools`, defines Python requirements, and centralizes Ruff and mypy settings.
- `tox.toml` defines the standard local test entrypoint.
- `.pre-commit-config.yaml` runs formatting, linting, secret scanning, and type checks.
- `.coderabbit.yaml` and `.pr_agent.toml` configure external review tooling.
- `.claude-plugin/marketplace.json` publishes the local plugins.
- `statusline.sh` builds the Claude Code status line from JSON input.

> **Tip:** When you are tracing behavior, follow the chain from `settings.json` to a hook or plugin name, then to the implementation file in `scripts/`, `plugins/`, or `myk_claude_tools/`.

This repository also uses a strict whitelist-style `.gitignore`. New files are not tracked automatically.

> **Warning:** Adding a new agent, rule, script, plugin file, skill, test, or Python module is a two-step change: create the file, then explicitly unignore it in `.gitignore`.

```1:18:.gitignore
# Ignore everything by default
# This config integrates into ~/.claude so we must be explicit about what we track
*

# Core config files
!.coderabbit.yaml
!.gitignore
!.markdownlint.yaml
!LICENSE
!AI_REVIEW.md
!README.md
!settings.json
!statusline.sh
!uv.lock

# agents/
!agents/
!agents/00-base-rules.md
```

## `agents/`: specialist prompts

The `agents/` directory holds the project’s custom specialist definitions. These are not executable programs; they are reusable prompts with tool permissions and working rules for specific domains such as Python, Bash, Git, Docker, Kubernetes, documentation, testing, and debugging.

Every agent inherits the shared guidance in `agents/00-base-rules.md`, then adds its own domain-specific instructions. A typical agent file starts with YAML frontmatter that declares its name, description, tools, and optional skills.

```1:5:agents/python-expert.md
---
name: python-expert
description: MUST BE USED for Python code creation, modification, refactoring, and fixes. Specializes in idiomatic Python, async/await, testing, and modern Python development.
tools: Read, Write, Edit, Bash, Glob, Grep, LSP
skills: [test-driven-development]
```

A few useful patterns to know:

- `agents/00-base-rules.md` is the shared baseline for all custom agents.
- Most agent files focus on one domain, such as `python-expert.md`, `bash-expert.md`, `git-expert.md`, or `technical-documentation-writer.md`.
- Some agents add runtime details in frontmatter. For example, `git-expert.md` declares a `PreToolUse` hook that points at `git-protection.py`.

> **Note:** Not every routed agent has a file in `agents/`. `rules/10-agent-routing.md` also references built-in agents such as `general-purpose` and `claude-code-guide`, which are provided by Claude Code itself rather than stored in this repository.

## `rules/`: workflow and policy library

The `rules/` directory is the human-readable policy layer for the project. These files explain how the main Claude session should behave, what to delegate, when to create issues, how to run reviews, how to use tasks, how slash commands differ from normal requests, and how to use MCP.

The numbered filenames make the policy set easy to scan and keep in a stable order. In practice, each file has a distinct responsibility:

- `00-orchestrator-core.md` defines the baseline manager/delegation model.
- `05-issue-first-workflow.md` explains when to create an issue before doing implementation work.
- `10-agent-routing.md` maps work types to specialists.
- `15-mcp-launchpad.md` documents `mcpl` discovery and execution.
- `20-code-review-loop.md` defines the mandatory review cycle.
- `25-task-system.md` explains when persisted tasks add value.
- `30-slash-commands.md` defines the direct-execution rules for slash commands.
- `40-critical-rules.md` covers global guardrails such as parallelism, temp files, and `uv`.
- `50-agent-bug-reporting.md` explains how to report bugs in custom agent definitions.

> **Note:** The full policy text lives in `rules/`. The current `scripts/rule-injector.py` adds a short manager reminder at prompt-submit time, so if you need the detailed workflow rules, read this directory directly.

## `scripts/`: hook implementations and helpers

`scripts/` is the executable layer for runtime behavior. Where `rules/` tells you what should happen, `scripts/` tells you what Claude Code actually runs.

The main files are:

- `rule-injector.py`: injects a short system reminder during `UserPromptSubmit`.
- `rule-enforcer.py`: blocks direct Bash use of `python`, `python3`, `pip`, `pip3`, and `pre-commit`, steering users toward `uv`, `uvx`, and `prek`.
- `git-protection.py`: blocks commits and pushes on protected or already-merged branches.
- `session-start-check.sh`: checks for required tools and required review plugins at session start.
- `my-notifier.sh`: sends desktop notifications.
- `statusline.sh`: builds the Claude status line from runtime JSON.

Here is the core of `rule-enforcer.py`, which shows that the enforcement logic is implemented as a hook script rather than only as prose:

```35:50:scripts/rule-enforcer.py
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
                            "See: https://docs.astral.sh/uv/"
```

This directory is also where the repo’s safety behavior lives. If you want to understand why a Bash command, commit, or push was allowed or denied, this is where to look first.

## `plugins/`: installable slash commands

The `plugins/` directory packages user-facing slash commands for Claude Code. Each plugin has its own folder and typically includes:

- `.claude-plugin/plugin.json` for plugin metadata
- `commands/*.md` for individual slash-command definitions
- `README.md` for plugin-level help

This repository currently ships three local plugins:

- `plugins/myk-github/` for GitHub review, release, and CodeRabbit workflows
- `plugins/myk-review/` for local review flows and database queries
- `plugins/myk-acpx/` for multi-agent prompting through `acpx`

A command definition is a Markdown file with frontmatter plus step-by-step instructions. The frontmatter is what declares the command’s description, arguments, and allowed tools.

```1:5:plugins/myk-github/commands/pr-review.md
---
description: Review a GitHub PR and post inline comments on selected findings
argument-hint: [PR_NUMBER|PR_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task
---
```

That design is important because it shows how the repository divides responsibilities:

- The plugin command file defines the user workflow.
- The command is allowed to call tools such as `gh`, `git`, `uv`, or `myk-claude-tools`.
- The heavy lifting is often delegated to the Python package in `myk_claude_tools/`.

The root `.claude-plugin/marketplace.json` file ties those plugin folders together into a publishable marketplace listing.

## `skills/`: reusable playbooks

The `skills/` directory is separate from both `agents/` and `plugins/`. A skill is a reusable, tool-focused playbook: it does not create a slash command, and it does not become a specialist persona. Instead, it gives Claude a repeatable procedure for using a specific tool or workflow well.

This repository currently includes:

- `skills/agent-browser/SKILL.md`
- `skills/docsfy-generate-docs/SKILL.md`

For example, the `agent-browser` skill is a compact operational guide for browser automation:

```15:20:skills/agent-browser/SKILL.md
agent-browser open <url>        # Navigate to page
agent-browser snapshot -i       # Get interactive elements with refs
agent-browser click @e1         # Click element by ref
agent-browser fill @e2 "text"   # Fill input by ref
agent-browser close             # Close browser
```

> **Tip:** Use a skill when the work is mostly procedural and tool-driven. Use an agent when you need a domain specialist. Use a plugin when you want a slash command users can invoke directly.

## `myk_claude_tools/`: deterministic CLI engine

The `myk_claude_tools/` package is the repository’s executable backend for deterministic operations. It is published as the `myk-claude-tools` console command, and many plugin workflows depend on it.

The top-level CLI is intentionally small: it just assembles the package’s subcommand groups.

```12:22:myk_claude_tools/cli.py
@click.group()
@click.version_option()
def cli() -> None:
    """CLI utilities for Claude Code plugins."""


cli.add_command(coderabbit_commands.coderabbit, name="coderabbit")
cli.add_command(db_commands.db, name="db")
cli.add_command(pr_commands.pr, name="pr")
cli.add_command(release_commands.release, name="release")
cli.add_command(reviews_commands.reviews, name="reviews")
```

Those subpackages divide the work cleanly:

- `coderabbit/` handles CodeRabbit rate-limit detection and retriggering.
- `db/` provides read-only analytics and query access to the review database.
- `pr/` fetches PR diffs, retrieves `CLAUDE.md`, and posts inline comments.
- `release/` detects version files, bumps versions, and creates releases.
- `reviews/` fetches, posts, updates, and stores review-thread data.

A few details make this package especially useful:

- `pyproject.toml` registers the console entrypoint as `myk-claude-tools = "myk_claude_tools.cli:main"`.
- `db/query.py` auto-detects the database at `<git-root>/.claude/data/reviews.db`.
- Raw SQL queries are intentionally restricted to `SELECT` and `WITH` statements for safety.
- `release/detect_versions.py` and `release/bump_version.py` handle version files across multiple ecosystems, including Python, Node.js, Rust, and Gradle.

If a plugin command feels more like a script than a prompt, the implementation usually lives here.

## `tests/` and automation

The `tests/` directory mirrors the repository’s most important runtime concerns: hooks, git safety rules, review database behavior, release/version automation, and CodeRabbit integrations.

Local test execution is intentionally simple:

```1:7:tox.toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

Important test files include:

- `tests/test_rule_enforcer.py` for deny/allow behavior and hook JSON output
- `tests/test_git_protection.py` for branch detection, merge checks, and commit/push blocking
- `tests/test_review_db.py` for database schema, migrations, query safety, and CLI behavior
- `tests/test_detect_versions.py` for cross-ecosystem version-file detection
- `tests/test_bump_version.py` for safe version updates
- `tests/test_coderabbit_rate_limit.py` for rate-limit parsing and retrigger logic

The rest of the automation is configured at the root:

- `.pre-commit-config.yaml` runs `pre-commit-hooks`, `flake8`, `detect-secrets`, `ruff`, `ruff-format`, `gitleaks`, `mypy`, and `markdownlint`.
- `.coderabbit.yaml` configures hosted CodeRabbit review tone, review settings, and enabled analysis tools.
- `.pr_agent.toml` configures Qodo Merge review behavior.

> **Note:** There is no `.github/workflows/` directory in this repository. The validation story is local-first: `tox`, `pre-commit`, and external review services configured through `.coderabbit.yaml` and `.pr_agent.toml`.

## Supporting directories

Two smaller directories are worth knowing about:

- `docs/plans/` holds design notes and planning documents, such as the auto-version-bump plan and design writeups. These are reference material, not runtime configuration.
- `state/` is for runtime snapshot data. Its local `.gitignore` keeps `*-snapshot.json` files out of version control while preserving the directory itself.

## Where to look first

| If you want to… | Start here | Then check |
| --- | --- | --- |
| Change hook behavior or startup checks | `settings.json` | `scripts/`, `tests/test_rule_enforcer.py`, `tests/test_git_protection.py` |
| Add or edit a specialist agent | `agents/` | `rules/10-agent-routing.md`, `.gitignore` |
| Change orchestration policy | `rules/` | `settings.json`, `scripts/` |
| Add a slash command | `plugins/<plugin>/commands/` | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.gitignore` |
| Add deterministic CLI behavior | `myk_claude_tools/` | `pyproject.toml`, `tests/` |
| Update local validation | `tox.toml` and `.pre-commit-config.yaml` | `.coderabbit.yaml`, `.pr_agent.toml` |
| Add any new tracked file under the major folders | The target directory | `.gitignore` whitelist entries |
