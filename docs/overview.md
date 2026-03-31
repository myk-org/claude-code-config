# Overview

`claude-code-config` turns Claude Code into a more structured working environment. Instead of only changing a prompt, it installs a coordinated set of settings, hooks, rule files, specialist agent definitions, slash-command plugins, reusable skills, and a bundled CLI called `myk-claude-tools`.

In practice, that means Claude Code starts with stronger defaults: the main assistant is pushed toward delegation, Git mistakes are caught earlier, review workflows are standardized, and common jobs such as PR review, release creation, review-database analysis, and multi-agent prompting become repeatable commands.

> **Note:** The shipped `settings.json` expects these files to live under `~/.claude/`, including `~/.claude/scripts/...` and `~/.claude/statusline.sh`. If you install the repository somewhere else, update those paths to match.

## What This Repository Maintains

| Component | What it gives you |
|---|---|
| `settings.json` | Claude Code permissions, hooks, status line, environment flags, and enabled plugins |
| `scripts/` | Notification, startup checks, prompt injection, command enforcement, and Git protection |
| `rules/` | The orchestrator policy set: routing, review loop, slash-command behavior, and task workflow |
| `agents/` | Specialist personas for Python, Git, GitHub, docs, tests, Bash, Docker, Kubernetes, Java, Go, frontend, and more |
| `plugins/` | Slash commands for GitHub workflows, local review workflows, and `acpx` multi-agent prompting |
| `skills/` | Reusable workflows such as browser automation and AI-driven docs generation |
| `myk_claude_tools/` | A Python CLI that powers PR, release, review, database, and CodeRabbit operations |

## What Runs Inside Claude Code

The heart of the setup is `settings.json`. It wires Claude Code's hook system to local scripts, narrows what tools can run directly, enables both first-party and official plugins, disables telemetry-related features, and turns on convenience flags such as always-thinking and auto-dream.

```37:85:/tmp/tmph3xeht2o/claude-code-config/settings.json
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
      // ... security prompt hook omitted ...
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
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/session-start-check.sh",
            "timeout": 5000
          }
        ]
      }
    ]
```

Those hooks do different jobs:

- `session-start-check.sh` verifies required tools and plugins such as `uv`, `gh`, `jq`, `gawk`, `prek`, `mcpl`, and the critical review plugins.
- `rule-injector.py` adds a short manager-style reminder to each prompt so the main assistant keeps delegating instead of doing all work directly.
- `rule-enforcer.py` blocks raw `python`, `python3`, `pip`, `pip3`, and `pre-commit` commands so the environment consistently uses `uv`, `uvx`, and `prek`.
- `git-protection.py` blocks commits or pushes on protected branches and on branches that are already merged.
- `my-notifier.sh` can surface Claude notifications through the desktop.

The setup also adds a custom status line. It builds a compact view from the current directory, SSH host, Git branch, virtual environment, model name, context-window usage, and line-change totals, so you can see the current working state at a glance.

`settings.json` also pre-enables a wider plugin set beyond this repository's own plugins, including official integrations such as `github`, `code-review`, `frontend-design`, `security-guidance`, `pyright-lsp`, `jdtls-lsp`, and `gopls-lsp`. At the environment level, it sets `DISABLE_TELEMETRY`, `DISABLE_ERROR_REPORTING`, and `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY`.

> **Warning:** This configuration is intentionally opinionated. Common shortcuts such as raw `python`, `pip`, `pre-commit`, or direct commits to `main` can be blocked until you use the preferred workflow.

## Rules and Specialist Agents

This repository separates orchestration from execution. The rule files in `rules/` describe how the main assistant should behave, while the files in `agents/` define the specialists that do the actual work.

A routing excerpt from the rule set shows the idea:

```5:25:/tmp/tmph3xeht2o/claude-code-config/rules/10-agent-routing.md
| Domain/Tool                                                                      | Agent                              |
|----------------------------------------------------------------------------------|------------------------------------|
| **Languages (by file type)**                                                     |                                    |
| Python (.py)                                                                     | `python-expert`                    |
| Go (.go)                                                                         | `go-expert`                        |
| Frontend (JS/TS/React/Vue/Angular)                                                | `frontend-expert`                  |
| Java (.java)                                                                     | `java-expert`                      |
| Shell scripts (.sh)                                                              | `bash-expert`                      |
| Markdown (.md)                                                                   | `technical-documentation-writer`   |
| **Infrastructure**                                                               |                                    |
| Docker                                                                           | `docker-expert`                    |
| Kubernetes/OpenShift                                                             | `kubernetes-expert`                |
| Jenkins/CI/Groovy                                                                | `jenkins-expert`                   |
| **Development**                                                                  |                                    |
| Git operations (local)                                                           | `git-expert`                       |
| GitHub (PRs, issues, releases, workflows)                                        | `github-expert`                    |
| Tests                                                                            | `test-automator`                   |
| Debugging                                                                        | `debugger`                         |
| API docs                                                                         | `api-documenter`                   |
| Claude Code docs (features, hooks, settings, commands, MCP, IDE, Agent SDK, API) | `claude-code-guide` (built-in)     |
| External library/framework docs (React, FastAPI, Django, etc.)                   | `docs-fetcher`                     |
```

That rule library also defines two important workflow policies:

- A mandatory three-reviewer loop using `superpowers:code-reviewer`, `pr-review-toolkit:code-reviewer`, and `feature-dev:code-reviewer` before testing and completion.
- Special handling for slash commands: the orchestrator runs the slash command workflow directly, rather than delegating the entire command away.

The `agents/` directory then supplies the actual specialist prompts. That includes language specialists like `python-expert`, infra specialists like `docker-expert` and `kubernetes-expert`, workflow specialists like `git-expert` and `github-expert`, and support roles like `technical-documentation-writer`, `test-automator`, and `test-runner`.

> **Note:** The runtime hook injects a short prompt reminder from `rule-injector.py`. The broader policy library still lives in `rules/`, where you maintain the project’s orchestrator behavior.

## Plugins and Slash Commands

The repository ships three first-party plugins through its marketplace manifest:

- `myk-github` for GitHub workflows such as PR review, review handling, release creation, and CodeRabbit rate-limit recovery.
- `myk-review` for local diff review and review-database analytics.
- `myk-acpx` for sending prompts to other ACP-compatible coding agents through `acpx`.

Here are real command examples from the plugin definitions.

`myk-github` adds PR review entry points:

```36:40:/tmp/tmph3xeht2o/claude-code-config/plugins/myk-github/commands/pr-review.md
- `/myk-github:pr-review` - Review PR from current branch (auto-detect)
- `/myk-github:pr-review 123` - Review PR #123 in current repo
- `/myk-github:pr-review https://github.com/owner/repo/pull/123` - Review from URL
```

`myk-review` exposes review-database queries for patterns and analytics:

```32:37:/tmp/tmph3xeht2o/claude-code-config/plugins/myk-review/commands/query-db.md
/myk-review:query-db stats --by-source        # Stats by source
/myk-review:query-db stats --by-reviewer      # Stats by reviewer
/myk-review:query-db patterns --min 2         # Find duplicate patterns
/myk-review:query-db dismissed --owner X --repo Y
/myk-review:query-db query "SELECT * FROM comments WHERE status='skipped' LIMIT 10"
/myk-review:query-db find-similar < comments.json   # Find similar dismissed comments
```

`myk-acpx` lets Claude hand work to other coding agents through `acpx`:

```32:41:/tmp/tmph3xeht2o/claude-code-config/plugins/myk-acpx/commands/prompt.md
- `/myk-acpx:prompt codex fix the tests`
- `/myk-acpx:prompt cursor review this code`
- `/myk-acpx:prompt gemini explain this function`
- `/myk-acpx:prompt codex --exec summarize this repo`
- `/myk-acpx:prompt codex --model o3-pro review the architecture`
- `/myk-acpx:prompt codex --fix fix the code quality issues`
- `/myk-acpx:prompt gemini --peer review this code`
- `/myk-acpx:prompt codex --peer --model o3-pro review the architecture`
- `/myk-acpx:prompt cursor,codex review this code`
- `/myk-acpx:prompt cursor,gemini,codex --peer review the architecture`
```

If you use this repository as a plugin source, these commands become a big part of the day-to-day workflow: review code locally, review PRs on GitHub, refine pending comments, query review history, or hand a prompt to another coding agent without rebuilding the workflow every time.

## Bundled CLI: `myk-claude-tools`

The plugins are backed by a Python CLI bundled in the same repository. In `pyproject.toml`, it is packaged as `myk-claude-tools`, currently version `1.7.2`, with a minimum Python version of `3.10`.

Its top-level command groups are defined here:

```12:22:/tmp/tmph3xeht2o/claude-code-config/myk_claude_tools/cli.py
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

