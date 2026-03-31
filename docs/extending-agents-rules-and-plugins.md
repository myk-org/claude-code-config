# Extending Agents, Rules, and Plugins

This repository is easy to extend once you know the pattern: add the primary file, whitelist it, update the companion metadata, and run the local checks. The details differ by extension type, but the workflow is consistent.

## The Safe Workflow

1. Add or remove the main file.
2. Update `.gitignore` so Git will track the change.
3. Update the related routing, hook, or marketplace metadata.
4. Add or update tests when you change guardrails or release logic.
5. Run the local validation commands before you commit.

## Start With `.gitignore`

This repo is intentionally deny-by-default. New files are ignored until you explicitly allow them.

From `.gitignore`:

```text
# Ignore everything by default
# This config integrates into ~/.claude so we must be explicit about what we track
*
```

> **Warning:** If you add a file under `agents/`, `rules/`, `scripts/`, `plugins/`, or `tests/` and do not add a matching `!path/to/file` entry in `.gitignore`, the file will not be tracked.

Use the existing sections as your template:

- `# agents/`
- `# rules/`
- `# scripts/`
- `# plugins/...`
- `# tests/`

Keep new entries in the same style and ordering as the existing block you are editing.

## Add or Remove Agents

Custom agents live in `agents/`. Built-in agents do not.

An existing agent file looks like this:

```markdown
---
name: technical-documentation-writer
description: MUST BE USED when you need comprehensive, user-focused technical documentation for projects, features, or systems.
tools: Read, Write, Edit, Glob, Grep
---
```

`rules/10-agent-routing.md` makes the distinction explicit:

```markdown
### Built-in vs Custom Agents

**Built-in agents** are provided by Claude Code itself and do NOT require definition files in `agents/`:

- `claude-code-guide` - Has current Claude Code documentation built into Claude Code
- `general-purpose` - Default fallback agent when no specialist matches

**Custom agents** are defined in this repository's `agents/` directory and require definition files:
```

### To add an agent

1. Create `agents/<agent-name>.md`.
2. Add frontmatter that matches the existing agent files: `name`, `description`, and `tools`.
3. Add `!agents/<agent-name>.md` to `.gitignore`.
4. Update `rules/10-agent-routing.md` so the orchestrator knows when to use the new agent.
5. Update `rules/50-agent-bug-reporting.md` so agent-configuration bugs stay reportable.

The bug-reporting rule contains an explicit allowlist of repository-defined agents:

```markdown
## Agents Covered by This Rule

This rule applies ONLY to agents defined in this repository (`agents/` directory):

- api-documenter
- bash-expert
- debugger
- docs-fetcher
- docker-expert
- frontend-expert
- git-expert
- github-expert
- go-expert
- java-expert
- jenkins-expert
- kubernetes-expert
- python-expert
- technical-documentation-writer
- test-automator
- test-runner
```

> **Warning:** Adding an agent file without updating `rules/50-agent-bug-reporting.md` leaves that agent outside the repository's bug-reporting workflow.

### To remove an agent

1. Delete `agents/<agent-name>.md`.
2. Remove its `!agents/<agent-name>.md` entry from `.gitignore`.
3. Remove its routing entry from `rules/10-agent-routing.md`.
4. Remove it from `rules/50-agent-bug-reporting.md`.

> **Tip:** If the agent name appears anywhere else in rules or command prompts, clean those up in the same change. Stale agent names are easy to miss because they are just text.

## Add or Remove Rules

Repository rules live in `rules/` as numbered Markdown files. The current set uses prefixes such as `00-`, `05-`, `10-`, `15-`, `20-`, `25-`, `30-`, `40-`, and `50-`.

### To add a rule

1. Create `rules/NN-your-topic.md`.
2. Pick the prefix based on load order and topic grouping, not just the next number.
3. Add `!rules/NN-your-topic.md` to `.gitignore`.
4. If the rule changes routing, bug-reporting, slash-command behavior, or task flow, update the related rule files too.

### To remove a rule

1. Delete `rules/NN-your-topic.md`.
2. Remove its whitelist line from `.gitignore`.
3. Remove references to it from other rules, scripts, or command prompts.

`settings.json` wires rules into the prompt pipeline through the `UserPromptSubmit` hook:

```json
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
]
```

> **Note:** Rule files and hook behavior should agree with each other. If you change a rule that describes enforcement, make sure the related hook scripts still match the documented behavior.

## Add or Remove Scripts

Scripts live in `scripts/`. In this repo, they are not just files on disk; they are often part of the hook and permission model.

`settings.json` includes an important reminder:

```json
"_scriptsNote": "Script entries must be duplicated in both permissions.allow and allowedTools arrays. When adding new scripts, update BOTH locations."
```

It also shows how scripts are hooked into Claude Code events:

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
```

### To add a script

1. Create the file under `scripts/`.
2. Add a matching `!scripts/<file>` line to `.gitignore`.
3. If the orchestrator needs permission to run it, add the script entry to both `permissions.allow` and `allowedTools` in `settings.json`.
4. If it should run automatically, register it under the appropriate hook in `settings.json`.
5. Add or update tests under `tests/`, and whitelist any new test files in `.gitignore`.

If you are writing a hook script, follow the same stdin/stdout protocol used by `scripts/rule-injector.py`:

```python
output = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": rule_reminder}}

