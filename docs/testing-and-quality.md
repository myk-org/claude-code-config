# Testing and Quality

This repository uses a local-first quality model. Unit tests run with `pytest`, `tox` provides a thin wrapper around that suite, and repository-wide checks run through pre-commit hooks. On top of that, the Claude Code configuration in this repo wires in runtime guardrails such as `rule-enforcer.py` and `git-protection.py`.

The result is a mix of fast automated checks and explicit policy tests. The Python test suite focuses on the `myk_claude_tools` CLI, hook scripts, release helpers, review automation, and the SQLite analytics layer.

## Quick Start

```bash
# Run the unit tests directly
uv run --group tests pytest tests

# Run a focused test module while you work
uv run --group tests pytest tests/test_git_protection.py

# Run the same suite through tox
tox

# Run formatting, typing, linting, Markdown, and secret scans
prek run --all-files
```

> **Note:** `pyproject.toml` declares `requires-python = ">=3.10"`, and most commands in this repository use `uv` because both `tox.toml` and the runtime hook policy are built around it.

> **Tip:** In the Claude Code environment configured by this repo, `scripts/rule-enforcer.py` intentionally blocks direct `python`, `pip`, and `pre-commit` commands. Use `uv`, `uvx`, and `prek` there instead.

## Quality Stack at a Glance

| Area | Source of truth | Purpose |
| --- | --- | --- |
| Unit tests | `tox.toml`, `tests/` | Runs the Python test suite with `pytest` |
| Linting and formatting | `pyproject.toml`, `.pre-commit-config.yaml` | Ruff lint + Ruff format |
| Type checking | `pyproject.toml`, `.pre-commit-config.yaml` | mypy |
| Extra Python bug check | `.flake8`, `.pre-commit-config.yaml` | Flake8 `M511` via `flake8-mutable` |
| Markdown quality | `.markdownlint.yaml`, `.pre-commit-config.yaml` | markdownlint |
| Secret scanning | `.pre-commit-config.yaml` | `detect-secrets`, `gitleaks`, and `detect-private-key` |
| Runtime guardrails | `settings.json`, `scripts/` | Blocks unsafe commands and protected-branch writes |

## Pytest and tox

`pytest` is the actual test runner. `tox` is configured as a lightweight wrapper around it, not as a build matrix or packaging pipeline. The checked-in tox config has a single environment named `unittests`, and `skipsdist = true` tells tox not to build the package first.

From `tox.toml`:

```toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

From `pyproject.toml`:

```toml
[dependency-groups]
tests = ["pytest>=9.0.2"]
```

What this means in practice:

- If you want the fastest path, run `uv run --group tests pytest tests`.
- If you prefer tox, `tox` runs the same suite through the `unittests` environment.
- The test suite is designed to be fast and deterministic, with heavy use of mocked Git, GitHub CLI, GraphQL, subprocess, and SQLite interactions.

## Ruff, mypy, and Flake8

### Ruff

Ruff is the main Python linter and formatter. The repository enables autofix-friendly behavior, grouped output, and preview mode.

From `pyproject.toml`:

```toml
[tool.ruff]
preview = true
line-length = 120
fix = true
output-format = "grouped"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "PLC0415", "ARG", "RUF059"]

[tool.ruff.lint.per-file-ignores]
"myk_claude_tools/*/commands.py" = ["PLC0415"]
```

What to expect:

- `120` characters is the Python line-length target.
- `fix = true` means Ruff is configured for autofix-friendly runs.
- The selected rules cover core linting, import ordering, bug-prone patterns, Python modernization, unused arguments, and a few repository-specific checks.
- `PLC0415` is ignored for `commands.py` files because the CLI command modules intentionally use lazy imports for faster startup.

> **Tip:** Because `preview = true` is enabled, keeping Ruff reasonably up to date matters. Very old Ruff versions may not match the repository’s expected behavior.

### mypy

Mypy is configured more strictly than its defaults, especially around untyped or partially typed functions.

From `pyproject.toml`:

```toml
[tool.mypy]
check_untyped_defs = true
disallow_any_generics = false
disallow_incomplete_defs = true
disallow_untyped_defs = true
no_implicit_optional = true
show_error_codes = true
warn_unused_ignores = true
strict_equality = true
extra_checks = true
warn_unused_configs = true
warn_redundant_casts = true
```

In plain English, that means:

- New Python code is expected to be typed, not left as “we’ll add types later.”
- Even when a function is untyped, mypy still checks its body.
- Implicit `Optional` behavior is not allowed.
- Redundant casts, unused ignores, and unused config are treated as real issues.

### Flake8

Flake8 is deliberately narrow here. It is not duplicating Ruff’s full lint surface. Instead, it is reserved for `M511`, provided by `flake8-mutable`, to catch mutable default argument bugs.

From `.flake8`:

```ini
[flake8]
select=M511

