# Development Environment

This repository combines shared Claude Code configuration with a Python CLI package named `myk-claude-tools`. If you are contributing locally, the most important things to understand are the `uv`-first Python workflow, the single `tests` dependency group, the hook-driven local guardrails, and the whitelist-style `.gitignore`.

If you are orienting yourself, these are the paths you will touch most often:

- `myk_claude_tools/` for the Python package and CLI commands
- `tests/` for the pytest suite
- `scripts/` for hook scripts such as `rule-enforcer.py` and `git-protection.py`
- `settings.json` for Claude Code hook wiring and tool permissions
- `agents/`, `rules/`, and `plugins/` for shared configuration content

## Python Package Setup

`pyproject.toml` defines a small Python package: Python 3.10+, Hatchling for builds, a console script named `myk-claude-tools`, and only two runtime dependencies.

```1:24:pyproject.toml
[project]
name = "myk-claude-tools"
version = "1.7.2"
description = "CLI utilities for Claude Code plugins"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [{ name = "myk-org" }]
keywords = ["claude", "cli", "github", "code-review"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Environment :: Console",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
]
dependencies = ["click>=8.0.0", "tomli>=2.0.0; python_version < '3.11'"]

[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

The CLI itself is a Click command group. At the top level, it exposes subcommands for CodeRabbit workflows, review database queries, PR helpers, release tasks, and review operations.

```12:27:myk_claude_tools/cli.py
@click.group()
@click.version_option()
def cli() -> None:
    """CLI utilities for Claude Code plugins."""


cli.add_command(coderabbit_commands.coderabbit, name="coderabbit")
cli.add_command(db_commands.db, name="db")
cli.add_command(pr_commands.pr, name="pr")
cli.add_command(release_commands.release, name="release")
cli.add_command(reviews_commands.reviews, name="reviews")


def main() -> None:
    """Entry point."""
    cli()
```

> **Note:** The package version is stored in both `pyproject.toml` and `myk_claude_tools/__init__.py`. If you update release metadata manually, keep both in sync.

## Dependency Groups

The repository currently defines a single dependency group: `tests`.

```67:68:pyproject.toml
[dependency-groups]
tests = ["pytest>=9.0.2"]
```

There is no separate `dev`, `lint`, or `docs` dependency group in `pyproject.toml` today. In practice, that means the project keeps development dependencies intentionally lean and routes test installation through `uv`.

> **Note:** `uv.lock` is tracked in the repository. If you change dependencies, plan to update both `pyproject.toml` and `uv.lock`.

## Prerequisites

Minimum setup:

- Python 3.10 or newer
- `uv`
- Git

Useful extras:

- `prek` if you want to run the pre-commit stack locally
- `gh` if you work on GitHub-related commands or review flows
- `jq`, `gawk`, and `mcpl` for review and MCP-oriented workflows

`scripts/session-start-check.sh` is the repo's built-in environment check. It treats `uv` as critical and reports optional tools when they are relevant to the current repo or workflow. If you use the full Claude Code setup, it also checks for required review plugins such as `pr-review-toolkit`, `superpowers`, and `feature-dev`.

> **Tip:** If you want the packaged CLI on your `PATH`, the repository's own plugin command docs check `myk-claude-tools --version` and recommend `uv tool install myk-claude-tools` when it is missing.

## Local Development Flow

The simplest way to work in this repository is:

1. Use `uv` or `uvx` for Python-related commands.
2. Run the unit test suite through the `tests` dependency group.
3. Run the hook stack through `prek` when you want the same checks the repository is configured to use.
4. If you are testing the full Claude Code configuration, expect local hooks from `settings.json` to shape the experience.

`tox.toml` keeps the test flow deliberately simple. There is one environment, `unittests`, and it runs the working tree directly instead of building a source distribution first.

```1:7:tox.toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

That `uv`-first approach is enforced, not just suggested. `scripts/rule-enforcer.py` actively blocks direct `python`, `python3`, `pip`, `pip3`, and direct `pre-commit` usage in hook-managed Bash flows, and points contributors toward `uv`, `uvx`, and `prek` instead.

```38:66:scripts/rule-enforcer.py
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
                        ),
                    }
                }
                print(json.dumps(output))
                sys.exit(0)

            if is_forbidden_precommit_command(command):
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Direct pre-commit commands are forbidden.",
                        "additionalContext": (
```