Those groups map to concrete workflow areas:

- `pr` fetches PR diffs and metadata, fetches repository `CLAUDE.md` content, and posts inline PR comments.
- `release` validates release state, creates releases, detects version files, and bumps versions.
- `reviews` fetches, updates, posts, and stores review-thread data.
- `db` queries the local review SQLite database for stats, patterns, dismissed comments, and similar historical comments.
- `coderabbit` checks rate-limit state and re-triggers reviews after cooldown windows.

The release tooling is broader than a single language stack. The version-detection code supports `pyproject.toml`, `package.json`, `setup.cfg`, `Cargo.toml`, `build.gradle`, `build.gradle.kts`, and Python files that define `__version__`. The database tooling also stays intentionally safe: its default path is `<git-root>/.claude/data/reviews.db`, and raw SQL is restricted to read-only `SELECT` and `WITH` queries.

> **Tip:** You can use `myk-claude-tools` directly, not just through slash commands. That makes it useful for scripting, debugging, or plugging the same workflows into your own automation.

## Skills

The repository also bundles reusable skills in `skills/`. These are smaller, task-focused workflow packages rather than full plugins or specialist agents.

Today the bundled skills are:

- `agent-browser` for browser automation, page inspection, form filling, screenshots, and testing.
- `docsfy-generate-docs` for running a `docsfy`-based documentation generation workflow.

The `agent-browser` skill shows the style clearly:

```16:20:/tmp/tmph3xeht2o/claude-code-config/skills/agent-browser/SKILL.md
agent-browser open <url>        # Navigate to page
agent-browser snapshot -i       # Get interactive elements with refs
agent-browser click @e1         # Click element by ref
agent-browser fill @e2 "text"   # Fill input by ref
agent-browser close             # Close browser
```

Skills are useful when you want a repeatable workflow but do not need a full plugin or a permanent rule change.

## Testing and Quality Checks

This repository treats its configuration as real software, not just a folder of prompts.

The `tests/` suite covers hook behavior, Git protection, review-database queries, version detection and bumping, CodeRabbit handling, review storage, and other CLI flows. Local automation is defined in `tox.toml`, `pyproject.toml`, and `.pre-commit-config.yaml`, which together wire up `pytest`, Ruff, mypy, Flake8, markdownlint, secret scanning, and related checks.

That matters as an end user because it means the setup is maintained with the same habits you would expect from an application: it is versioned, tested, linted, and designed to fail safely when the environment is missing required tools.

Taken together, this repository gives Claude Code a full operating model: stricter settings, active safeguards, explicit routing rules, specialized agents, command-driven plugins, reusable skills, and a CLI that handles the mechanical parts of review and release workflows. If you want Claude Code to behave less like a blank slate and more like a structured engineering assistant, this is the layer that makes that happen.
