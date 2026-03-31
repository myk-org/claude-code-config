# Skills and Templates

This repository ships two reusable skills and a full personal Claude configuration template.

The skills live in `skills/`. The template is the repository itself: tracked files are designed to live under `~/.claude`, with `settings.json`, hook scripts, a custom status line, and bundled plugin metadata all working together.

## What ships with this repository

The tracked `skills/` entries are explicitly whitelisted in `.gitignore`, which makes it easy to see what is part of the shared setup:

```gitignore
# This config integrates into ~/.claude so we must be explicit about what we track
*

# skills/
!skills/
!skills/agent-browser/
!skills/agent-browser/SKILL.md
!skills/docsfy-generate-docs/
!skills/docsfy-generate-docs/SKILL.md
```

That gives you three main building blocks:

- `skills/agent-browser/SKILL.md` for browser automation
- `skills/docsfy-generate-docs/SKILL.md` for docsfy-powered documentation generation
- A personal Claude configuration template built around `settings.json`, `scripts/`, `statusline.sh`, and `.claude-plugin/marketplace.json`

> **Note:** There is no separate “template file.” The repository layout itself is the template, and several paths in `settings.json` assume these files are available under `~/.claude`.

## Browser automation skill

The `agent-browser` skill is for tasks where Claude needs to drive a real browser: testing flows, filling forms, taking screenshots, recording demos, or extracting page data.

Its front matter makes the intent clear:

```yaml
---
name: agent-browser
description: >-
  Automates browser interactions for web testing, form filling, screenshots,
  and data extraction. Use when the user needs to navigate websites, interact
  with web pages, fill forms, take screenshots, test web applications, or
  extract information from web pages.
allowed-tools: Bash(agent-browser:*)
---
```

### Quick start

The skill recommends a simple loop: open a page, inspect the interactive elements, act on those element references, and re-snapshot when the page changes.

```bash
agent-browser open <url>        # Navigate to page
agent-browser snapshot -i       # Get interactive elements with refs
agent-browser click @e1         # Click element by ref
agent-browser fill @e2 "text"   # Fill input by ref
agent-browser close             # Close browser
```

### What it can do

You can use `agent-browser` for a lot more than basic clicking:

- Navigate with `open`, `back`, `forward`, and `reload`
- Inspect the page with `snapshot`, including interactive-only mode
- Interact with elements using refs like `@e1`
- Read content with `get text`, `get html`, `get value`, and `get attr`
- Capture screenshots, PDFs, videos, traces, and console output
- Work with cookies, storage, tabs, windows, frames, and network routing
- Save and restore browser state between sessions

Here are a few examples pulled directly from the skill:

```bash
agent-browser screenshot path.png
agent-browser screenshot --full
agent-browser pdf output.pdf
agent-browser record start ./demo.webm
agent-browser record stop
```

```bash
agent-browser state save auth.json
agent-browser state load auth.json
agent-browser --session test1 open site-a.com
agent-browser session list
```

```bash
agent-browser find role button click --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "user@test.com"
```

### Practical workflow

For most UI tasks, the best pattern is:

1. Open the page.
2. Run `agent-browser snapshot -i`.
3. Use the returned refs such as `@e1` and `@e2`.
4. Re-run `snapshot -i` after navigation or a large DOM update.

> **Tip:** `snapshot -i` is the default starting point for real work. It gives you stable references for the elements Claude should interact with.

The skill also supports JSON output when you want machine-readable results:

```bash
agent-browser snapshot -i --json
agent-browser get text @e1 --json
```

> **Note:** Video recording starts a fresh browser context but preserves cookies and storage from your session, so it is useful for clean demos without forcing you to log in again.

## docsfy documentation generation skill

The `docsfy-generate-docs` skill is for creating AI-generated documentation for a Git repository using the `docsfy` CLI and a running docsfy server.

The skill is opinionated in a useful way: it treats documentation generation as a workflow, not just a single command.

### Prerequisites

Before generating anything, the skill checks two things:

```bash
docsfy --help
docsfy health
```

If `docsfy` is missing, the skill points to:

```bash
uv tool install docsfy
```

If the server is unavailable, the skill tells you to check or initialize the docsfy configuration:

```bash
docsfy-server
docsfy config show
docsfy config init
```

### Generation workflow

The core generation command is:

```bash
docsfy generate <repo_url> --branch <branch> --provider <provider> --model <model> --watch [--force]
```

A few details matter here:

- The skill always uses `--watch` so progress is visible in real time.
- The repository is passed as a Git URL, not a local folder.
- The provider and model are not guessed.

