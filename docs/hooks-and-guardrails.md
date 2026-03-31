# Hooks and Guardrails

This configuration uses Claude Code hooks as a safety layer. Some hooks stop risky commands before they run. Some add context so the assistant follows the intended workflow. Others check whether your local setup is missing tools or turn Claude notifications into desktop popups.

The hook registrations live in `settings.json`. The tracked source files live in the repository's `scripts/` directory, and the runtime configuration invokes them from `~/.claude/scripts/...`.

## At a Glance

| Component | Event | What it does |
| --- | --- | --- |
| `rule-enforcer.py` | `PreToolUse` | Blocks raw `python`/`pip` and raw `pre-commit` commands. |
| `git-protection.py` | `PreToolUse` | Blocks unsafe `git commit` and `git push` operations. |
| Bash destruction gate | `PreToolUse` | Reviews high-risk shell commands and can approve, block, or ask for confirmation. |
| `rule-injector.py` | `UserPromptSubmit` | Adds reminder text to each prompt so the assistant stays within the intended workflow. |
| `session-start-check.sh` | `SessionStart` | Reports missing tools and plugins, but does not stop the session. |
| `my-notifier.sh` | `Notification` | Sends desktop notifications with `notify-send`. |

## Where Hooks Are Wired In

```25:55:settings.json
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/my-notifier.sh"
          }
        ]
      }
    ],
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
```

Later in the same `settings.json` section, the configuration also wires in the prompt-based Bash destruction gate, `rule-injector.py` for `UserPromptSubmit`, and `session-start-check.sh` for `SessionStart`.

> **Note:** The config includes its own maintenance warning: script entries need to appear in both `permissions.allow` and `allowedTools`. If you add or rename a hook, update both places.

## Pre-Tool Guardrails

### `rule-enforcer.py`

Despite its name, this hook is focused rather than broad. In the current code, it only acts on Bash commands and blocks two categories:

- direct `python`, `python3`, `pip`, and `pip3`
- direct `pre-commit`

It does not block `uv`, `uvx`, or `prek`, and it does not inspect non-Bash tools. Because the matcher is `TodoWrite|Bash`, Claude may invoke it for `TodoWrite`, but the script immediately returns unless `tool_name == "Bash"`.

```35:71:scripts/rule-enforcer.py
        # Block direct python/pip commands
        if tool_name == "Bash":
            command = tool_input.get("command", "")
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
                            "You attempted to run pre-commit directly. Instead:\n"
                            "1. Use the 'prek' command which wraps pre-commit\n"
                            "2. Example: prek run --all-files\n"
                            "See: https://github.com/j178/prek"
```

In practice, that means switching to `uv run ...`, `uvx ...`, or `prek run --all-files` instead of calling the raw tool directly.

> **Tip:** If a command gets denied here, use the wrapper the hook suggests instead of trying to work around it. That is the supported workflow this repository expects.

`tests/test_rule_enforcer.py` confirms a few important details:

- matching is case-insensitive
- `uv`, `uvx`, and `prek` are allowed
- commands that merely contain words like `python` in an argument are not blocked
- malformed hook input and internal exceptions fail open, so the hook does not block the session if its own input is broken

### `git-protection.py`

This is the strictest guardrail in the repository. It inspects Bash commands for `git commit` and `git push` and blocks them when the current branch is unsafe.

It blocks `git commit` when:

- you are in detached HEAD
- you are on `main` or `master`
- the current branch is already merged locally
- the current branch already has a merged GitHub PR
- the GitHub PR lookup itself fails

It blocks `git push` for the same protected-branch and merged-branch cases, but it does not block pushes from detached HEAD.

It also has one important escape hatch: `git commit --amend` is allowed when your branch is ahead of its upstream, so you can clean up unpublished commits.

