# System Requirements

This repository is a Claude Code configuration, not a standalone application. To use it as intended, you need Claude Code itself plus the local tools, hooks, and plugins that the checked-in configuration expects.

The list below is based on the codebase itself: `settings.json`, hook scripts, plugin commands, Python modules, tests, and local automation files.

## Requirement Matrix

| Component | Why the repository expects it | Required? |
|---|---|---|
| Python 3.10+ | `myk-claude-tools` declares `requires-python = ">=3.10"` | Yes |
| `uv` | Runs all Python hooks and is the expected Python entrypoint | Yes |
| `git` | Required by repo-aware CLI flows such as reviews and releases | Yes |
| `myk-claude-tools` | Required by the `myk-github` and `myk-review` slash commands | Yes for those plugins |
| `superpowers`, `pr-review-toolkit`, `feature-dev` plugins | Power the mandatory 3-agent review loop | Yes |
| `gh` | Needed for GitHub PR, review, diff, release, and API operations | Required for GitHub workflows |
| `jq` | Used by the status line and notification hook; checked at session start | Recommended, practically required for stock setup |
| `gawk` | Checked as part of the expected AI review handler toolchain | Recommended |
| `prek` | Required for this repo’s pre-commit workflow; direct `pre-commit ...` is blocked | Recommended, effectively required here |
| `mcpl` | Required if you use MCP server discovery and execution | Optional |
| `acpx` | Required only for the optional `myk-acpx` plugin | Optional |
| `notify-send` | Needed only for the Linux desktop notification hook | Optional, Linux-only |

## Core Runtime

The packaged CLI and Python tooling require Python 3.10 or newer, and the repository is wired to run Python through `uv`.

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

