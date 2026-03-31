# Personal CLAUDE.md

Use a personal `CLAUDE.md` when you want Claude to follow your own preferences in this repository without editing shared files like `AI_REVIEW.md`, `rules/`, `scripts/`, or `settings.json`. It is the right place for personal style, communication, environment, and workflow notes.

This repository already includes a starting template in `CLAUDE.md.example`.

## Quick Start

Copy the template and edit it for your own workflow:

```bash
cp CLAUDE.md.example CLAUDE.md
```

The template starts like this:

```markdown
# Personal Claude Configuration Template

This is a template for your personal `CLAUDE.md` file. Copy this to `CLAUDE.md` and customize it to your preferences.

> **Note**: Orchestrator rules (agent routing, delegation, etc.) auto-load from `.claude/rules/` - you don't need to include them here. This file is for YOUR personal preferences only.
```

The template already gives you sections for:

- code style preferences
- communication preferences
- project context
- tools and environment
- custom personal rules
- rule overrides

A real example from the template:

```text
# Example preferences:
- Be concise - skip explanations unless I ask
- Always explain complex decisions
- Use technical terminology freely
- Provide context for breaking changes
- Highlight security implications
```

> **Tip:** Start small. A short `CLAUDE.md` with a few strong preferences is usually more useful than a long list of vague rules.

## Where To Put It

The repository tooling supports either of these locations:

- `CLAUDE.md`
- `.claude/CLAUDE.md`

If both exist, `CLAUDE.md` wins because it is checked first.

Use `CLAUDE.md` when you want the simplest setup. Use `.claude/CLAUDE.md` when you want to keep local AI configuration inside an ignored `.claude/` directory.

## Why It Stays Personal

This repository ignores everything by default and then explicitly re-includes tracked files. The top of `.gitignore` shows the pattern:

```gitignore
# Ignore everything by default
# This config integrates into ~/.claude so we must be explicit about what we track
*

# Core config files
!.coderabbit.yaml
!.gitignore
!LICENSE
!AI_REVIEW.md
!README.md
!settings.json
!statusline.sh
```

`CLAUDE.md` is not whitelisted there, which makes it a good place for local preferences in this repo.

That means you can tune Claude for your own work without creating shared repository changes just to store personal taste.

> **Note:** `CLAUDE.md.example` is the tracked template. Your own `CLAUDE.md` is the personal working copy.

## What Belongs In Personal `CLAUDE.md`

Good things to put here:

- how concise or detailed you want responses
- your preferred editors, shells, runtimes, or package managers
- local workflow habits you want Claude to respect
- project-specific reminders that matter to your daily work
- narrow, well-documented overrides for your own workflow

The template includes practical sections for exactly that:

```text
## Code Style Preferences
## Communication Preferences
## Project Context
## Tools & Environment
## Custom Personal Rules
## Rule Overrides
```

A real tools-and-environment example from the template:

```text
# Example preferences:
- Editor: VSCode with Pylance
- Terminal: zsh with oh-my-zsh
- Container runtime: Podman (not Docker)
- Cloud provider: AWS
- Preferred testing frameworks:
  - Python: pytest
  - JavaScript: Jest
  - Go: standard testing package
```

## How It Is Discovered

The repository’s PR helper looks for `CLAUDE.md` content in a fixed order in `myk_claude_tools/pr/claude_md.py`:

```python
# Check local ./CLAUDE.md
local_claude_md = Path("./CLAUDE.md")
if local_claude_md.is_file():
    print(local_claude_md.read_text(encoding="utf-8"))
    return

# Check local ./.claude/CLAUDE.md
local_claude_dir_md = Path("./.claude/CLAUDE.md")
if local_claude_dir_md.is_file():
    print(local_claude_dir_md.read_text(encoding="utf-8"))
    return

# Fetch upstream CLAUDE.md
content = fetch_from_github(pr_info.owner, pr_info.repo, "CLAUDE.md")

# Fetch upstream .claude/CLAUDE.md
content = fetch_from_github(pr_info.owner, pr_info.repo, ".claude/CLAUDE.md")
```

In practice, the lookup order is:

1. local `./CLAUDE.md`
2. local `./.claude/CLAUDE.md`
3. remote `CLAUDE.md`
4. remote `.claude/CLAUDE.md`

This matters because a personal file in your local clone can be picked up before anything fetched from GitHub.

## How The Repo Uses It

### PR review

The GitHub PR review workflow has an explicit `CLAUDE.md` fetch step:

```bash
myk-claude-tools pr claude-md {pr_number}
```

That content is then passed into the review agents alongside the diff. In other words, if you keep stable review-relevant conventions in your personal `CLAUDE.md`, the review flow can use them.

### Peer review

The ACPX peer review workflow checks whether `CLAUDE.md` exists and, if it does, tells the peer agent to read it:

```text
IMPORTANT: This project has a CLAUDE.md file with coding conventions
and project guidelines. Read it before reviewing. Flag any violations
of those conventions as findings.
```

This makes `CLAUDE.md` useful for conventions you want reviewers to enforce consistently.

> **Warning:** If you ever choose to track a `CLAUDE.md` in another project, its contents may be read by review tooling and fetched remotely. Do not put secrets, tokens, or private credentials in it.

## Using The Rule Overrides Section

The template includes a `Rule Overrides` section for personal, targeted exceptions. These are written as readable instructions, not as a replacement for tracked repo configuration.

Real examples from `CLAUDE.md.example`:

```text
# IGNORE RULE: 20-code-review-loop.md
# Reason: Working on quick prototypes, skip mandatory code review

# OVERRIDE: Allow direct Bash usage
# For simple commands (ls, pwd, cd), allow orchestrator to use Bash directly
# instead of delegating to bash-expert

# ROUTE OVERRIDE: Python tests
# Route Python test execution to test-automator instead of python-expert

# CONDITIONAL: Code review for critical files only
# Only enforce code review for files in: src/core/, src/security/
# Skip review for: tests/, docs/, scripts/
```

The template also shows a more structured style with scope and reason:

```text
# My Custom Workflow Overrides

# 1. Skip code review for documentation
IGNORE RULE: 20-code-review-loop.md
SCOPE: **/*.md, docs/**/*

# 2. Allow direct bash for git commands
OVERRIDE: Git operations can use Bash directly
REASON: Git commands are simple and don't need git-expert delegation
```

When you use overrides:

- keep them narrow
- include a reason
- include scope when possible
- review them periodically
- remove them when they are no longer useful

> **Tip:** If an override would help everyone, it probably belongs in a tracked shared rule instead of your personal file.

## What Personal Overrides Cannot Change

Personal guidance is not the same thing as changing repository enforcement.

For example, `scripts/rule-enforcer.py` denies direct `python`, `python3`, `pip`, `pip3`, and `pre-commit` commands in favor of `uv`, `uvx`, and `prek`:

```python
def is_forbidden_python_command(command: str) -> bool:
    cmd = command.strip().lower()

    # Allow uv/uvx commands
    if cmd.startswith(("uv ", "uvx ")):
        return False

    # Block direct python/pip
    forbidden = ("python ", "python3 ", "pip ", "pip3 ")
    return cmd.startswith(forbidden)


def is_forbidden_precommit_command(command: str) -> bool:
    cmd = command.strip().lower()

    # Block direct pre-commit commands
    return cmd.startswith("pre-commit ")
```

The test suite confirms that behavior in `tests/test_rule_enforcer.py`: commands like `python script.py` and `pre-commit run --all-files` are denied, while `uv run script.py`, `uvx ruff check .`, and `prek run --all-files` are allowed.

So a personal note like “use `python` directly” does not override that hook. Shared hook behavior still lives in tracked configuration and scripts.

## Keep Shared Changes Separate

Use this rule of thumb:

| Put it in personal `CLAUDE.md` | Change a tracked shared file instead |
|---|---|
| response tone and detail level | team-wide documentation or project guidance |
| preferred editor, shell, runtime, package manager | shared hooks and permissions |
| local workflow preferences | repository rule files in `rules/` |
| narrow personal overrides | `settings.json` behavior |
| personal reminders for review | shared project context in `AI_REVIEW.md` |

This also applies to automated checks. Repository validation is configured separately in `.pre-commit-config.yaml`, for example:

```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  hooks:
    - id: ruff
    - id: ruff-format

- repo: https://github.com/pre-commit/mirrors-mypy
  hooks:
    - id: mypy

- repo: https://github.com/igorshubovych/markdownlint-cli
  hooks:
    - id: markdownlint
```

Your personal `CLAUDE.md` can ask Claude to write in a certain style, but it does not disable tracked linting, typing, or documentation checks.

## Optional Plugin Support

The repo enables the official `claude-md-management` plugin in `settings.json`:

```json
"enabledPlugins": {
  "claude-md-management@claude-plugins-official": true
}
```

The session-start check also looks for `claude-md-management` as an optional plugin. That means the repository is ready to work well with the official `CLAUDE.md` management tooling, but you can still use the template and lookup behavior without editing shared repository files.

## Recommended Workflow

1. Copy `CLAUDE.md.example` to `CLAUDE.md`.
2. Remove sections you do not need.
3. Add only the preferences you actually care about.
4. Put stable review-relevant conventions in the file if you want PR and peer-review tools to use them.
5. Keep shared policy changes out of it and update tracked repo files only when you intentionally want to change behavior for everyone.

A good personal `CLAUDE.md` is short, specific, and local. It should make Claude easier to work with for you, without turning personal preferences into shared repository policy.