In practice, the commands you will see repeated across this repository are `uv run --group tests pytest tests`, `uvx ruff check .`, `prek run --all-files`, and `myk-claude-tools --version`.

> **Warning:** If you are used to generic Python repositories, these guardrails can feel strict at first. That is intentional. The behavior is covered by `tests/test_rule_enforcer.py` and `tests/test_git_protection.py`, so those are the first tests to revisit when you change hook behavior.

If you are exercising the full Claude Code configuration rather than only editing Python code, `settings.json` also wires in `session-start-check.sh`, `rule-injector.py`, `rule-enforcer.py`, and `git-protection.py`. That makes hook behavior part of the normal local development loop.

> **Note:** `settings.json` includes a `_scriptsNote` reminding contributors that new script entries must be added in both `permissions.allow` and `allowedTools`.

## Quality Checks

Ruff is the main lint and formatting tool here, and Mypy handles type checking. Ruff configuration lives in `pyproject.toml` and uses a 120-character line length with auto-fix enabled. Mypy is configured with stricter-than-default settings such as `disallow_untyped_defs`, `no_implicit_optional`, and `strict_equality`.

Flake8 is present too, but only for `M511` via `flake8-mutable`; it is not the primary style checker for the project.

The configured pre-commit stack covers file hygiene, secret scanning, Ruff, Mypy, Flake8, Gitleaks, and Markdown linting.

```9:63:.pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: check-added-large-files
      - id: check-docstring-first
      - id: check-executables-have-shebangs
      - id: check-merge-conflict
      - id: check-symlinks
      - id: detect-private-key
      - id: mixed-line-ending
      - id: debug-statements
      - id: trailing-whitespace
        args: [--markdown-linebreak-ext=md] # Do not process Markdown files.
      - id: end-of-file-fixer
      - id: check-ast
      - id: check-builtin-literals
      - id: check-toml

  - repo: https://github.com/PyCQA/flake8
    rev: 7.3.0
    hooks:
      - id: flake8
        args: [--config=.flake8]
        additional_dependencies:
          [flake8-mutable]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.14
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.0
    hooks:
      - id: gitleaks

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
          - pytest

  - repo: https://github.com/igorshubovych/markdownlint-cli
```

That split is worth remembering when you debug a failed check:

- Look in `pyproject.toml` for Ruff and Mypy behavior.
- Look in `.flake8` for the narrow Flake8 rule set.
- Look in `.pre-commit-config.yaml` for the full local hook chain.

> **Tip:** Installing `prek` makes it easier to run the repository's hook stack locally without invoking `pre-commit` directly, which matches the repo's own guardrails.

## Repository Conventions

The root `.gitignore` uses a whitelist model. It starts by ignoring everything, then selectively re-enables the files and directories that are meant to be shared.

```1:14:.gitignore
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
```

This is unusual in a Python project, but it fits this repository. The configuration is designed to live inside `~/.claude`, so the default is "ignore unless explicitly shared."

In practice, that means directories such as `agents/`, `rules/`, `scripts/`, `tests/`, `plugins/`, and `myk_claude_tools/` are only tracked because individual paths are explicitly whitelisted later in the file.

> **Warning:** If you add a new file under one of those trees and forget the matching `!path/to/file` entry in `.gitignore`, Git will behave as if the file does not exist. Update the correct section and keep the entries alphabetized.

The same "explicit over implicit" convention shows up elsewhere too. Hook scripts are registered intentionally, allowed tools are listed explicitly, and tracked files are opt-in rather than assumed.

## CI And Automation

There is no checked-in CI pipeline in this repository. There is no `.github/workflows/` directory, no `Jenkinsfile`, and no GitLab or Azure pipeline file in the tree.

What the repository does include is local and external automation configuration:

- `.pre-commit-config.yaml` for local checks
- `.coderabbit.yaml` for review automation
- `settings.json` plus `scripts/` for Claude Code hook behavior

> **Note:** The `ci:` block inside `.pre-commit-config.yaml` is pre-commit metadata, not a full repository CI pipeline.

> **Tip:** Treat local `tox` and `prek` runs as the primary way to validate changes before opening a pull request unless you add a dedicated CI workflow later.
