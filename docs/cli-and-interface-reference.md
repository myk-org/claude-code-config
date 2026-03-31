# CLI and Interface Reference

This repository exposes its public functionality through local interfaces: a Python CLI, Claude Code slash commands, hook scripts, and JSON files passed between them. It does not expose a standalone HTTP API.

> **Note:** The interfaces are intentionally composable. A slash command often calls `myk-claude-tools`, which then reads or writes JSON under `/tmp/claude/` or `.claude/data/`.

## Interface Map

| Surface | Primary files | What you use it for |
|---------|---------------|---------------------|
| CLI | `myk_claude_tools/` | Pull request data, review handling, review analytics, release automation, CodeRabbit rate-limit handling |
| Slash commands | `plugins/*/commands/*.md` | Running those workflows from Claude Code with guided prompts and tool permissions |
| Hooks | `settings.json`, `scripts/` | Enforcing guardrails, injecting context, checking prerequisites, desktop notifications |
| JSON/config files | `settings.json`, `.claude-plugin/*.json`, `/tmp/claude/*.json` | Configuring Claude Code and passing machine-readable data between commands |
| Review database | `.claude/data/reviews.db` | Persisting completed review history for analytics and auto-skip logic |

## `myk-claude-tools` CLI

The package exposes a single console entrypoint:

```23:24:pyproject.toml
[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

Python `>=3.10` is required. The command is designed to be installed as a tool, and the plugin workflows repeatedly check for it before they proceed.

Install it with:

```bash
uv tool install myk-claude-tools
```

At runtime, the CLI is organized into five command groups:

```12:22:myk_claude_tools/cli.py
@click.group()
@click.version_option()
def cli() -> None:
    """CLI utilities for Claude Code plugins."""


cli.add_command(coderabbit_commands.coderabbit, name="coderabbit")
cli.add_command(db_commands.db, name="db")
cli.add_command(pr_commands.pr, name="pr")
cli.add_command(release_commands.release, name="release")
cli.add_command(reviews_commands.reviews, name="reviews")
```

### Shared invocation patterns

`pr diff` and `pr claude-md` accept the same three input styles:

- `owner/repo` plus a PR number
- A full GitHub PR URL
- A bare PR number when you are already inside the target repository

> **Tip:** If you only have a PR number, run the command from the repository you want to inspect. The parser uses `gh repo view` to infer `owner/repo`.

Most GitHub-backed commands depend on a working `gh` CLI login. Review and release workflows also assume `git`, and many slash-command wrappers check for `uv` before continuing.

## `pr` commands

The `pr` group covers three public interfaces:

| Command | Input | Output |
|---------|-------|--------|
| `myk-claude-tools pr diff` | `owner/repo <pr_number>`, PR URL, or PR number | JSON with PR metadata, full diff text, and changed files |
| `myk-claude-tools pr claude-md` | Same three forms as `pr diff` | Plain-text `CLAUDE.md` content, or an empty string if none exists |
| `myk-claude-tools pr post-comment` | `owner/repo <pr_number> <commit_sha> <json_file>` or `-` for stdin | JSON reporting success or failure of posted inline comments |

`pr diff` is the main machine-readable PR payload. Its output shape is defined directly in the implementation:

```216:229:myk_claude_tools/pr/diff.py
    output = {
        "metadata": {
            "owner": pr_info.owner,
            "repo": pr_info.repo,
            "pr_number": pr_info.pr_number,
            "head_sha": head_sha,
            "base_ref": base_ref,
            "title": pr_title,
            "state": pr_state,
        },
        "diff": pr_diff,
        "files": files,
    }
```

The `files` array contains one object per changed file with:

- `path`
- `status`
- `additions`
- `deletions`
- `patch`

`pr claude-md` is intentionally plain text. It checks in this order:

1. Local `./CLAUDE.md` if the current checkout matches the target repo
2. Local `./.claude/CLAUDE.md` if the current checkout matches the target repo
3. Remote `CLAUDE.md` via GitHub
4. Remote `.claude/CLAUDE.md` via GitHub
5. Empty output if nothing is found

> **Tip:** `pr claude-md` is local-first. If you are already in the target repository, it will use your local file before calling GitHub.

`pr post-comment` expects a JSON array of inline comments. Each object must have `path`, `line`, and `body`. The command also recognizes optional severity markers inside `body`:

- `### [CRITICAL]`
- `### [WARNING]`
- `### [SUGGESTION]`

