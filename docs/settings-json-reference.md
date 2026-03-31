# settings.json Reference

`settings.json` is the root Claude Code configuration for this repository. It defines what Claude Code is allowed to do, which hooks run, which plugins are enabled, and which environment and UI defaults are applied.

> **Note:** This file is written to work with companion files under `~/.claude/`. Every hook command points at `~/.claude/scripts/...`, and the status line points at `~/.claude/statusline.sh`. If you want to use this configuration unchanged, make sure those files exist at those paths.

```1:3:settings.json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "includeCoAuthoredBy": false,
```

The schema line gives editors JSON Schema validation and autocomplete. `includeCoAuthoredBy: false` disables automatic `Co-authored-by` trailers.

## What This File Controls

- Tool permissions and Bash allowlists
- Session startup checks
- Pre-tool safety hooks
- Prompt submission behavior
- Desktop notifications
- Enabled plugins and extra marketplaces
- Status-line rendering
- Environment flags and feedback settings

## Permissions

The first safety layer is `permissions.allow`. It is intentionally narrow: direct file access is limited to `/tmp/claude/**`, and only a small set of Bash command patterns are pre-approved.

```4:23:settings.json
"permissions": {
  "allow": [
    "Read(/tmp/claude/**)",
    "Edit(/tmp/claude/**)",
    "Write(/tmp/claude/**)",
    "Bash(mkdir -p /tmp/claude*)",
    "Bash(claude:*)",
    "Bash(sed -n:*)",
    "Bash(grep:*)",
    "Bash(mcpl:*)",
    "Bash(git -C:*)",
    "Bash(prek:*)",
    "Bash(~/.claude/scripts/session-start-check.sh:*)",
    "Bash(~/.claude/scripts/my-notifier.sh:*)",
    "Bash(uv run ~/.claude/scripts/rule-injector.py:*)",
    "Bash(uv run ~/.claude/scripts/rule-enforcer.py:*)",
    "Bash(uv run ~/.claude/scripts/git-protection.py:*)",
    "Grep",
    "Bash(myk-claude-tools:*)"
  ]
},
```

In practice, that gives you these categories of access:

- Temporary workspace access: `Read`, `Edit`, and `Write` only under `/tmp/claude/**`
- Approved shell entry points: `claude`, `sed -n`, `grep`, `mcpl`, `git -C`, `prek`, and `myk-claude-tools`
- Hook entry points: the startup checker, notifier, and Python hook scripts
- Native search access: the built-in `Grep` tool

A few details are worth calling out:

- `git` access is narrow here: the allowlist includes `Bash(git -C:*)`, not a blanket `Bash(git:*)`
- `pre-commit` is not allowlisted directly; this config expects `prek`
- The repo-specific `myk-claude-tools` command is a real CLI entry point defined in `pyproject.toml`