# Output JSON to stdout
print(json.dumps(output, indent=2))
```

### To remove a script

1. Delete the script file.
2. Remove its `.gitignore` whitelist entry.
3. Remove any matching entries from both `permissions.allow` and `allowedTools`.
4. Remove any hook registrations that call it.
5. Remove or update its tests.

> **Warning:** Updating a script file without updating `settings.json` is only half the change. The repo treats hook registration and tool allowlists as part of the script contract.

## Add Slash Commands to a Plugin

Each plugin has two important parts:

- A manifest at `plugins/<plugin>/.claude-plugin/plugin.json`
- One Markdown file per command at `plugins/<plugin>/commands/*.md`

An existing plugin manifest looks like this:

```json
{
  "name": "myk-github",
  "version": "1.4.3",
  "description": "GitHub operations for Claude Code - PR reviews, releases, review handling, and CodeRabbit rate limits",
  "author": {
    "name": "myk-org"
  },
  "repository": "https://github.com/myk-org/claude-code-config",
  "license": "MIT",
  "keywords": ["github", "pr-review", "refine-review", "release", "code-review", "coderabbit", "rate-limit"]
}
```

An existing command file looks like this:

```markdown
---
description: Review a GitHub PR and post inline comments on selected findings
argument-hint: [PR_NUMBER|PR_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task
---
```

### To add a command to an existing plugin

1. Create `plugins/<plugin>/commands/<command-name>.md`.
2. Add frontmatter that matches the existing command files: `description`, `argument-hint`, and `allowed-tools`.
3. Write the command body in the same style as the existing command prompts.
4. Add a matching whitelist entry in `.gitignore`.

The slash-command rule is strict about execution mode:

```text
1. **EXECUTE IT DIRECTLY YOURSELF** - NEVER delegate to any agent
2. **ALL internal operations run DIRECTLY** - scripts, bash commands, everything
3. **Slash command prompt takes FULL CONTROL** - its instructions override general CLAUDE.md rules
```

> **Note:** When you write a command file, write it as the command's own workflow. Do not assume the normal routing rules apply unless the command itself says to call an agent.

> **Warning:** Keep command frontmatter minimal. Existing commands use `description`, `argument-hint`, and `allowed-tools`. Do not add extra keys unless you know Claude Code supports them for command files.

## Add or Remove a Plugin

### To add a plugin

1. Create `plugins/<plugin>/`.
2. Add `plugins/<plugin>/.claude-plugin/plugin.json`.
3. Add `plugins/<plugin>/commands/` and at least one command file.
4. Add the full whitelist block to `.gitignore` for the plugin directory, manifest, commands directory, and each tracked command file.
5. If this plugin should be enabled in the checked-in config, add it to `settings.json` under `enabledPlugins`.
6. Add it to `.claude-plugin/marketplace.json` if it should be installable from this repo's marketplace.

The existing `enabledPlugins` block includes the repository's own plugins:

```json
"enabledPlugins": {
  "myk-review@myk-org": true,
  "myk-github@myk-org": true,
  "myk-acpx@myk-org": true
}
```

### To remove a plugin

1. Delete the plugin directory.
2. Remove its whitelist block from `.gitignore`.
3. Remove its entry from `settings.json` `enabledPlugins` if present.
4. Remove its object from `.claude-plugin/marketplace.json`.
5. Remove references to its commands anywhere else in the repo.

> **Tip:** You do not need to list commands inside `plugin.json`. In this repo, command discovery comes from the files under `plugins/<plugin>/commands/`.

## Add or Remove Marketplace Entries

The repo's marketplace manifest lives at `.claude-plugin/marketplace.json`. Each entry includes a plugin `name`, `source`, `description`, and `version`.

Example:

```json
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
    }
  ]
}
```

### To add a marketplace entry

1. Add a new object under `plugins`.
2. Point `source` at the plugin directory, for example `./plugins/my-plugin`.
3. Use a short description that matches the manifest and command set.
4. Set the version you want to publish.

### To remove a marketplace entry

1. Remove the plugin object from `.claude-plugin/marketplace.json`.
2. Remove the plugin itself if it is no longer part of the repo.
3. Remove any `enabledPlugins` entry if the checked-in config enables it.

> **Note:** The release tooling in `myk_claude_tools/release/detect_versions.py` only scans `pyproject.toml`, `package.json`, `setup.cfg`, `Cargo.toml`, `build.gradle`, `build.gradle.kts`, and Python `__version__` files such as `__init__.py` and `version.py`. It does not automatically update `plugins/*/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`, so plugin and marketplace version metadata must be maintained separately.

## Validate the Change

The repo's local validation lives in `tox.toml`, `pyproject.toml`, and `.pre-commit-config.yaml`.

`tox.toml` runs pytest through `uv`:

```toml
[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

Use these checks from the repository root:

```bash
uv run --group tests pytest tests
uv run --group tests pytest tests/test_rule_enforcer.py tests/test_git_protection.py
uv run --group tests pytest tests/test_detect_versions.py tests/test_bump_version.py
prek run --all-files
```

What those checks cover:

- `uv run --group tests pytest tests` runs the full unit test suite.
- `tests/test_rule_enforcer.py` and `tests/test_git_protection.py` are the important targeted tests when you change hook or guardrail scripts.
- `tests/test_detect_versions.py` and `tests/test_bump_version.py` are the targeted tests when you change release or version-detection logic.
- `prek run --all-files` runs the hooks defined in `.pre-commit-config.yaml`, including `flake8`, `detect-secrets`, `ruff`, `gitleaks`, `mypy`, and `markdownlint`.

> **Warning:** Use `prek`, not `pre-commit`. `scripts/rule-enforcer.py` explicitly blocks direct `pre-commit` commands and tells the caller to use `prek` instead.

`pyproject.toml` is the source of truth for Ruff and Mypy settings, so if you add Python code or release tooling, treat lint and type checks as part of the change, not as optional cleanup.

If you keep the whitelist, routing, bug-reporting coverage, hooks, and marketplace metadata in sync, new extensions behave like the rest of the repository instead of becoming one-off exceptions.