```287:346:scripts/git-protection.py
    # Check if PR is already merged on GitHub (doesn't need main_branch)
    pr_merged, pr_info = get_pr_merge_status(current_branch)
    if pr_merged is None:
        # Error checking PR status - fail closed
        return True, format_pr_merge_error("get_pr_merge_status()", pr_info)
    if pr_merged:
        # Get main branch for the message (best effort)
        main_branch = get_main_branch() or "main"
        return (
            True,
            f"""⛔ BLOCKED: PR #{pr_info} for branch '{current_branch}' is already MERGED.

What happened:
- This branch's PR was already merged
- Committing more changes to a merged branch is not useful

**ACTION REQUIRED - Execute these commands NOW:**

You MUST create a new branch for these changes. Do NOT ask user - just do it:
1. git checkout {main_branch}
2. git pull origin {main_branch}
3. git checkout -b feature/new-changes
4. Move uncommitted changes and commit on the new branch

IMMEDIATELY switch to '{main_branch}' and create a new feature branch.""",
        )

    # Get main branch for subsequent checks
    detected_main_branch = get_main_branch()
    if not detected_main_branch:
        # Can't determine main branch - allow
        return False, None

    # Block if on main/master branch
    if current_branch in ["main", "master"]:
        return (
            True,
            f"""⛔ BLOCKED: Cannot commit directly to '{current_branch}' branch.

What happened:
- You are on the protected '{current_branch}' branch
- Direct commits to {current_branch} bypass code review and CI checks

**ACTION REQUIRED - Execute these commands NOW:**

You MUST create a feature branch for these changes. Do NOT ask user - just do it:
1. git stash (if you have uncommitted changes)
2. git checkout -b feature/your-feature
3. git stash pop (if you stashed changes)
4. Then commit your changes on the new branch

IMMEDIATELY create a feature branch and move your changes there.""",
        )

    # Allow amend on unpushed commits
    if is_amend_with_unpushed_commits(command):
        return False, None

    # Check if branch is merged (local check as fallback)
    if is_branch_merged(current_branch, detected_main_branch):
```

A few details matter if you are troubleshooting:

- the GitHub check only runs for GitHub remotes and only when `gh` is installed
- if that GitHub check is unavailable, the script falls back to local git history checks
- the parser is deliberately broader than a simple prefix match; tests confirm it catches forms like `git -C /path commit ...`, environment-prefixed commands, and quoted or piped `git commit` strings, while still avoiding common false positives like `git config push.default`

> **Warning:** `git-protection.py` fails closed. If it cannot safely determine whether a commit or push should be allowed, it blocks the operation rather than guessing. In a GitHub-backed repository, a broken `gh` login or a GitHub API error is enough to stop the command.

> **Note:** When the GitHub lookup or the hook itself crashes, the returned message explicitly tells the assistant to ask whether you want a GitHub issue created against `myk-org/claude-code-config`. That behavior is intentional and is covered by the tests.

### The additional Bash destruction gate

The `PreToolUse` chain in `settings.json` also includes a prompt-based security gate for Bash. It is not implemented in one of the scripts above, but it is part of the overall guardrail story.

That prompt-based hook is aimed at catastrophic OS damage: deleting system directories, formatting disks, writing raw devices with `dd`, removing files such as `/etc/passwd`, or chaining destructive commands after safe-looking ones. Depending on the command, it can approve, block, or ask for explicit confirmation.

> **Warning:** This guardrail is intentionally conservative. If a command uses `sudo` or looks risky even when it is not obviously destructive, you may be asked to confirm before it runs.

## Prompt Enrichment

### `rule-injector.py`

This hook runs on `UserPromptSubmit`. Instead of blocking anything, it adds a short reminder to the prompt context so the assistant keeps following the repository's intended division of responsibilities.

```21:35:scripts/rule-injector.py
    try:
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

        # Output JSON to stdout
        print(json.dumps(output, indent=2))
```

The important user-facing point is that this hook enriches the assistant's context every time you send a prompt. It does not touch your files or shell history.

> **Note:** In the current implementation, `rule-injector.py` emits a fixed reminder string. It does not read the repository's `rules/` directory at runtime.

If the script hits an error, it logs to stderr and exits successfully, so your prompt still goes through.

## Session Start Checks

### `session-start-check.sh`

This hook runs once at session start, with a 5 second timeout in `settings.json`. If everything is present, it stays silent. If something is missing, it acts like a non-blocking environment audit.

It checks for:

- critical `uv`, because the Python hooks are run with `uv run`
- `gh`, but only when the current repo points at GitHub
- `jq`
- `gawk`
- `prek`, but only when `.pre-commit-config.yaml` exists
- `mcpl`
- critical review plugins: `pr-review-toolkit`, `superpowers`, and `feature-dev`
- a longer list of optional marketplace plugins

