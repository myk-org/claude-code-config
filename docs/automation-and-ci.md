# Automation and CI

This repository does not check in a repository-local CI workflow. There is no `.github/workflows/` directory in the tree. Instead, the project's automation is built from a mix of local quality checks, `pre-commit.ci`, GitHub-app-based review automation, and Claude Code hooks.

> **Note:** If you fork this repository, you will not automatically get a GitHub Actions pipeline. If you want repository-owned CI jobs, add your own workflows on top of the configs described here.

## At a glance

| Layer | What it does | Where it is configured |
| --- | --- | --- |
| Pre-commit hooks | Linting, formatting, secrets scanning, type checking, Markdown checks | `.pre-commit-config.yaml`, `pyproject.toml`, `.flake8`, `.markdownlint.yaml` |
| Local test runner | Runs the Python test suite with `pytest` via `uv` | `tox.toml` |
| CodeRabbit | Automated PR reviews, summaries, tool-driven checks, rate-limit helpers | `.coderabbit.yaml`, `myk_claude_tools/coderabbit/`, `plugins/myk-github/commands/coderabbit-rate-limit.md` |
| Qodo Merge | Automated PR reviews and review commands such as `/describe`, `/review`, and `/improve` | `.pr_agent.toml`, `myk_claude_tools/reviews/`, `plugins/myk-github/commands/review-handler.md` |
| Claude Code hooks | Session checks and command guardrails | `settings.json`, `scripts/` |

## Pre-commit and pre-commit.ci

The main checked-in quality gate is `.pre-commit-config.yaml`. That file defines both the local hook set and the `pre-commit.ci` behavior.

```yaml
ci:
  autofix_prs: false
  autoupdate_commit_msg: "ci: [pre-commit.ci] pre-commit autoupdate"
```

In practice, that means `pre-commit.ci` may create hook-version update commits, but it is not configured to push autofix commits back to pull requests. Contributors are expected to run the checks themselves.

The hook set covers repository hygiene, Python quality, secrets scanning, and Markdown validation:

```yaml
- repo: https://github.com/PyCQA/flake8
  rev: 7.3.0
  hooks:
    - id: flake8
      args: [--config=.flake8]
      additional_dependencies:
        [flake8-mutable]

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

Other configured hooks include:

- `pre-commit-hooks` for file hygiene such as large files, merge conflicts, symlinks, AST and TOML validation, end-of-file fixes, and private-key detection.
- `detect-secrets` and `gitleaks` for secrets scanning.
- `trailing-whitespace` with special Markdown handling via `--markdown-linebreak-ext=md`.

Supporting config is checked in alongside the hook file. Markdown line-length is relaxed for prose-heavy docs:

```yaml
default: true

MD013:
  line_length: 180
  code_blocks: false
  tables: false
```

Python linting and type-checking rules live in `pyproject.toml`:

```toml
[tool.ruff]
preview = true
line-length = 120
fix = true
output-format = "grouped"

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

The Flake8 config is intentionally narrow and delegates the rule selection to `M511`:

```ini
[flake8]
select=M511
```

Tests are wired through `tox`, but `tox` is only a runner here, not a hosted CI service:

```toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

> **Tip:** This project prefers `prek` over raw `pre-commit`. A hook script blocks direct `pre-commit` commands and tells callers to use the wrapper instead.

The enforcement is explicit in `scripts/rule-enforcer.py`:

```python
def is_forbidden_precommit_command(command: str) -> bool:
    """Check if command uses pre-commit directly instead of prek."""
    cmd = command.strip().lower()

    # Block direct pre-commit commands
    return cmd.startswith("pre-commit ")
```

## CodeRabbit

CodeRabbit is configured in `.coderabbit.yaml` as an assertive reviewer that can request changes and auto-review non-draft pull requests.

```yaml
reviews:
  profile: assertive
  request_changes_workflow: true
  high_level_summary: true
  poem: false
  review_status: true
  collapse_walkthrough: false

  auto_review:
    enabled: true
    drafts: false
```

Its tool integrations are broad:

```yaml
tools:
  ruff:
    enabled: true
  pylint:
    enabled: true
  eslint:
    enabled: true
  shellcheck:
    enabled: true
  yamllint:
    enabled: true
  gitleaks:
    enabled: true
  semgrep:
    enabled: true
  actionlint:
    enabled: true
  hadolint:
    enabled: true