If no marker is present, the comment is treated as a suggestion. The command posts a single GitHub review with a generated summary and the inline comments.

> **Warning:** GitHub only accepts inline comments on lines that are part of the current PR diff. If the path, line number, or commit SHA do not match the diff, `pr post-comment` will fail.

## `reviews` commands

The `reviews` group is the most important interface family in this repository. It handles fetching review data, updating replies, refining pending reviews, and storing completed review history.

| Command | What it does | File behavior |
|---------|--------------|---------------|
| `reviews fetch` | Fetch unresolved review threads for the current branch’s PR, or for a supplied review URL | Writes `/tmp/claude/pr-<number>-reviews.json` and also prints the JSON to stdout |
| `reviews post` | Read a fetched review JSON file, post replies, and resolve threads where appropriate | Updates timestamps in place and can be safely re-run |
| `reviews pending-fetch` | Fetch the authenticated user’s pending PR review | Writes `/tmp/claude/pr-<repo>-<number>-pending-review.json` and prints only the path |
| `reviews pending-update` | Update accepted pending review comments, optionally submit the review | Reads the pending-review JSON file |
| `reviews store` | Persist a completed review JSON file into SQLite | Imports it into `.claude/data/reviews.db` and deletes the JSON file on success |

### `reviews fetch`

`reviews fetch` outputs a categorized JSON document with three arrays: `human`, `qodo`, and `coderabbit`.

```949:960:myk_claude_tools/reviews/fetch.py
        final_output = {
            "metadata": {
                "owner": owner,
                "repo": repo,
                "pr_number": int(pr_number),
                "json_path": str(json_path),
            },
            "human": categorized["human"],
            "qodo": categorized["qodo"],
            "coderabbit": categorized["coderabbit"],
        }
```

Each review entry can include:

- `thread_id`
- `node_id`
- `comment_id`
- `author`
- `path`
- `line`
- `body`
- `replies`
- `source`
- `priority`
- `status`
- `reply`

Depending on the review source and matching history, you may also see:

- `skip_reason`
- `original_status`
- `is_auto_skipped`
- `type`
- `review_id`
- `suggestion_index`

`reviews fetch` also supports review-specific URL fragments, including:

- `#pullrequestreview-<id>`
- `#discussion_r<id>`
- A raw numeric review ID

That matters when you want to focus on one review rather than all unresolved threads.

CodeRabbit support goes further than GitHub’s review-thread API. The implementation also parses CodeRabbit review-body comments and classifies them as:

- `outside_diff_comment`
- `nitpick_comment`
- `duplicate_comment`

Those comment types are important later, because they are replied to via consolidated PR comments rather than normal thread replies.

### Status values and reply behavior

The review-posting workflow is driven by status values stored in the JSON:

```24:34:myk_claude_tools/reviews/post.py
Status handling:
  - addressed: Post reply and resolve thread
  - not_addressed: Post reply and resolve thread (similar to addressed)
  - skipped: Post reply (with skip reason) and resolve thread
  - pending: Skip (not processed yet)
  - failed: Retry posting

Resolution behavior by source:
  - qodo/coderabbit: Always resolve threads after replying
  - human: Only resolve if status is "addressed"; skipped/not_addressed
          threads are not resolved to allow reviewer follow-up
```

In practice, that means:

- Human reviews stay open when you reply with `skipped` or `not_addressed`
- Qodo and CodeRabbit threads are resolved after a reply
- Re-running `reviews post` is safe because it tracks `posted_at` and `resolved_at`
- If some posts fail, the command prints an exact retry command you can run again

`reviews post` also groups body-only comments by reviewer and posts one or more consolidated PR comments mentioning that reviewer. That is how outside-diff, nitpick, and duplicate comments are acknowledged.

### `reviews pending-fetch` and `reviews pending-update`

Pending-review refinement uses a separate JSON format. The output file contains metadata, a flat `comments` list, and a truncated PR diff for context.