[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

The checked-in Claude settings run the hook scripts with `uv run`, so `uv` is not optional if you want the configuration to work as shipped.

```37:84:settings.json
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
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "You are a security gate protecting against catastrophic OS destruction. Analyze: $ARGUMENTS\n\nBLOCK if the command would:\n- Delete system directories: /, /boot, /etc, /usr, /bin, /sbin, /lib, /var, /home\n- Write to disk devices: dd to /dev/sda, /dev/nvme, etc.\n- Format filesystems: mkfs on any device\n- Remove critical files: /etc/fstab, /etc/passwd, /etc/shadow, kernel/initramfs\n- Recursive delete with sudo or as root\n- Chain destructive commands after safe ones using &&, ;, |, ||\n\nASK (requires user confirmation) if:\n- Command uses sudo but is not clearly destructive\n- Deletes files outside system directories but looks risky\n\nALLOW all other commands - this gate only guards against OS destruction.\n\nIMPORTANT: Use your judgment. If a command seems potentially destructive even if not explicitly listed above, ASK the user for confirmation.\n\nRespond with JSON: {\"decision\": \"approve\" or \"block\" or \"ask\", \"reason\": \"brief explanation\"}",
            "timeout": 10000
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
```

`git` is also part of the expected baseline. It is not just for cloning the repo; several Python modules call it directly to find branches, roots, tags, and diffs.

> **Warning:** If `uv` is missing, the hook system in `settings.json` cannot run as configured.

## Startup Checks

The session-start hook is the clearest summary of what this configuration expects to find on your machine.

```29:93:scripts/session-start-check.sh
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
  Install: brew install gawk (macOS) or apt install gawk (Linux)")
fi

# OPTIONAL: prek - Only check if .pre-commit-config.yaml exists
if [[ -f ".pre-commit-config.yaml" ]]; then
  if ! command -v prek &>/dev/null; then
    missing_optional+=("[OPTIONAL] prek - Required for pre-commit hooks (detected .pre-commit-config.yaml)
  Install: https://github.com/j178/prek")
  fi
fi

# OPTIONAL: mcpl - MCP Launchpad (always check)
if ! command -v mcpl &>/dev/null; then
  missing_optional+=("[OPTIONAL] mcpl - MCP Launchpad for MCP server access
  Install: https://github.com/kenneth-liao/mcp-launchpad")
fi

# CRITICAL: Review plugins - Required for mandatory code review loop
critical_marketplace_plugins=(
  pr-review-toolkit
  superpowers
  feature-dev
)
```

Two details are worth calling out:

- `gh`, `jq`, `gawk`, `prek`, and `mcpl` are reported as optional by the startup script, but several project features stop working without them.
- This repo contains `.pre-commit-config.yaml`, so the `prek` check is active here.

> **Note:** `gawk` is only explicitly checked by the startup script in this repository. That means it is part of the supported review-processing environment, even though the critical hooks do not hard-fail if it is missing.

## `uv` Instead of Raw Python or `pre-commit`

The rule-enforcer hook blocks direct Python and direct `pre-commit` usage. The expected workflow is `uv run`, `uvx`, and `prek`.

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

In practice, that means:

- Use `uv run ...` for Python scripts.
- Use `uvx ...` for Python-based CLI tools.
- Use `prek run --all-files` instead of `pre-commit run --all-files`.

`tests/test_rule_enforcer.py` backs this up: it explicitly allows `uv`/`uvx` and `prek`, and explicitly denies direct `pre-commit ...` commands.

> **Warning:** If you already use `pre-commit` directly in other projects, do not assume that will work here. This repo’s hook logic is written to reject that path.

## Review Plugins Are Mandatory

This configuration enforces a 3-reviewer loop for code changes. Those reviewers come from official Claude plugins, and the workflow depends on them being installed.

```35:43:rules/20-code-review-loop.md
Three plugin agents review code in parallel for comprehensive coverage:

| Agent | Focus |
|---|---|
| `superpowers:code-reviewer` | General code quality and maintainability |
| `pr-review-toolkit:code-reviewer` | Project guidelines and style adherence (CLAUDE.md) |
| `feature-dev:code-reviewer` | Bugs, logic errors, and security vulnerabilities |

**All 3 MUST be invoked in the same assistant turn as 3 parallel Task tool calls (one response containing 3 Task invocations, not sequential messages).**
```

If you want the configuration to behave the way the rules describe, install:

- `superpowers@claude-plugins-official`
- `pr-review-toolkit@claude-plugins-official`
- `feature-dev@claude-plugins-official`

The checked-in `settings.json` also enables a larger set of optional marketplace plugins, including `coderabbit`, `github`, `code-review`, `code-simplifier`, `frontend-design`, `security-guidance`, `pyright-lsp`, `gopls-lsp`, `jdtls-lsp`, `lua-lsp`, `playground`, `commit-commands`, `claude-code-setup`, and `claude-md-management`. Those are enhancements, not the hard minimum.

> **Warning:** Skipping the three review plugins breaks the repository’s mandatory review loop, even if everything else is installed.

## Shipped Plugins From This Repo

The repository’s marketplace manifest ships three plugins of its own:

- `myk-github`
- `myk-review`
- `myk-acpx`

Those are declared in `.claude-plugin/marketplace.json`, and `settings.json` enables them as `myk-github@myk-org`, `myk-review@myk-org`, and `myk-acpx@myk-org`.

If you plan to use the repo’s slash commands, install the relevant plugin packages through Claude Code’s plugin system.

## `myk-claude-tools` Is Required for `myk-github` and `myk-review`

The repo’s GitHub and review plugins rely on the packaged `myk-claude-tools` CLI. The command definitions repeatedly check for it and tell users to install it with `uv`.

Examples in the command files include:

- `myk-claude-tools --version`
- `uv tool install myk-claude-tools`

That dependency is not theoretical. The `myk-github` and `myk-review` commands are designed around `myk-claude-tools pr ...`, `myk-claude-tools reviews ...`, `myk-claude-tools db ...`, and `myk-claude-tools release ...`.

> **Tip:** If you only want the hook behavior and do not plan to use `/myk-github:*` or `/myk-review:*`, you can postpone installing `myk-claude-tools`. For the slash commands themselves, it is required.

## GitHub CLI (`gh`) and Authentication

`gh` is where the repo draws an important line between "startup can continue" and "feature works correctly."

The startup checker only marks `gh` as optional for GitHub repos, but the actual CLI commands that fetch PRs, diffs, and release metadata fail without it.

```83:88:myk_claude_tools/reviews/fetch.py
def check_dependencies() -> None:
    """Check required dependencies."""
    for cmd in ("gh", "git"):
        if shutil.which(cmd) is None:
            print_stderr(f"Error: '{cmd}' is required but not installed.")
            sys.exit(1)
```

```188:223:myk_claude_tools/reviews/fetch.py
    for target_repo in repos_to_try:
        cmd = ["gh", "pr", "view", current_branch, "--json", "number", "--jq", ".number"]
        if target_repo:
            cmd.extend(["-R", target_repo])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                pr_number = result.stdout.strip()
                matched_repo = target_repo
                if target_repo:
                    print_stderr(f"Found PR #{pr_number} on upstream ({target_repo})")
                break
        except subprocess.TimeoutExpired:
            continue

    # Fall back to gh repo view for the default repo
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "owner,name", "-q", '.owner.login + "/" + .name'],
```

Other modules do the same:

- `myk_claude_tools/pr/diff.py` uses `gh api` and `gh pr diff`.
- `myk_claude_tools/release/info.py` treats both `gh` and `git` as required for release info.
- The `myk-github` plugin command definitions use `gh pr view`, `gh repo view`, and `gh pr create`.

That means you need both:

- the `gh` binary installed
- a working `gh` login with access to the repositories you want to operate on

> **Warning:** Installing `gh` is not enough by itself. Review, diff, PR, and release flows assume `gh` can successfully call `gh api`, `gh pr view`, and `gh repo view` against your GitHub account.

There is one notable exception: `scripts/git-protection.py` uses `gh` opportunistically to detect merged PRs, but it tolerates a missing `gh` and falls back gracefully. `tests/test_get_all_reviews.py` and `tests/test_git_protection.py` cover that difference.

## `jq`, `notify-send`, and the Stock UI Hooks

The repo’s stock status line parses JSON with `jq`, and the notification hook requires both `jq` and `notify-send`.

```7:11:statusline.sh
model_name=$(echo "$input" | jq -r '.model.display_name')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')

# Get context usage percentage (pre-calculated by Claude Code v2.1.6+)
context_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
```

```4:9:scripts/my-notifier.sh
# Check for required commands
for cmd in jq notify-send; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: Required command '$cmd' not found" >&2
        exit 1
    fi
done
```

For a stock Linux setup, install both.

On non-Linux systems, or if you do not want desktop notifications, you can treat `notify-send` as optional and adjust the hook to match your platform.

> **Note:** `jq` is labeled optional in the startup script, but it is a practical day-one dependency if you keep the checked-in status line and notifier enabled.

## `mcpl` for MCP Servers

If you use MCP-backed workflows, this repo expects `mcpl` as the command-line entrypoint.

```12:22:rules/15-mcp-launchpad.md
| Command                                      | Purpose                                             |
|----------------------------------------------|-----------------------------------------------------|
| `mcpl search "<query>"`                      | Search all tools (shows required params, 5 results) |
| `mcpl search "<query>" --limit N`            | Search with more results                            |
| `mcpl list`                                  | List all MCP servers                                |
| `mcpl list <server>`                         | List tools for a server (shows required params)     |
| `mcpl inspect <server> <tool>`               | Get full schema                                     |
| `mcpl inspect <server> <tool> --example`     | Get schema + example call                           |
| `mcpl call <server> <tool> '{}'`             | Execute tool (no arguments)                         |
| `mcpl call <server> <tool> '{"param": "v"}'` | Execute tool with arguments                         |
| `mcpl verify`                                | Test all server connections                         |
```

`settings.json` also explicitly allows `Bash(mcpl:*)`.

If you never use MCP servers, you can skip `mcpl`. If you do use them, install it before relying on MCP-related rules or commands.

## Optional `acpx` Support

`myk-acpx` is shipped and enabled in `settings.json`, but its own command file treats `acpx` as optional and prompts users to install it only when needed.

```45:80:plugins/myk-acpx/commands/prompt.md
### Step 1: Prerequisites Check

#### 1a: Check acpx

```bash
acpx --version
```

If not found, ask the user via AskUserQuestion:

"acpx is not installed. It provides structured access to multiple coding agents (Codex, Cursor, Gemini, etc.) via the Agent Client Protocol.

Install it now?"

Options:

- **Yes (Recommended)** — Install globally with `npm install -g acpx@latest`
- **No** — Abort

If user selects Yes, run:

```bash
npm install -g acpx@latest
```

Verify installation:

```bash
acpx --version
```
```

If you want `/myk-acpx:prompt`, you need:

- `acpx`
- the underlying target agent CLI you want `acpx` to wrap, such as Cursor, Codex, Gemini, or Copilot

If you do not use `myk-acpx`, you can skip this entire dependency chain.

## Local Validation Model

This repository does not define GitHub Actions workflows under `.github/workflows/`. Its automation model is local-first:

- Claude hooks are defined in `settings.json`
- test execution is defined in `tox.toml`
- pre-commit hooks are defined in `.pre-commit-config.yaml`
- the supported wrapper for pre-commit is `prek`

`tox.toml` shows the expected test command:

```1:7:tox.toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

That means you do not need to provision CI runners just to use the repo. You do need the local CLI toolchain that those hooks and test commands expect.

> **Note:** In this repo, "CI/CD requirements" mostly translate to local hook and validation requirements, not hosted workflow requirements.

## Quick Verification Checklist

Run the commands below after installing the toolchain you need:

```bash
uv --version
myk-claude-tools --version
gh repo view --json nameWithOwner -q .nameWithOwner
prek run --all-files
mcpl verify
acpx --version
uv run --group tests pytest tests
```

Use the ones that match the features you plan to use:

- Always verify `uv`.
- Verify `myk-claude-tools` if you plan to use `myk-github` or `myk-review`.
- Verify `gh` against a real repository if you plan to use PR, review, or release features.
- Verify `prek` in this repository, because `.pre-commit-config.yaml` is present.
- Verify `mcpl` only if you use MCP integrations.
- Verify `acpx` only if you use `myk-acpx`.

> **Tip:** `~/.claude/scripts/session-start-check.sh` is the fastest way to surface missing critical and optional requirements in one pass.