```

The config also points CodeRabbit at the repository's guidance file:

```yaml
knowledge_base:
  code_guidelines:
    enabled: true
    filePatterns:
      - "AI_REVIEW.md"
```

That matters because CodeRabbit is not treated as a generic reviewer here. It is expected to review in the context of this repository's rules and conventions.

### CodeRabbit helper automation

The repo does more than just check in a `.coderabbit.yaml` file. It also includes local helpers for handling CodeRabbit-specific behavior.

For rate limits, `myk_claude_tools/coderabbit/rate_limit.py` looks for CodeRabbit's summary comment, parses the wait time, and can re-trigger a review:

```python
_SUMMARY_MARKER = "<!-- This is an auto-generated comment: summarize by coderabbit.ai -->"
_RATE_LIMITED_MARKER = "<!-- This is an auto-generated comment: rate limited by coderabbit.ai -->"

_WAIT_TIME_RE = re.compile(r"Please wait \*\*(?:(\d+) minutes? and )?(\d+) seconds?\*\*")

_POLL_INTERVAL = 60  # seconds between polls
_MAX_POLL_ATTEMPTS = 10  # max 10 minutes
```

The expected rate-limit message is covered directly in tests:

```python
RATE_LIMITED_BODY = (
    f"{_SUMMARY_MARKER}\n"
    f"{_RATE_LIMITED_MARKER}\n"
    "Please wait **22 minutes and 57 seconds** before requesting another review.\n"
)
```

The CLI exposes two focused commands for this flow:

```bash
myk-claude-tools coderabbit check <owner/repo> <pr_number>
myk-claude-tools coderabbit trigger <owner/repo> <pr_number> --wait <wait_seconds>
```

The repository also accounts for a CodeRabbit quirk that matters in real review sessions: some comments are embedded in the review body instead of appearing as standard inline threads.

```python
def fetch_coderabbit_body_comments(owner: str, repo: str, pr_number: str) -> list[dict[str, Any]]:
    """Fetch CodeRabbit body-embedded comments from review bodies.

    CodeRabbit embeds some comments in the review body text (not as inline threads)
    when they reference code outside the PR diff range or are nitpick-level suggestions.
    This function fetches all CodeRabbit reviews and parses their bodies for these comments.
    """
```

That extra parsing is one reason the repo ships its own review helpers instead of relying on raw GitHub review threads alone.

## Qodo Merge

Qodo Merge is configured in `.pr_agent.toml`. The settings align it with the rest of the project: English-language responses, repository metadata from `AI_REVIEW.md`, and no noise on draft or WIP work.

```toml
[config]
response_language = "en-US"
add_repo_metadata = true
add_repo_metadata_file_list = ["AI_REVIEW.md"]
ignore_pr_title = ["^\\[WIP\\]", "^WIP:", "^Draft:"]
ignore_pr_labels = ["wip", "work-in-progress"]

[github_app]
handle_pr_actions = ["opened", "reopened", "ready_for_review"]
pr_commands = ["/describe", "/review", "/improve"]
feedback_on_draft_pr = false
handle_push_trigger = true
push_commands = ["/review", "/improve"]
```

The review policy is also opinionated:

```toml
require_security_review = true
require_tests_review = true
require_estimate_effort_to_review = false
require_score_review = false
enable_review_labels_security = false
enable_review_labels_effort = false
num_max_findings = 50
persistent_comment = false
```

And code suggestions are scoped toward the kinds of files this repo actually contains:

```toml
[pr_code_suggestions]
extra_instructions = "Focus on Bash script quality (shellcheck, quoting, error handling), Python hook correctness, and Markdown clarity. Follow AI_REVIEW.md orchestrator pattern guidelines."
focus_only_on_problems = false
```

In other words, Qodo Merge is not configured as a generic "review everything the same way" bot. It is pointed at this repository's actual automation surface: Bash hooks, Python scripts, Markdown docs, and repository-specific rules.

### Shared review-handling pipeline

The local tooling in `myk_claude_tools/reviews/` ties Qodo, CodeRabbit, and human reviews together.

Reviewer source detection is explicit:

```python
QODO_USERS = ["qodo-code-review", "qodo-code-review[bot]"]
CODERABBIT_USERS = ["coderabbitai", "coderabbitai[bot]"]
```

Tests lock that behavior in:

```python
assert get_all_reviews.detect_source("qodo-code-review") == "qodo"
assert get_all_reviews.detect_source("qodo-code-review[bot]") == "qodo"
assert get_all_reviews.detect_source("coderabbitai") == "coderabbit"
assert get_all_reviews.detect_source("coderabbitai[bot]") == "coderabbit"
```

The `reviews fetch` command is designed to gather all unresolved review input for the current PR and split it into `human`, `qodo`, and `coderabbit` buckets:

```python
@reviews.command("fetch")
@click.argument("review_url", required=False, default="")
def reviews_fetch(review_url: str) -> None:
    """Fetch unresolved review threads from current PR.

    Fetches ALL unresolved review threads from the current branch's PR
    and categorizes them by source (human, qodo, coderabbit).

    Saves output to /tmp/claude/pr-<number>-reviews.json
    """