```23:24:pyproject.toml
[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

## The Duplicate Allowlist

This repository keeps a second allowlist in `allowedTools`. The checked-in file treats it as a mirror of the same approved tool set, and the file includes an explicit reminder to keep script entries synchronized.

```137:156:settings.json
"_scriptsNote": "Script entries must be duplicated in both permissions.allow and allowedTools arrays. When adding new scripts, update BOTH locations.",
"allowedTools": [
  "Edit(/tmp/claude/**)",
  "Write(/tmp/claude/**)",
  "Read(/tmp/claude/**)",
  "Bash(mkdir -p /tmp/claude*)",
  "Bash(claude:*)",
  "Bash(sed -n:*)",
  "Bash(grep:*)",
  "Bash(mcpl:*)",
  "Bash(git -C:*)",
  "Bash(prek:*)",
  "Grep",
  "Bash(~/.claude/scripts/session-start-check.sh:*)",
  "Bash(~/.claude/scripts/my-notifier.sh:*)",
  "Bash(uv run ~/.claude/scripts/rule-injector.py:*)",
  "Bash(uv run ~/.claude/scripts/rule-enforcer.py:*)",
  "Bash(uv run ~/.claude/scripts/git-protection.py:*)",
  "Bash(myk-claude-tools:*)"
],
```

> **Warning:** If you add, remove, or rename a script-based command, update both `permissions.allow` and `allowedTools`. Updating only one of them is a common way to break this configuration.

A practical way to think about this is: there is one logical allowlist, but this file stores it twice.

## Hooks

The `hooks` block is where most of the behavior lives. This configuration uses four hook phases.

| Hook event | Matcher | Runs | Purpose |
|---|---|---|---|
| `SessionStart` | `""` | `~/.claude/scripts/session-start-check.sh` | Checks tool and plugin prerequisites |
| `UserPromptSubmit` | `""` | `uv run ~/.claude/scripts/rule-injector.py` | Injects a short reminder into prompt context |
| `PreToolUse` | `TodoWrite|Bash` | `uv run ~/.claude/scripts/rule-enforcer.py` | Denies raw `python`, `pip`, and `pre-commit` usage |
| `PreToolUse` | `Bash` | `uv run ~/.claude/scripts/git-protection.py` | Blocks unsafe `git commit` and `git push` usage |
| `PreToolUse` | `Bash` | inline `prompt` hook | Blocks or asks about dangerous OS-level commands |
| `Notification` | `""` | `~/.claude/scripts/my-notifier.sh` | Sends desktop notifications |

> **Note:** Every Python hook is run through `uv run`, so `uv` is a hard requirement for this setup.

### SessionStart

The startup hook is a non-blocking health check. It looks for required tools, optional helpers, and a set of official plugins.

```29:66:scripts/session-start-check.sh
# CRITICAL: uv - Required for Python hooks
if ! command -v uv &>/dev/null; then
  missing_critical+=("[CRITICAL] uv - Required for running Python hooks
  Install: https://docs.astral.sh/uv/")
fi

# OPTIONAL: gh - Only check if this is a GitHub repository
if git remote -v 2>/dev/null | grep -q "github.com"; then
  if ! command -v gh &>/dev/null; then
    missing_optional+=("[OPTIONAL] gh - Required for GitHub operations (PRs, issues, releases)
  Install: https://cli.github.com/")
  fi
fi

# OPTIONAL: jq - Required for AI review handlers
if ! command -v jq &>/dev/null; then
  missing_optional+=("[OPTIONAL] jq - Required for AI review handlers (JSON processing)
  Install: https://stedolan.github.io/jq/download/")
fi

# OPTIONAL: gawk - Required for AI review handlers
if ! command -v gawk &>/dev/null; then
  missing_optional+=("[OPTIONAL] gawk - Required for AI review handlers (text processing)
```

The same script also checks for review-critical plugins and a wider set of optional official plugins:

```69:131:scripts/session-start-check.sh
# CRITICAL: Review plugins - Required for mandatory code review loop
critical_marketplace_plugins=(
  pr-review-toolkit
  superpowers
  feature-dev
)

# OPTIONAL: Marketplace plugins - Check @claude-plugins-official plugins
optional_marketplace_plugins=(
  claude-code-setup
  claude-md-management
  code-review
  code-simplifier
  coderabbit
  commit-commands
  frontend-design
  github
  gopls-lsp
  jdtls-lsp
  lua-lsp
  playground
  pyright-lsp
  security-guidance
)
```

If anything is missing, the script prints a structured `MISSING_TOOLS_REPORT` and tells the assistant to offer installation help. It never blocks the session.

```134:166:scripts/session-start-check.sh
# Output report only if something is missing
if [[ ${#missing_critical[@]} -gt 0 || ${#missing_optional[@]} -gt 0 ]]; then
  echo "MISSING_TOOLS_REPORT:"
  echo ""
  echo "[AI INSTRUCTION - YOU MUST FOLLOW THIS]"
  echo "Some tools required by this configuration are missing."
  echo ""
  echo "Criticality levels:"
  echo "- CRITICAL: Configuration will NOT work without these. Must install."
  echo "- OPTIONAL: Enhances functionality. Nice to have."
  # ...
fi

# Always exit 0 (non-blocking)
exit 0
```

A few practical takeaways:

- `uv` is mandatory because the Python hooks use it
- `gh` is only checked when the repo remote points at GitHub
- `prek` is only checked when `.pre-commit-config.yaml` exists, and this repository does include that file
- `mcpl`, `jq`, and `gawk` are optional, but they support real parts of this setup

> **Tip:** Install `uv` first. If you want the review workflow to work cleanly, install `pr-review-toolkit`, `superpowers`, and `feature-dev` next.

### UserPromptSubmit

The prompt-submit hook injects a fixed reminder string into the prompt context.

```22:32:scripts/rule-injector.py
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

That means the current checked-in implementation reinforces behavior with a static reminder rather than dynamically editing the user's prompt.

### PreToolUse: `rule-enforcer.py`

The first `PreToolUse` hook is a Bash gate. It blocks direct `python`, `python3`, `pip`, `pip3`, and `pre-commit` commands. It explicitly allows `uv` and `uvx`, and the overall workflow prefers `prek` over raw `pre-commit`.

```8:26:scripts/rule-enforcer.py
def is_forbidden_python_command(command: str) -> bool:
    """Check if command uses python/pip directly instead of uv."""
    cmd = command.strip().lower()

    # Allow uv/uvx commands
    if cmd.startswith(("uv ", "uvx ")):
        return False

    # Block direct python/pip
    forbidden = ("python ", "python3 ", "pip ", "pip3 ")
    return cmd.startswith(forbidden)

def is_forbidden_precommit_command(command: str) -> bool:
    """Check if command uses pre-commit directly instead of prek."""
    cmd = command.strip().lower()

    # Block direct pre-commit commands
    return cmd.startswith("pre-commit ")
```

The tests are a good example of the intended contract:

```368:442:tests/test_rule_enforcer.py
@pytest.mark.parametrize(
    "command",
    [
        "python script.py",
        "python3 -m pytest",
        "pip install requests",
        "pip3 freeze",
    ],
)
def test_deny_forbidden_bash_command(self, command: str) -> None:
    # ...

@pytest.mark.parametrize(
    "command",
    [
        "pre-commit run",
        "pre-commit run --all-files",
        "pre-commit install",
        "pre-commit autoupdate",
    ],
)
def test_deny_forbidden_precommit_command(self, command: str) -> None:
    # ...

@pytest.mark.parametrize(
    "command",
    [
        "uv run script.py",
        "uvx ruff check .",
        "git status",
        "ls -la",
    ],
)
def test_allow_permitted_bash_command(self, command: str) -> None:
```

One subtle detail: the hook matcher is `TodoWrite|Bash`, but the script itself only inspects `Bash` commands.

> **Tip:** If you are adapting this config, prefer `uv run`, `uvx`, and `prek` in your own commands. That matches both the hook behavior and the startup checks.

### PreToolUse: `git-protection.py`

The second `PreToolUse` hook protects Git history. It blocks commits and pushes on protected branches, already-merged branches, and branches whose PRs are already merged.

The script also fails closed when PR-state lookup errors occur:

```287:291:scripts/git-protection.py
pr_merged, pr_info = get_pr_merge_status(current_branch)
if pr_merged is None:
    # Error checking PR status - fail closed
    return True, format_pr_merge_error("get_pr_merge_status()", pr_info)
```

The tests show the intended behavior clearly:

```727:775:tests/test_git_protection.py
def test_detached_head(self, mock_is_repo: Any, mock_branch: Any) -> None:
    """Detached HEAD should block commit."""
    mock_is_repo.return_value = True
    mock_branch.return_value = None
    should_block, reason = git_protection.should_block_commit('git commit -m "test"')
    assert should_block is True
    assert "detached HEAD" in reason

def test_on_main_branch(self, mock_is_repo: Any, mock_branch: Any, mock_pr_status: Any, mock_main: Any) -> None:
    """On main branch should block commit."""
    mock_is_repo.return_value = True
    mock_branch.return_value = "main"
    mock_pr_status.return_value = (False, None)
    mock_main.return_value = "main"
    should_block, reason = git_protection.should_block_commit('git commit -m "test"')
    assert should_block is True
    assert "'main'" in reason
    assert "protected" in reason.lower()
```

There is one important exception: `--amend` is allowed when the branch is ahead of its remote.

```253:255:scripts/git-protection.py
def is_amend_with_unpushed_commits(command: str) -> bool:
    """Check if this is an amend on unpushed commits (which should be allowed)."""
    return "--amend" in command and is_branch_ahead_of_remote()
```

> **Warning:** On GitHub repositories, this hook uses `gh` to check whether the current branch already has a merged PR. If that lookup fails, the hook blocks the operation. If you rely on GitHub workflows, make sure `gh` is installed and authenticated.

### PreToolUse: destructive command gate

The third `PreToolUse` hook is an inline prompt-based safety check. It is not a shell script. It analyzes Bash commands and does three things:

- Blocks obviously catastrophic OS-destructive commands
- Asks for confirmation on commands that look risky but not clearly catastrophic
- Approves normal commands

The configured timeout is 10 seconds.

This is important because the config also enables `skipDangerousModePermissionPrompt`, so Bash safety here is handled by the allowlists and `PreToolUse` hooks rather than relying only on the default dangerous-mode flow.

### Notification

The notification hook sends the Claude message text through `notify-send`. It explicitly requires both `jq` and `notify-send`.

```4:35:scripts/my-notifier.sh
# Check for required commands
for cmd in jq notify-send; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: Required command '$cmd' not found" >&2
        exit 1
    fi
done

# Read JSON input from stdin
input_json=$(cat)

# Parse JSON and extract message, capturing any jq errors
if ! notification_message=$(echo "$input_json" | jq -r '.message' 2>&1); then
    echo "Error: Failed to parse JSON - $notification_message" >&2
    exit 1
fi

# Send the notification and propagate any failures
if ! notify-send --icon="" --wait "Claude: $notification_message"; then
    echo "Error: notify-send failed" >&2
    exit 1
fi
```

> **Note:** `session-start-check.sh` checks for `jq`, but it does not check for `notify-send`. If your machine does not have `notify-send`, you will need to replace or remove the `Notification` hook.

## Enabled Plugins

The file enables official plugins, repo-owned plugins, and two third-party marketplace plugins.

```96:133:settings.json
"enabledPlugins": {
  "pyright-lsp@claude-plugins-official": true,
  "jdtls-lsp@claude-plugins-official": true,
  "lua-lsp@claude-plugins-official": true,
  "github@claude-plugins-official": true,
  "myk-review@myk-org": true,
  "myk-github@myk-org": true,
  "code-simplifier@claude-plugins-official": true,
  "playground@claude-plugins-official": true,
  "frontend-design@claude-plugins-official": true,
  "code-review@claude-plugins-official": true,
  "superpowers@claude-plugins-official": true,
  "feature-dev@claude-plugins-official": true,
  "commit-commands@claude-plugins-official": true,
  "security-guidance@claude-plugins-official": true,
  "claude-md-management@claude-plugins-official": true,
  "pr-review-toolkit@claude-plugins-official": true,
  "claude-code-setup@claude-plugins-official": true,
  "gopls-lsp@claude-plugins-official": true,
  "coderabbit@claude-plugins-official": true,
  "cli-anything@cli-anything": true,
  "worktrunk@worktrunk": true,
  "myk-acpx@myk-org": true
},
"extraKnownMarketplaces": {
  "cli-anything": {
    "source": { "source": "github", "repo": "HKUDS/CLI-Anything" }
  },
  "worktrunk": {
    "source": { "source": "github", "repo": "max-sixty/worktrunk" }
  }
},
```

A useful way to read this list is by category:

- Language servers: `pyright-lsp`, `jdtls-lsp`, `lua-lsp`, `gopls-lsp`
- Review and workflow helpers: `github`, `code-review`, `pr-review-toolkit`, `superpowers`, `feature-dev`, `coderabbit`, `security-guidance`, `code-simplifier`, `frontend-design`, `commit-commands`, `claude-md-management`, `claude-code-setup`, `playground`
- Repo marketplace plugins: `myk-review`, `myk-github`, `myk-acpx`
- Third-party marketplaces: `cli-anything`, `worktrunk`

The repo-owned marketplace is defined in the checked-in manifest at `.claude-plugin/marketplace.json`:

```1:24:.claude-plugin/marketplace.json
{
  "name": "myk-org",
  "owner": {
    "name": "myk-org"
  },
  "plugins": [
    {
      "name": "myk-github",
      "source": "./plugins/myk-github",
      "description": "GitHub operations - PR reviews, releases, review handling, CodeRabbit rate limits",
      "version": "1.7.2"
    },
    {
      "name": "myk-review",
      "source": "./plugins/myk-review",
      "description": "Local code review and review database operations",
      "version": "1.7.2"
    },
    {
      "name": "myk-acpx",
      "source": "./plugins/myk-acpx",
      "description": "Multi-agent prompt execution via acpx (Agent Client Protocol)",
      "version": "1.7.2"
    }
  ]
}
```

> **Note:** The startup health check only validates a subset of official plugins. It does not currently verify installation of the `myk-*`, `cli-anything`, or `worktrunk` plugins, even though they are enabled here.

## Status Line

This configuration replaces the default status line with a shell script and disables extra padding.

```91:94:settings.json
"statusLine": {
  "type": "command",
  "command": "bash ~/.claude/statusline.sh",
  "padding": 0
},
```

The script builds the line from workspace and runtime context:

```7:50:statusline.sh
model_name=$(echo "$input" | jq -r '.model.display_name')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')

# Get context usage percentage (pre-calculated by Claude Code v2.1.6+)
context_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Get current directory basename
dir_name=$(basename "$current_dir")

# Add SSH info if connected via SSH
if [ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]; then
    status_parts+=("$(whoami)@$(hostname -s)")
fi

# Add git branch if in a git repository
if git rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git branch --show-current 2>/dev/null || echo "detached")
    status_parts+=("$branch")
fi

# Add virtual environment if active
if [ -n "$VIRTUAL_ENV" ]; then
    status_parts+=("($(basename "$VIRTUAL_ENV"))")
fi

# Add model and context usage
status_parts+=("$model_name")
if [ -n "$context_pct" ]; then
    status_parts+=("(${context_pct}%)")
fi
```

In order, the rendered line includes:

- Current directory name
- SSH user and host, when connected over SSH
- Current Git branch, when inside a Git repo
- Active virtual environment name, when present
- Model display name
- Context-window usage percentage, when available
- Added/removed line counts, when nonzero

> **Tip:** `statusline.sh` depends on `jq` and `git`. If the status line looks broken, check those first.

## Environment And UX Flags

At the end of the file, `settings.json` sets runtime flags, environment variables, and survey behavior.

```134:165:settings.json
"alwaysThinkingEnabled": true,
"skipDangerousModePermissionPrompt": true,
"autoDreamEnabled": true,
"_scriptsNote": "Script entries must be duplicated in both permissions.allow and allowedTools arrays. When adding new scripts, update BOTH locations.",
"allowedTools": [
  # ...
],
"env": {
  "DISABLE_TELEMETRY": "1",
  "DISABLE_ERROR_REPORTING": "1",
  "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1"
},
"feedbackSurveyRate": 0,
"feedbackSurveyState": {
  "lastShownTime": 1754082998309
}
```

Here is what those settings mean in practice:

- `alwaysThinkingEnabled: true` turns on Claude Code's thinking mode by default
- `autoDreamEnabled: true` enables Claude Code's auto-dream behavior by default
- `skipDangerousModePermissionPrompt: true` removes the standard dangerous-mode confirmation prompt, but this config still protects Bash usage with allowlists and `PreToolUse` hooks
- `DISABLE_TELEMETRY` and `DISABLE_ERROR_REPORTING` opt out of telemetry and automatic error reporting
- `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY` plus `feedbackSurveyRate: 0` disables feedback survey prompts
- `feedbackSurveyState.lastShownTime` is local runtime state, not a setting most users need to edit

> **Note:** If you are trimming this file for your own use, keep the safety model in mind. Disabling the dangerous-mode prompt makes the Bash allowlist and hooks even more important.

## Keeping Everything In Sync

When you change this file, use this checklist:

1. Keep `scripts/` installed under `~/.claude/scripts/` and `statusline.sh` at `~/.claude/statusline.sh`.
2. If you add or rename a hook script, update the hook `command` and mirror its `Bash(...)` entry in both `permissions.allow` and `allowedTools`.
3. Keep `uv` installed, because all Python hooks depend on it.
4. Prefer `uv run`, `uvx`, and `prek` over raw `python`, `pip`, and `pre-commit`.
5. If you want desktop notifications, make sure `jq` and `notify-send` are available.
6. If you rely on GitHub PR checks, make sure `gh` is installed and authenticated.

## Verifying Changes

This repository validates the hook behavior with unit tests, and `tox.toml` runs those tests through `uv`:

```4:7:tox.toml
[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

The repo also includes `.pre-commit-config.yaml`, which is why `session-start-check.sh` treats `prek` as relevant here.

> **Note:** There are no checked-in GitHub Actions or Jenkins pipeline files in this repository. The visible validation path in-repo is local: `tox` plus pre-commit.