> **Note:** The skill explicitly says to ask for the AI provider and model instead of hardcoding them. The supported provider examples in the skill are `claude`, `gemini`, and `cursor`.

### Branching and download

Once generation reaches `ready`, the skill creates a docs branch before downloading the generated files:

```bash
git fetch origin <branch>
git checkout -B docs/docsfy-<project_name> origin/<branch>
```

Then it downloads the generated documentation:

```bash
docsfy download <project_name> --branch <branch> --provider <provider> --model <model> --output <output_dir>
```

The docsfy output arrives in a nested folder, so the skill flattens it:

```bash
ls <output_dir>/<project>-<branch>-<provider>-<model>/
mv <output_dir>/<project>-<branch>-<provider>-<model>/* <output_dir>/ || true
mv <output_dir>/<project>-<branch>-<provider>-<model>/.* <output_dir>/ 2>/dev/null || true
rm -rf <output_dir>/<project>-<branch>-<provider>-<model>
```

> **Warning:** The skill expects a nested download directory and removes it after flattening. If that folder does not exist, your project name, branch, provider, or model probably does not match the generation job you started.

### GitHub Pages support

When the target repository is on GitHub, the skill can check whether GitHub Pages is already serving from `docs/`:

```bash
gh api repos/<owner>/<repo>/pages --jq '.source' 2>/dev/null
```

If Pages is not configured, the skill can set it up like this:

```bash
gh api repos/<owner>/<repo>/pages -X POST -f "source[branch]=<branch>" -f "source[path]=/docs"
```

If Pages is serving from `docs/`, the skill also supports a follow-up step: simplifying the root `README.md` so it points readers to the generated docs site.

> **Tip:** This skill is best when you want a fast first version of a docs site for an existing repository. It already accounts for generation, branching, download, Pages checks, and post-generation cleanup.

## The personal Claude configuration template

The repository is built as a reusable `~/.claude` setup. You can see that directly in `settings.json`, where the hooks and status line call scripts from `~/.claude`:

```json
"hooks": {
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
},
"statusLine": {
  "type": "command",
  "command": "bash ~/.claude/statusline.sh",
  "padding": 0
}
```

### What this template gives you

If you adopt this template, you get:

- Session startup checks for required tools and plugins
- Prompt-time rule injection
- Command guardrails for Python, pip, and pre-commit
- Git branch and PR protection for commit and push operations
- A custom status line
- Desktop notifications
- Bundled marketplace plugins

### Session startup checks

Every session runs `scripts/session-start-check.sh`. It checks for:

- `uv` as a critical dependency
- `gh` when the current repo uses GitHub
- `jq`
- `gawk`
- `prek` when `.pre-commit-config.yaml` exists
- `mcpl` for MCP Launchpad
- critical review plugins: `pr-review-toolkit`, `superpowers`, and `feature-dev`

A representative excerpt:

```bash
# CRITICAL: uv - Required for Python hooks
if ! command -v uv &>/dev/null; then
  missing_critical+=("[CRITICAL] uv - Required for running Python hooks
  Install: https://docs.astral.sh/uv/")
fi

# OPTIONAL: mcpl - MCP Launchpad (always check)
if ! command -v mcpl &>/dev/null; then
  missing_optional+=("[OPTIONAL] mcpl - MCP Launchpad for MCP server access
  Install: https://github.com/kenneth-liao/mcp-launchpad")
fi
```

This means the template does more than define preferences. It checks whether the environment can actually support the workflows it expects.

### Prompt injection and guardrails

The template uses a `UserPromptSubmit` hook to add an orchestration reminder before each request. It also uses `PreToolUse` hooks to block unsafe or off-pattern commands.

The `rule-enforcer.py` hook blocks direct Python, pip, and pre-commit usage:

```python
# Allow uv/uvx commands
if cmd.startswith(("uv ", "uvx ")):
    return False

# Block direct python/pip
forbidden = ("python ", "python3 ", "pip ", "pip3 ")
return cmd.startswith(forbidden)
```

```python
def is_forbidden_precommit_command(command: str) -> bool:
    """Check if command uses pre-commit directly instead of prek."""
    cmd = command.strip().lower()

    # Block direct pre-commit commands
    return cmd.startswith("pre-commit ")
```

In practice, that means this template expects you to use:

- `uv run ...` instead of `python ...`
- `uvx ...` for one-off Python CLI tools
- `prek ...` instead of `pre-commit ...`

> **Warning:** If you are used to typing `python`, `pip`, or `pre-commit` directly, this template will stop you. That is intentional.