```265:277:myk_claude_tools/reviews/pending_fetch.py
    final_output: dict[str, Any] = {
        "metadata": {
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number_int,
            "review_id": review_id,
            "username": username,
            "json_path": str(json_path),
        },
        "comments": comments,
        "diff": diff,
    }
```

Each pending comment includes:

- `id`
- `path`
- `line`
- `side`
- `body`
- `diff_hunk`
- `refined_body`
- `status`

The initial `status` is `pending`, and `refined_body` starts as `null`.

`reviews pending-update` is deliberately conservative:

- It only updates comments whose `status` is `accepted`
- It only updates when `refined_body` is non-empty
- It skips updates if the refined text is unchanged from the original
- It only submits the review when both conditions are true:
  - `metadata.submit_action` is set to `COMMENT`, `APPROVE`, or `REQUEST_CHANGES`
  - The CLI was run with `--submit`

> **Warning:** `reviews store` deletes the source JSON file after it has been imported into `.claude/data/reviews.db`. If you want to keep a copy, duplicate it before running the store step.

## `db` commands

The `db` group is the read-only analytics interface over the review history database. By default it opens:

- `<git-root>/.claude/data/reviews.db`

You can override that with `--db-path` on every command.

### Available subcommands

| Command | What it returns |
|---------|-----------------|
| `db stats` | Review stats grouped by source or reviewer |
| `db patterns` | Recurring dismissed comment patterns |
| `db dismissed` | Previously dismissed comments for a repository |
| `db query` | A raw SQL query result |
| `db find-similar` | The closest previously dismissed comment for a new path/body pair |

### Important safety rules

`db query` is intentionally locked down:

- It only accepts `SELECT` and `WITH` queries
- It rejects multiple SQL statements
- It blocks dangerous keywords such as `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `DETACH`, and `PRAGMA`

That behavior is enforced in code and covered by tests.

### Actual stdin contract for `find-similar`

The implementation expects one JSON object on stdin with `path` and `body` fields:

```163:172:myk_claude_tools/db/commands.py
        Reads JSON from stdin with 'path' and 'body' fields. Uses exact path match
        combined with body similarity (Jaccard word overlap). This is useful for
        auto-skip logic: if a similar comment was previously dismissed with a reason,
        the same reason may apply.

        Examples:

            # Find similar comment
            echo '{"path": "foo.py", "body": "Add error handling..."}' | \
                myk-claude-tools db find-similar --owner myk-org --repo claude-code-config --json
