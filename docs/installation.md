# Installation

This repository is meant to become your Claude Code home directory. Installing it gives you the project’s `settings.json`, hook scripts, custom status line, bundled `myk-claude-tools` CLI integration, and the bundled plugins `myk-github`, `myk-review`, and `myk-acpx`.

## Before You Start

You need a working Claude Code installation plus a few local tools.

- `uv` is required. The hook configuration runs Python scripts with `uv run ~/.claude/scripts/...`.
- Python `3.10+` is required by the bundled CLI package.
- `gh` is needed for GitHub workflows such as PR review and release commands. The session-start check only flags it when the repo you open uses a GitHub remote.
- `jq` is used by the status line, notification script, and review handlers.
- `gawk`, `prek`, and `mcpl` are optional, but the session-start check will tell you when they matter.
- `notify-send` is required if you want the built-in desktop notifications from `my-notifier.sh`.

> **Note:** This configuration intentionally prefers `uv` and `uvx` over direct `python`, `pip`, and `pre-commit` commands. The rule-enforcer hook blocks those direct commands.

## 1. Install the Repo as `~/.claude`

The shipped `settings.json` uses fixed paths under `~/.claude`, so the repository needs to live there.

For a fresh install:

```bash
git clone https://github.com/myk-org/claude-code-config ~/.claude
```

If you already have a Claude Code home directory, back it up first:

```bash
mv ~/.claude ~/.claude.backup.$(date +%Y%m%d%H%M%S)
git clone https://github.com/myk-org/claude-code-config ~/.claude
```

> **Warning:** Do not clone this repo into a nested path such as `~/.claude/claude-code-config`. The configured hook and status-line commands point to `~/.claude/...` directly.

These paths come straight from the repository’s `settings.json`:

```json
{
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
}
```

## 2. Use This Repo’s `settings.json` and Scripts

The simplest installation is to use this repository’s `settings.json` as your `~/.claude/settings.json`.

That file does more than turn hooks on. It also wires up permissions, enables plugins, and registers extra marketplaces. If you merge it by hand instead of replacing your file, keep these sections aligned:

- `hooks`
- `statusLine`
- `permissions.allow`
- `allowedTools`
- `enabledPlugins`
- `extraKnownMarketplaces`

This note is already embedded in the shipped settings:

```json
{
  "_scriptsNote": "Script entries must be duplicated in both permissions.allow and allowedTools arrays. When adding new scripts, update BOTH locations."
}
```

The same file already enables the bundled plugins once they are installed:

```json
{
  "enabledPlugins": {
    "myk-review@myk-org": true,
    "myk-github@myk-org": true,
    "myk-acpx@myk-org": true,
    "pr-review-toolkit@claude-plugins-official": true,
    "superpowers@claude-plugins-official": true,
    "feature-dev@claude-plugins-official": true
  }
}
```

> **Note:** `settings.json` also defines `cli-anything` and `worktrunk` under `extraKnownMarketplaces`. Those entries make the marketplaces known to Claude Code, but they do not install any plugins by themselves.

## 3. Install the Bundled CLI

Several bundled plugin commands explicitly check for `myk-claude-tools` and tell you to install it with `uv tool install myk-claude-tools`.

The CLI package metadata in this repo looks like this:

```toml
[project]
name = "myk-claude-tools"
requires-python = ">=3.10"

[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

Its entrypoint registers these top-level command groups:

```python
cli.add_command(coderabbit_commands.coderabbit, name="coderabbit")
cli.add_command(db_commands.db, name="db")
cli.add_command(pr_commands.pr, name="pr")
cli.add_command(release_commands.release, name="release")
cli.add_command(reviews_commands.reviews, name="reviews")
```

Install it with `uv`:

```bash
uv tool install myk-claude-tools
myk-claude-tools --version
```

## 4. Add the Plugin Marketplaces and Install the Plugins

This repository ships its own marketplace manifest. The bundled plugins are defined there:

```json
{
  "name": "myk-org",
  "plugins": [
    {
      "name": "myk-github",
      "source": "./plugins/myk-github"
    },
    {
      "name": "myk-review",
      "source": "./plugins/myk-review"
    },
    {
      "name": "myk-acpx",
      "source": "./plugins/myk-acpx"
    }
  ]
}
```

Add the marketplace for this repo and install the bundled plugins:

```text
/plugin marketplace add myk-org/claude-code-config
/plugin install myk-github@myk-org
/plugin install myk-review@myk-org
/plugin install myk-acpx@myk-org
```

The session-start hook also treats three official review plugins as critical. That list comes straight from `session-start-check.sh`:

```bash
critical_marketplace_plugins=(
  pr-review-toolkit
  superpowers
  feature-dev
)
```

Install them from the official marketplace:

```text
/plugin marketplace add claude-plugins-official
/plugin install pr-review-toolkit@claude-plugins-official
/plugin install superpowers@claude-plugins-official
/plugin install feature-dev@claude-plugins-official
```

`settings.json` also enables additional official plugins such as `github`, `pyright-lsp`, `gopls-lsp`, `jdtls-lsp`, `lua-lsp`, `code-review`, `code-simplifier`, `frontend-design`, `coderabbit`, `commit-commands`, `claude-md-management`, `claude-code-setup`, `playground`, and `security-guidance`. You can install those as needed; the session-start check reports missing optional marketplace plugins and prints the exact `/plugin install` commands for them.

> **Note:** `myk-acpx` has one extra prerequisite. Its command file checks for `acpx` and recommends this install if it is missing.

```bash
npm install -g acpx@latest
```

## 5. Restart Claude Code and Verify the Install

Start a new Claude Code session after installing the repo, CLI, and plugins.

A quick verification checklist:

- `myk-claude-tools --help` works and the CLI is on your `PATH`.
- The session-start check does not report missing **CRITICAL** items.
- The custom status line appears.
- These bundled commands are available: `/myk-review:local`, `/myk-review:query-db`, `/myk-github:pr-review`, `/myk-github:review-handler`, `/myk-github:release`, and `/myk-acpx:prompt`.

> **Tip:** The status line script uses `jq` to read Claude Code’s JSON input. If the status line is blank or errors out, install `jq` first.

## What to Expect After Installation

Once the configuration is active, Claude Code will automatically:

- run a session-start check for required tools and critical plugins
- inject the repo’s prompt-time rule reminder hook
- enforce command guardrails around Python, `pip`, and `pre-commit`
- protect `main` and `master` from direct commits and pushes
- show a custom status line from `statusline.sh`

If you use the review tooling, review analytics are stored per project, not under your home directory. The database lives here:

```text
<project-root>/.claude/data/reviews.db
```

The storage code creates that directory if needed, and the test suite confirms the database is created there and appended to on later runs.

## Troubleshooting

### `uv` is missing or Python commands are blocked

This is expected. The rule-enforcer hook allows `uv` and `uvx` but blocks direct `python`, `python3`, `pip`, and `pip3`:

```python
if cmd.startswith(("uv ", "uvx ")):
    return False

forbidden = ("python ", "python3 ", "pip ", "pip3 ")
```

If you hit that guardrail:

- install `uv`
- run Python scripts with `uv run`
- run CLI tools with `uvx` when appropriate
- use `prek`, not `pre-commit`, if you want the pre-commit workflow this repo expects

### Notifications fail

The bundled notification script checks for both `jq` and `notify-send`. If you do not have `notify-send`, desktop notifications will fail.

> **Note:** If you do not want desktop notifications, remove or replace the `Notification` hook in `~/.claude/settings.json` after installation.

### Git commits or pushes are blocked

That is expected too. `git-protection.py` is designed to stop commits and pushes on `main`, `master`, and branches that are already merged. The intended workflow is to work on a feature branch.

> **Tip:** If Claude Code tells you a commit or push was blocked on a protected branch, create a feature branch and continue there. The test suite in this repo confirms that behavior.

### No CI/CD setup is required

This repository does not ship any `.github/workflows` files. Installation is entirely local to your Claude Code environment.