### Git safety

The Git protection hook is another important part of the template. Its own docstring summarizes the behavior well:

```python
"""PreToolUse hook - prevents commits and pushes on protected branches.

This hook intercepts git commit and push commands and blocks them if:
1. The current branch is already merged into the main branch
2. The current branch is the main/master branch itself

Allows commits on:
- Unmerged branches
- Amended commits that haven't been pushed yet
"""
```

For GitHub repositories, it also checks whether the current branch already has a merged PR by using `gh pr list --head <branch> --state merged`. If that PR is already merged, further commits and pushes from the same branch are blocked.

This is backed up by the test suite in `tests/test_git_protection.py`, so the behavior is enforced and verified rather than just described.

### Status line and notifications

The custom status line is wired through `settings.json` and built in `statusline.sh`. It shows the current directory, optional SSH user and host, Git branch, active virtual environment, model name, context usage, and line-change totals.

A shortened excerpt from `statusline.sh`:

```bash
# Add directory name
status_parts+=("$dir_name")

# Add git branch if in a git repository
if git rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null || echo "detached")
    status_parts+=("$branch")
fi

status_parts+=("$model_name")
if [ -n "$context_pct" ]; then
    status_parts+=("(${context_pct}%)")
fi
```

The notification hook uses `notify-send` and `jq`, so desktop notifications are part of the template too.

### Plugin marketplace entries

The repository publishes three bundled plugins through `.claude-plugin/marketplace.json`:

| Plugin | Description |
|------|------|
| `myk-github` | GitHub operations, including PR reviews, releases, review handling, and CodeRabbit rate limits |
| `myk-review` | Local code review and review database operations |
| `myk-acpx` | Multi-agent prompt execution through `acpx` |

The `myk-acpx` plugin is especially useful if you want to send the same prompt to multiple coding agents. Its command file includes examples like:

```text
/myk-acpx:prompt codex fix the tests
/myk-acpx:prompt cursor review this code
/myk-acpx:prompt gemini explain this function
/myk-acpx:prompt codex --exec summarize this repo
/myk-acpx:prompt cursor,codex review this code
/myk-acpx:prompt cursor,gemini,codex --peer review the architecture
```

> **Note:** The `myk-acpx` command supports multiple agents, but `--fix`, `--peer`, and `--exec` have compatibility rules. For example, multi-agent mode cannot be combined with `--fix`.

### Template defaults worth knowing about

A few defaults in `settings.json` are easy to miss but matter in daily use:

```json
"env": {
  "DISABLE_TELEMETRY": "1",
  "DISABLE_ERROR_REPORTING": "1",
  "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1"
}
```

The template also keeps a large `enabledPlugins` list turned on, including official review, language server, and setup plugins alongside the `myk-*` plugins.

> **Tip:** When you customize the template, keep the directory structure stable under `~/.claude`. The hook and status-line paths are hardcoded around that layout.

## Customizing this template safely

Two details are especially important if you plan to extend the setup.

First, `settings.json` includes this reminder:

```json
"_scriptsNote": "Script entries must be duplicated in both permissions.allow and allowedTools arrays. When adding new scripts, update BOTH locations."
```

Second, the repository uses an allowlist-style `.gitignore`, which means local-only files can live beside tracked files without being committed by accident.

That is a good fit for personal configuration because you can keep:

- shared, reusable config in version control
- machine-specific or experimental files untracked

## Validation and maintenance

This repository validates the template with tests and pre-commit tooling.

`tox.toml` runs the Python test suite through `uv`:

```toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

The pre-commit configuration covers formatting, linting, type checking, documentation linting, and secret scanning. Included tools and hooks include:

- `ruff`
- `ruff-format`
- `mypy`
- `flake8`
- `markdownlint`
- `detect-secrets`
- `gitleaks`
- standard `pre-commit-hooks` checks such as merge conflicts, docstrings, TOML, and EOF fixes

> **Tip:** In this setup, use `prek` instead of calling `pre-commit` directly. That matches the template’s guardrails and avoids the `rule-enforcer.py` block.

## Summary

Use this repository when you want both reusable skills and a structured personal Claude setup.

Use the skills when you need Claude to:

- drive a browser with `agent-browser`
- generate project documentation with `docsfy`

Use the template when you want Claude to:

- start with environment checks
- follow consistent tool rules
- avoid unsafe Git operations
- surface more context in the status line
- work with a curated plugin set

If you keep the `~/.claude` layout intact, the pieces fit together cleanly and give you a configuration that is practical for day-to-day use, not just a collection of isolated files.