```

> **Warning:** `db find-similar` expects a single JSON object, not an array. The CLI implementation and tests both use one object with `path` and `body`.

### Database tables

If you use `db query`, these are the key tables and columns you will interact with:

| Table | Key columns |
|-------|-------------|
| `reviews` | `id`, `pr_number`, `owner`, `repo`, `commit_sha`, `created_at` |
| `comments` | `review_id`, `source`, `thread_id`, `node_id`, `comment_id`, `author`, `path`, `line`, `body`, `priority`, `status`, `reply`, `skip_reason`, `posted_at`, `resolved_at`, `type` |

The `type` column is especially useful when working with CodeRabbit body comments such as `outside_diff_comment`, `nitpick_comment`, and `duplicate_comment`.

## `release` commands

The `release` group exposes the release workflow in four parts:

| Command | What it does |
|---------|--------------|
| `release info` | Validates the repo state and returns commits since the last matching tag |
| `release detect-versions` | Finds version files in the current repository |
| `release bump-version` | Updates detected version strings in place |
| `release create` | Creates a GitHub release from a changelog file |

### `release info`

`release info` returns JSON with:

- `metadata`
- `validations`
- `last_tag`
- `all_tags`
- `commits`
- `commit_count`
- `is_first_release`
- `target_branch`
- `tag_match`

The `validations` block tells you whether the repo is ready to release:

- On the target branch
- Working tree clean
- `git fetch` succeeded
- Synced with remote

If validation fails, the command still returns JSON, but it skips expensive tag and commit collection.

> **Tip:** If you are on a branch named like `v2.10`, `release info` auto-detects it as the target branch and automatically narrows tag matching to `v2.10.*`.

### `release detect-versions`

Version-file detection covers several common ecosystems:

```167:174:myk_claude_tools/release/detect_versions.py
_ROOT_SCANNERS: list[tuple[str, Callable[[Path], str | None], str]] = [
    ("pyproject.toml", _parse_pyproject_toml, "pyproject"),
    ("package.json", _parse_package_json, "package_json"),
    ("setup.cfg", _parse_setup_cfg, "setup_cfg"),
    ("Cargo.toml", _parse_cargo_toml, "cargo"),
    ("build.gradle", _parse_gradle, "gradle"),
    ("build.gradle.kts", _parse_gradle, "gradle"),
]
```

It also scans Python `__version__` assignments in `__init__.py` and `version.py`.

Tests confirm several important details:

- `pyproject.toml` detection only reads `[project]`, not unrelated sections
- `setup.cfg` detection only reads `[metadata]`
- `Cargo.toml` detection only reads `[package]`
- Dynamic `setup.cfg` versions such as `attr:` or `file:` are skipped
- Common generated or vendor directories like `.venv`, `node_modules`, `.tox`, and `target` are ignored

The command prints JSON in this shape:

- `version_files`: an array of `{path, current_version, type}`
- `count`: number of detected version files

### `release bump-version`

`release bump-version` updates the files returned by `detect-versions`. Its output is machine-readable and reports:

- `status`
- `version`
- `updated`
- `skipped`
- `error` on failure

It also validates the version string before doing any file writes.

> **Warning:** Pass `1.2.3`, not `v1.2.3`. The implementation rejects versions with a leading `v` and tells you to use the bare version number instead.

Tests verify that `bump-version`:

- Only updates the correct section in multi-section files
- Preserves unrelated content
- Fails fast when `--files` does not match detected version files
- Returns skipped reasons instead of silently ignoring failures

### `release create`

`release create` expects:

- `owner/repo`
- A tag such as `v1.2.3`
- A path to a changelog file

It calls `gh release create` and returns JSON with:

- `status`
- `tag`
- `url`
- `prerelease`
- `draft`

If the tag is not semantic-version-like, the command warns to stderr but still attempts the release.

## `coderabbit` commands

The `coderabbit` group exposes two composable commands:

| Command | What it does |
|---------|--------------|
| `coderabbit check` | Inspect the latest CodeRabbit summary comment and report whether the PR is rate-limited |
| `coderabbit trigger` | Wait if requested, post `@coderabbitai review`, and poll until the review starts |

`coderabbit check` returns one of these JSON shapes:

- `{"rate_limited": false}`
- `{"rate_limited": true, "wait_seconds": <seconds>, "comment_id": <id>}`

The command parses CodeRabbit’s own comment body for the wait time, and the tests cover both minute/second and second-only formats.

`coderabbit trigger` behaves like this:

- Optional initial sleep via `--wait`
- Post `@coderabbitai review`
- Poll every 60 seconds
- Give up after 10 attempts

> **Tip:** The polling logic treats two consecutive “summary comment disappeared” checks as success. That matches CodeRabbit replacing the rate-limit comment when the new review begins.

## Slash commands and plugin interfaces

Claude Code plugin commands live under `plugins/*/commands/*.md`. Each command file begins with YAML frontmatter that defines the public interface seen in Claude Code:

```1:5:plugins/myk-github/commands/pr-review.md
---
description: Review a GitHub PR and post inline comments on selected findings
argument-hint: [PR_NUMBER|PR_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task
---
```

At the plugin level, metadata comes from `plugins/*/.claude-plugin/plugin.json`, and the root marketplace index comes from `.claude-plugin/marketplace.json`:

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
```

### `myk-github`

`myk-github` is the GitHub workflow plugin. Its public commands are:

| Slash command | What it wraps |
|---------------|---------------|
| `/myk-github:pr-review` | `pr diff`, `pr claude-md`, review agents, and optionally `pr post-comment` |
| `/myk-github:review-handler` | `reviews fetch`, local fixes, tests, `reviews post`, `reviews store`; optional `--autorabbit` polling loop |
| `/myk-github:refine-review` | `reviews pending-fetch` plus a refinement and submission flow |
| `/myk-github:release` | `release info`, `detect-versions`, `bump-version`, `release create` |
| `/myk-github:coderabbit-rate-limit` | `coderabbit check` and `coderabbit trigger` |