exclude =
    doc,
    .tox,
    .git,
    .yml,
    Pipfile.*,
    docs/*,
    .cache/*
```

That is why you will see both Ruff and Flake8 in the hook stack: Ruff does the heavy lifting, and Flake8 adds one focused rule the project still wants enforced.

## Markdown Quality

The repository contains a lot of Markdown: plugin commands, agent definitions, rules, and user-facing docs. `markdownlint` is part of the default hook set, with a small adjustment to keep documentation writing practical.

From `.markdownlint.yaml`:

```yaml
default: true

MD013:
  line_length: 180
  code_blocks: false
  tables: false
```

This means:

- All default markdownlint rules are on.
- Long prose lines are allowed up to `180` characters.
- Code fences and tables are exempt from the line-length rule, which avoids awkward wrapping of examples and comparison tables.

## Secret Scanning and Repository Hygiene

Secret scanning is not a one-tool checkbox here. The pre-commit stack combines several layers:

- `detect-private-key` from `pre-commit-hooks` catches obvious key material.
- `detect-secrets` looks for likely secret patterns and high-risk text.
- `gitleaks` adds a second secret-scanning engine with different signatures.
- Generic hygiene hooks also catch merge conflicts, large files, mixed line endings, debug statements, trailing whitespace, and TOML syntax errors.

From `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key
      - id: debug-statements
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-toml

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.0
    hooks:
      - id: gitleaks
```

The project also handles test-only false positives carefully. Instead of weakening secret scanners globally, tests allowlist specific fake SHA-looking values inline when needed.

From `tests/test_store_reviews_to_db.py`:

```python
assert result == "abc1234567890abcdef"  # pragma: allowlist secret
```

> **Note:** This is a good pattern to copy. If a test needs a fake token, hash, or key-shaped string, allowlist that exact line instead of broadly disabling the scanner.

## Pre-commit Workflow

The checked-in hook stack is the main “one command” quality gate. In addition to the hooks above, it also runs Ruff, Ruff format, mypy, Flake8, and markdownlint.

Relevant parts of `.pre-commit-config.yaml`:

```yaml
ci:
  autofix_prs: false
  autoupdate_commit_msg: "ci: [pre-commit.ci] pre-commit autoupdate"

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.14
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.19.1
    hooks:
      - id: mypy
        additional_dependencies:
          - pytest

  - repo: https://github.com/igorshubovych/markdownlint-cli
    rev: v0.44.0
    hooks:
      - id: markdownlint
        args: [--config, .markdownlint.yaml]
        types: [markdown]
```

Two practical takeaways:

- The project expects contributors to fix issues locally rather than relying on automatic bot-generated fix PRs.
- The hook stack is intentionally broad. If `prek run --all-files` passes, you have exercised the linting, formatting, typing, Markdown, and secret-scanning layers in one go.

## Hook-Enforced Quality in the Claude Code Environment

This repository does not rely only on conventional lint and test tools. It also encodes runtime guardrails in Claude Code hook scripts, and those scripts are heavily tested.

From `settings.json`:

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
]
```

### `rule-enforcer.py`

`rule-enforcer.py` keeps the environment consistent by steering Python and pre-commit execution toward the approved toolchain.

From `scripts/rule-enforcer.py`:

```python
def is_forbidden_python_command(command: str) -> bool:
    cmd = command.strip().lower()

    # Allow uv/uvx commands
    if cmd.startswith(("uv ", "uvx ")):
        return False

    # Block direct python/pip
    forbidden = ("python ", "python3 ", "pip ", "pip3 ")
    return cmd.startswith(forbidden)
```

Tests around this script verify that it:

- Blocks direct `python`, `python3`, `pip`, `pip3`, and `pre-commit` commands.
- Allows `uv`, `uvx`, and `prek`.
- Handles whitespace and mixed case correctly.
- Fails open on malformed hook input so a broken hook payload does not brick the entire session.

### `git-protection.py`

`git-protection.py` protects branch hygiene. It blocks commits and pushes in cases that are easy to regret later.

From `scripts/git-protection.py`:

```python
# Allow amend on unpushed commits
if is_amend_with_unpushed_commits(command):
    return False, None
```

The tests around `git-protection.py` lock down behavior such as:

- Rejecting commits on `main` or `master`.
- Rejecting commits and pushes to branches that are already merged.
- Rejecting work on branches whose pull requests are already merged.
- Allowing `git commit --amend` when the branch is ahead of its remote.
- Handling detached HEAD, orphan branches, and GitHub API errors explicitly.
- Failing closed when it cannot safely decide, so an unsafe commit or push does not slip through.

> **Warning:** These hook scripts are part of the quality story in this repo. Passing `pytest` alone does not mean you have exercised the runtime guardrails unless the relevant hook tests are also green.

## What the Test Suite Actually Guarantees

The tests in `tests/` are not generic smoke tests. They encode concrete policies and edge cases for the project’s most important moving parts.

### Review automation is expected to be safe and repeatable

The review pipeline tests cover fetching, parsing, replying, storing, and querying review data. That includes:

- GitHub GraphQL and REST pagination behavior.
- Parsing CodeRabbit outside-diff, nitpick, and duplicate comments.
- Posting replies idempotently, so already-posted entries are not posted again.
- Retrying a failed resolve without double-posting a reply.
- Grouping body-only comments into consolidated PR comments and chunking them to stay below GitHub size limits.
- Different resolution rules for human versus AI-generated review comments.

From `myk_claude_tools/reviews/post.py`:

```python
# Determine if we should resolve this thread (MUST be before resolve_only_retry check)
should_resolve = True
if category == "human" and status != "addressed":
    should_resolve = False
```

That one branch summarizes a real project policy: human review threads stay open unless they were actually addressed, while AI-originated review items can be auto-resolved after the reply policy is applied.

### Review database access is deliberately conservative

The SQLite layer is tested for append-only storage, schema migration, and read-only analytics access. The database helper does not allow arbitrary write SQL through its query interface.

From `myk_claude_tools/db/query.py`:

```python
if not sql_upper.startswith(("SELECT", "WITH")):
    raise ValueError("Only SELECT/CTE queries are allowed for safety")
```

Tests also verify that the query layer rejects:

- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, and `PRAGMA`
- Multi-statement SQL
- Dangerous keywords hidden inside otherwise “read-like” queries

The storage layer is also tested to create `.claude/data/` with `0700` permissions, migrate older databases forward, and append new review snapshots instead of rewriting earlier ones.

### Version tooling is section-aware and atomic

The release helpers are also well-covered. The tests check that version detection and bumping:

- Find versions in `pyproject.toml`, `package.json`, `setup.cfg`, `Cargo.toml`, Gradle files, and Python `__version__` files
- Skip excluded directories such as `.venv`, `node_modules`, `.tox`, and build caches
- Only update the correct section, not every `version` key in a file
- Reject invalid version strings
- Fail safely when a requested file filter does not match
- Use atomic writes so partial edits do not leak into the repository on error

These are especially useful guarantees if you use the repository’s release helpers as part of a scripted workflow.

### Hook behavior is tested as behavior, not just as syntax

The hook test modules do more than import the scripts and call one happy path. They cover:

- Regex-based Git subcommand detection, including false-positive cases
- JSON hook I/O behavior
- Whitespace and case handling
- Timeout and subprocess failure paths
- The intentional difference between fail-open and fail-closed hooks

> **Note:** Most of these tests are unit tests with mocked subprocess and GitHub responses. That is intentional. The goal is to make policy-heavy behavior easy to test without depending on live GitHub state or a specific local Git history.

> **Tip:** If you want the exact contract for a subsystem, the clearest starting points are `tests/test_rule_enforcer.py`, `tests/test_git_protection.py`, `tests/test_post_review_replies.py`, `tests/test_store_reviews_to_db.py`, and `tests/test_review_db.py`.

## CI/CD Status

> **Warning:** No `.github/workflows/` directory is committed in this repository.

From the repository contents, the quality gates you can verify are:

- `pytest` for unit tests
- `tox` as a wrapper around the unit test suite
- pre-commit hooks for linting, typing, formatting, Markdown, and secret scanning
- Claude Code hook scripts for runtime enforcement

`.pre-commit-config.yaml` does include a `ci:` section, but the source tree itself does not define a checked-in GitHub Actions pipeline. In practice, this means the repository is local-first: contributors are expected to run the checks themselves and keep them green before sharing changes.

## Recommended Workflow

A practical workflow for contributors is:

1. Run a targeted `pytest` module while you work, such as `uv run --group tests pytest tests/test_post_review_replies.py`.
2. Run the full test suite with `uv run --group tests pytest tests`.
3. Run `prek run --all-files` before committing.
4. If you use tox, make sure `tox` stays green as a second path through the same unit-test suite.

That combination covers the repository’s two main quality layers: tested behavior and repository-wide hygiene.