```

That data can then be posted back and stored locally for analytics. The storage layer writes to `.claude/data/reviews.db` and keeps per-source counts:

```python
db_path = project_root / ".claude" / "data" / "reviews.db"

# Count comments by source
counts: dict[str, int] = {"human": 0, "qodo": 0, "coderabbit": 0}

# Insert comments from each source
for source in ["human", "qodo", "coderabbit"]:
    comments = data.get(source, [])
    for comment in comments:
        insert_comment(conn, review_id, source, comment)
```

If you use the included GitHub plugin workflow, the repo also exposes a single front door for mixed-source review handling:

```text
/myk-github:review-handler
/myk-github:review-handler https://github.com/owner/repo/pull/123#pullrequestreview-456
/myk-github:review-handler --autorabbit
```

The `--autorabbit` mode is specifically designed to keep processing new CodeRabbit comments in a loop while still treating human and Qodo feedback as separate inputs.

> **Warning:** CodeRabbit and Qodo Merge are review assistants, not merge policy on their own. Because this repo does not ship a local GitHub Actions workflow, required checks and branch protection must be configured outside the repository if you need them.

## Claude Code hooks and session automation

A large part of this repository's automation happens locally when it is used inside Claude Code. `settings.json` wires several hooks into scripts under `~/.claude/scripts/`:

```json
"hooks": {
  "PreToolUse": [
    {
      "matcher": "TodoWrite|Bash",
      "hooks": [
        {
          "type": "command",
          "command": "uv run ~/.claude/scripts/rule-enforcer.py"
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
}
```

Those hooks are not CI in the GitHub Actions sense, but they are part of the project's automation story:

- `rule-enforcer.py` blocks direct `python`, `pip`, and raw `pre-commit` usage.
- `git-protection.py` is invoked before Bash tool use.
- `rule-injector.py` loads rule files on prompt submission.
- `session-start-check.sh` verifies expected tools and plugins are installed.

The session-start check looks for:

- `uv`
- `gh` when the repo has a GitHub remote
- `jq`
- `gawk`
- `prek` when `.pre-commit-config.yaml` is present
- `mcpl`
- required review plugins such as `pr-review-toolkit`, `superpowers`, and `feature-dev`
- optional marketplace plugins including `coderabbit`

This is a good example of how automation in this repository leans toward guardrails and workflow setup rather than a traditional single CI pipeline.

## What the tests confirm

The automation in this repo is backed by unit tests, not just configuration files.

- `tests/test_get_all_reviews.py` verifies reviewer source detection and priority classification.
- `tests/test_coderabbit_rate_limit.py` verifies wait-time parsing and trigger/poll behavior.
- `tests/test_review_db.py` and `tests/test_store_reviews_to_db.py` verify that `qodo` and `coderabbit` data are stored correctly in the review database.
- `tests/test_rule_enforcer.py` verifies that direct `python`, `pip`, and `pre-commit` usage is blocked as intended.

## What this means for users

If you use this repository as intended, think of its automation in four parts:

- Local quality checks come from `prek`, `uv`, `pytest`, `tox`, and Claude Code hooks.
- Hosted hook automation comes from `pre-commit.ci`.
- PR review automation comes from CodeRabbit and Qodo Merge.
- There is no checked-in repository-local CI workflow, so GitHub Actions-style CI is something you add yourself if you need it.

That setup keeps the repository lightweight while still giving you strong linting, typing, review assistance, and workflow guardrails.
