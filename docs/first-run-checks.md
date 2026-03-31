# First-Run Checks

When you open a Claude Code session with this configuration, a quick startup hook runs to verify the local tools and plugins it depends on. The goal is to catch missing pieces early, explain what matters, and let you keep going instead of failing hard at startup.

```78:95:settings.json
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
  },
```

> **Note:** A healthy startup is intentionally quiet. If everything required is present, the session-start check does not print a success banner.

## What Runs At Session Start
The validation logic lives in `scripts/session-start-check.sh`. It checks command-line tools with `command -v`, checks official marketplace plugins in standard `~/.claude` install locations, groups anything missing into `CRITICAL` and `OPTIONAL`, and only prints a report when there is something to fix.

The tool checks are:

| Item | Level | When it is checked | Why it matters |
|---|---|---|---|
| `uv` | Critical | Always | Required for the Python-based hooks used by this config |
| `gh` | Optional | Only if the current repo has a GitHub remote | Needed for GitHub PR, issue, and release workflows |
| `jq` | Optional | Always | Used for JSON processing in AI review tooling |
| `gawk` | Optional | Always | Used for text processing in AI review tooling |
| `prek` | Optional | Only if `.pre-commit-config.yaml` exists in the current directory | Needed for pre-commit workflows |
| `mcpl` | Optional | Always | Enables MCP Launchpad access |

The script also checks a curated set of official marketplace plugins as optional enhancements: `claude-code-setup`, `claude-md-management`, `code-review`, `code-simplifier`, `coderabbit`, `commit-commands`, `frontend-design`, `github`, `gopls-lsp`, `jdtls-lsp`, `lua-lsp`, `playground`, `pyright-lsp`, and `security-guidance`.

> **Tip:** Open Claude Code in the project root you actually want to work in. The `gh` check depends on the repo's Git remotes, and the `prek` check depends on files in your current directory.

## Critical Plugin Checks
Three official review plugins are treated as critical. If any of them are missing, the startup check tells Claude to prioritize fixing those first.

```69:93:scripts/session-start-check.sh
# CRITICAL: Review plugins - Required for mandatory code review loop
critical_marketplace_plugins=(
  pr-review-toolkit
  superpowers
  feature-dev
)

missing_critical_plugins=()
for plugin in "${critical_marketplace_plugins[@]}"; do
  if ! check_plugin_installed "$plugin"; then
    missing_critical_plugins+=("$plugin")
  fi
done

if [[ ${#missing_critical_plugins[@]} -gt 0 ]]; then
  missing_list=$(printf '%s, ' "${missing_critical_plugins[@]}")
  missing_list=${missing_list%, }
  install_cmds=""
  for p in "${missing_critical_plugins[@]}"; do
    install_cmds+="    /plugin install ${p}@claude-plugins-official"$'\n'
  done
  missing_critical+=("[CRITICAL] Missing review plugins - Required for mandatory code review loop
  Install:
    /plugin marketplace add claude-plugins-official
${install_cmds}  Missing: ${missing_list}")
```

Those three plugins are critical because the repository's review workflow depends on all three review agents running in parallel:

```35:41:rules/20-code-review-loop.md
Three plugin agents review code in parallel for comprehensive coverage:

| Agent | Focus |
|---|---|
| `superpowers:code-reviewer` | General code quality and maintainability |
| `pr-review-toolkit:code-reviewer` | Project guidelines and style adherence (CLAUDE.md) |
| `feature-dev:code-reviewer` | Bugs, logic errors, and security vulnerabilities |
```

> **Warning:** The startup check is non-blocking. Claude Code will still open even if something marked `CRITICAL` is missing, so treat those warnings as action required, not as harmless suggestions.

## What Happens When Something Is Missing
If the script finds anything missing, it prints a structured `MISSING_TOOLS_REPORT:`. That report does more than list missing items: it explicitly tells Claude to explain each one and ask whether you want help installing it.

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
  echo ""
  echo "YOUR REQUIRED ACTION:"
  echo "1. List each missing tool with its purpose"
  echo "2. ASK the user: 'Would you like me to help install these tools?'"
  echo "3. If user accepts, provide the installation command for each tool"
  echo "4. Prioritize CRITICAL tools first"
  echo ""
  echo "DO NOT just mention the tools. You MUST ask if the user wants help installing them."
  echo ""

  for item in "${missing_critical[@]}"; do
    echo "$item"
    echo ""
  done

  for item in "${missing_optional[@]}"; do
    echo "$item"
    echo ""
  done
fi

# Always exit 0 (non-blocking)
exit 0
```

In practice, the first-run flow looks like this:

1. A new Claude session starts.
2. The `SessionStart` hook runs `session-start-check.sh`.
3. If everything is present, startup stays silent.
4. If anything is missing, Claude should explain what is missing and ask if you want installation help.

> **Note:** Because this check is attached to `SessionStart`, the simplest way to run it again after installing something is to start a new Claude session.

## How To Confirm The Configuration Is Active
There is no dedicated "all good" banner, so confirmation is mostly about expected behavior.

A visible signal is the custom status line. This config enables `statusline.sh`, which builds a line from your current directory, Git branch, model name, context usage, and line delta.

```7:46:statusline.sh
model_name=$(echo "$input" | jq -r '.model.display_name')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')

# Get context usage percentage (pre-calculated by Claude Code v2.1.6+)
context_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Get current directory basename
dir_name=$(basename "$current_dir")

# Build status line components
status_parts=()

# Add directory name
status_parts+=("$dir_name")

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

# Extract lines added/removed
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
```

A practical confirmation checklist:

1. Open a fresh Claude Code session in the repository root.
2. If anything is missing, expect a `MISSING_TOOLS_REPORT:` and an offer to help install it.
3. If nothing is missing, expect no startup warning.
4. Look for the custom status line showing your directory, branch, model, and session context.
5. If you use one of this repo's slash commands, expect it to follow the repo's defined workflows rather than generic Claude defaults.

> **Warning:** `jq` is labeled optional by the startup check, but the status line also uses `jq`. If `jq` is missing, Claude Code may still start, but the custom status line can fail or appear incomplete.

## What First-Run Checks Do Not Cover
The startup check is useful, but it is not exhaustive.

It does not validate every dependency every command might need later. For example, repo-specific commands can run their own prerequisite checks on demand instead of at session start:

```11:32:plugins/myk-github/commands/pr-review.md
## Prerequisites Check (MANDATORY)

Before starting, verify the tools are available:

### Step 0: Check uv

... command example omitted ...

If not found, install from <https://docs.astral.sh/uv/getting-started/installation/>

### Step 1: Check myk-claude-tools

... command example omitted ...

If not found, prompt user: "myk-claude-tools is required. Install with: `uv tool install myk-claude-tools`. Install now?"

- Yes: Run `uv tool install myk-claude-tools`
- No: Abort with instructions
```

That means "the first-run check passed" and "every later command dependency is already installed" are not exactly the same thing. The startup hook verifies the shared foundation, while individual commands may still perform their own targeted checks.

The other important limit is plugin detection scope. The startup script checks official `@claude-plugins-official` plugins from standard `~/.claude` install paths. It does not serve as a full audit of every enabled plugin or every marketplace you may have configured.

> **Warning:** If your plugins are installed in a non-standard location, the startup check may report them missing even though Claude Code can still reach them another way.