These commands are documented as full workflows, not just wrappers. That means their public interface includes:

- Required prerequisites
- Expected arguments
- Temp-file conventions under `/tmp/claude/`
- User-decision points
- Allowed tool list

### `myk-review`

`myk-review` provides two local workflows:

| Slash command | What it does |
|---------------|--------------|
| `/myk-review:local [BRANCH]` | Review uncommitted changes or diff against a branch using three review agents in parallel |
| `/myk-review:query-db ...` | Run the `db` analytics commands through Claude Code |

`/myk-review:local` is intentionally simple: it chooses either `git diff HEAD` or `git diff "<branch>"...HEAD`, then sends that diff to the review agents.

### `myk-acpx`

`myk-acpx` is different from the rest of the repo because it does not call `myk-claude-tools`. It is a slash-command interface for the external `acpx` CLI.

Public inputs include:

- One agent name or a comma-separated list of agents
- Optional `--fix`, `--peer`, or `--exec`
- Optional `--model <model>`
- The prompt text

Supported agent names come directly from the command file and include:

- `pi`
- `openclaw`
- `codex`
- `claude`
- `gemini`
- `cursor`
- `copilot`
- `droid`
- `iflow`
- `kilocode`
- `kimi`
- `kiro`
- `opencode`
- `qwen`

Important validation rules:

- `--fix`, `--peer`, and `--exec` are mutually exclusive in the combinations documented by the command
- Multiple agents are allowed, but not with `--fix`
- `--model` cannot be repeated
- An agent name and prompt are both required

In day-to-day use:

- Default mode is a persistent, read-only session
- `--exec` is one-shot and stateless
- `--fix` allows file writes
- `--peer` runs a review loop where the peer agent re-checks the code after every fix round

## Hooks and `settings.json`

The checked-in `settings.json` is the central runtime configuration file for Claude Code. It defines:

- `permissions.allow`
- `allowedTools`
- `hooks`
- `statusLine`
- `enabledPlugins`
- `extraKnownMarketplaces`
- `env`

The hook registration is explicit and machine-readable:

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

### Hook events and contracts

| Hook | Script or handler | Contract |
|------|-------------------|----------|
| `Notification` | `scripts/my-notifier.sh` | Reads JSON from stdin and expects a `.message` field |
| `PreToolUse` | `scripts/rule-enforcer.py` | Reads hook JSON with `tool_name` and `tool_input`; prints deny JSON when blocking |
| `PreToolUse` | `scripts/git-protection.py` | Same hook JSON shape; denies protected `git commit` and `git push` operations |
| `PreToolUse` | Inline prompt gate in `settings.json` | Returns JSON with `decision: approve|block|ask` for destructive Bash commands |
| `UserPromptSubmit` | `scripts/rule-injector.py` | Prints `hookSpecificOutput.additionalContext` |
| `SessionStart` | `scripts/session-start-check.sh` | Prints a human-readable `MISSING_TOOLS_REPORT` when prerequisites are missing |

### `rule-enforcer.py`

`rule-enforcer.py` blocks direct `python`, `python3`, `pip`, `pip3`, and `pre-commit` Bash commands. Instead, it instructs users and agents to use:

- `uv run`
- `uvx`
- `prek`

The deny payload is a standard Claude Code hook response:

```35:50:scripts/rule-enforcer.py
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
```

Tests confirm two user-visible details:

- Allowed commands such as `uv run`, `uvx`, `git status`, and `ls` produce no stdout at all
- The script fails open on malformed input or internal exceptions

### `git-protection.py`

`git-protection.py` protects the repository against commits and pushes in the wrong place. It blocks:

- `git commit` on `main` or `master`
- `git push` on `main` or `master`
- Commits or pushes on branches whose PR is already merged
- Commits in detached HEAD state

It allows `git commit --amend` when the branch is ahead of its remote.

This hook is stricter than `rule-enforcer.py`:

- It fails closed on internal errors
- It checks GitHub PR merge state when possible
- It falls back to local merge checks when needed

> **Warning:** If you adopt this config as-is, direct commits and pushes to protected or already-merged branches are intentionally blocked by the hook layer, not just by convention.

### `session-start-check.sh`

`session-start-check.sh` is the dependency-reporting hook. It checks for:

- Critical: `uv`
- Optional or situational: `gh`, `jq`, `gawk`, `prek`, `mcpl`
- Required review plugins: `pr-review-toolkit`, `superpowers`, `feature-dev`

If something is missing, it prints a `MISSING_TOOLS_REPORT:` block with installation guidance and still exits `0`, so it informs rather than blocks.

### `my-notifier.sh`

`my-notifier.sh` is the desktop-notification interface. It:

- Requires `jq` and `notify-send`
- Reads stdin JSON
- Extracts `.message`
- Sends `notify-send --wait "Claude: <message>"`

If the message is missing or the tools are absent, it exits non-zero.

### `statusLine`

`settings.json` also configures a status-line command: `bash ~/.claude/statusline.sh`.

That script reads JSON from stdin and builds a one-line status string from fields such as:

- `.model.display_name`
- `.workspace.current_dir`
- `.context_window.used_percentage`
- `.cost.total_lines_added`
- `.cost.total_lines_removed`

This is a JSON-based interface too, even though it is not a hook.

> **Note:** The file also contains a maintenance reminder: when you add or change script entries, keep `permissions.allow` and `allowedTools` in sync.

## Review JSON files

The repo’s review commands use local JSON files as a first-class interface. These files live under `/tmp/claude/`, and the implementations explicitly create the directory with `0700` permissions.

### Fetched review file

`reviews fetch` writes a file like:

- `/tmp/claude/pr-123-reviews.json`

Key top-level fields:

- `metadata.owner`
- `metadata.repo`
- `metadata.pr_number`
- `metadata.json_path`
- `human`
- `qodo`
- `coderabbit`

Key per-comment fields:

- `thread_id`
- `node_id`
- `comment_id`
- `author`
- `path`
- `line`
- `body`
- `replies`
- `source`
- `priority`
- `status`
- `reply`

Optional per-comment fields:

- `skip_reason`
- `original_status`
- `is_auto_skipped`
- `posted_at`
- `resolved_at`
- `type`

### Pending review file

`reviews pending-fetch` writes a file like:

- `/tmp/claude/pr-owner-repo-123-pending-review.json`

Key top-level fields:

- `metadata.owner`
- `metadata.repo`
- `metadata.pr_number`
- `metadata.review_id`
- `metadata.username`
- `metadata.json_path`
- `comments`
- `diff`

Key per-comment fields:

- `id`
- `path`
- `line`
- `side`
- `body`
- `diff_hunk`
- `refined_body`
- `status`

The `diff` field is intentionally capped at 50,000 characters so the file remains manageable.

## Plugin metadata files

The plugin layer uses two JSON metadata formats.

### Per-plugin `plugin.json`

Each plugin defines:

- `name`
- `version`
- `description`
- `author`
- `repository`
- `license`
- `keywords`

That is the metadata Claude Code and marketplace tooling can display.

### Root marketplace manifest

`.claude-plugin/marketplace.json` is the index for this repository’s plugin marketplace. It names the marketplace and points each plugin name at its source directory.

For end users, that means the canonical public plugin names are:

- `myk-github`
- `myk-review`
- `myk-acpx`

## Automation and validation surfaces

This repository does not check in a GitHub Actions workflow or another CI pipeline definition. The automation surfaces you can inspect in-tree are local.

### `tox.toml`

The test runner configuration is intentionally small:

```1:7:tox.toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

That means the supported local test entrypoint is:

- `tox` via `uv`
- Or the equivalent direct `uv run --group tests pytest tests`

### `.pre-commit-config.yaml`

The pre-commit configuration exposes another important interface surface. It includes hooks for:

- File sanity checks from `pre-commit-hooks`
- `flake8`
- `detect-secrets`
- `ruff`
- `ruff-format`
- `gitleaks`
- `mypy`
- `markdownlint`

Because `rule-enforcer.py` blocks direct `pre-commit` commands, this configuration is meant to be run through `prek` rather than `pre-commit`.

> **Note:** There is no checked-in `.github/workflows/` directory in this repository. If you are looking for automation behavior, the in-repo interfaces to inspect are `tox.toml`, `.pre-commit-config.yaml`, the release commands, and the Claude Code hooks in `settings.json`.