When something is missing, it prints a structured report instead of stopping the session.

```134:151:scripts/session-start-check.sh
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
```

This repository does include a real `.pre-commit-config.yaml`, with hooks such as `detect-private-key`, `ruff`, `mypy`, and `markdownlint`. That is why `prek` matters in practice here, even though the startup report labels it optional.

> **Tip:** If you see `MISSING_TOOLS_REPORT`, install the critical items first. The startup hook always exits `0`, so it will not block the session on its own.

> **Note:** The startup check warns about missing `jq`, but it does not check for `notify-send`. A session can start cleanly and still have notification failures later if your machine cannot run desktop notifications.

## Notifications

### `my-notifier.sh`

This is the `Notification` hook. It reads JSON from stdin, extracts `.message`, and passes it to `notify-send` as a desktop notification.

```4:37:scripts/my-notifier.sh
# Check for required commands
for cmd in jq notify-send; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: Required command '$cmd' not found" >&2
        exit 1
    fi
done

# Read JSON input from stdin
input_json=$(cat)

# Verify input is not empty
if [[ -z "$input_json" ]]; then
    echo "Error: No input received from stdin" >&2
    exit 1
fi

# Parse JSON and extract message, capturing any jq errors
if ! notification_message=$(echo "$input_json" | jq -r '.message' 2>&1); then
    echo "Error: Failed to parse JSON - $notification_message" >&2
    exit 1
fi

# Verify notification_message is non-empty
if [[ -z "$notification_message" || "$notification_message" == "null" ]]; then
    echo "Error: Notification message is empty or missing from JSON" >&2
    exit 1
fi

# Send the notification and propagate any failures
if ! notify-send --icon="" --wait "Claude: $notification_message"; then
    echo "Error: notify-send failed" >&2
    exit 1
fi
```

This script is Linux-friendly out of the box because it relies on `notify-send`. If you use a headless environment, container, remote shell, or another operating system, you may need to replace it with a platform-specific notifier.

> **Warning:** Unlike `session-start-check.sh`, this script does not degrade gracefully. Missing dependencies, malformed JSON, or a failing notification daemon all cause it to exit non-zero.

## Failure Behavior

Not all hooks fail the same way, and that difference is intentional.

| Component | Failure behavior |
| --- | --- |
| `rule-enforcer.py` | Fails open. Invalid JSON or internal errors do not block the tool call. |
| `git-protection.py` | Fails closed. If it cannot safely evaluate the git operation, it blocks it. |
| `rule-injector.py` | Fails open. Prompt submission continues even if the injector errors. |
| `session-start-check.sh` | Never blocks. It reports missing items and exits `0`. |
| `my-notifier.sh` | Exits non-zero on dependency, input, or notification errors. |

## How This Is Verified

The two Python guardrails are backed by unit tests, and the repository's tox configuration runs them through `uv`:

```1:7:tox.toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

The checked-in automation around these hooks is local `tox`/`pytest` and pre-commit configuration rather than a separate hook-specific pipeline file.

Those tests verify the behavior that matters most to users:

- `tests/test_rule_enforcer.py` covers case-insensitive command detection, the `uv`/`uvx` and `prek` escape hatches, and the script's fail-open behavior
- `tests/test_git_protection.py` covers protected branches, merged-PR detection, merged-branch fallback logic, `--amend` handling, detached HEAD behavior, false-positive avoidance in subcommand parsing, and fail-closed error handling

The repository also ships a `.pre-commit-config.yaml`, so local linting and type checking are part of the expected workflow alongside these hooks.

## What To Do When a Hook Fires

- If `rule-enforcer.py` blocks a command, rerun it with `uv`, `uvx`, or `prek` rather than the raw tool.
- If `git-protection.py` blocks a commit or push, move the work onto a feature branch. If the message mentions GitHub lookup errors, fix `gh` authentication or connectivity first.
- If `session-start-check.sh` reports missing items, install critical tools and plugins before leaning on the full workflow.
- If `my-notifier.sh` fails, install `jq` and `notify-send` or replace the notifier with something that fits your OS.
- If the Bash destruction gate asks for confirmation, treat that as a real safety checkpoint, not a nuisance prompt.

This setup is opinionated on purpose: it prefers safe defaults, explicit recovery steps, and clear feedback over silent failures or risky convenience.
