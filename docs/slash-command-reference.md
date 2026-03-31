# Slash Command Reference

This repository bundles eight slash commands across three plugins:

| Plugin | Command | Best for | Triggered workflow |
| --- | --- | --- | --- |
| `myk-github` | `/myk-github:coderabbit-rate-limit` | Waiting out a CodeRabbit cooldown | `coderabbit check` -> `coderabbit trigger` |
| `myk-github` | `/myk-github:pr-review` | Reviewing an open GitHub PR and posting selected findings | `pr diff` -> `pr claude-md` -> 3 reviewer tasks -> `pr post-comment` |
| `myk-github` | `/myk-github:refine-review` | Polishing your own pending GitHub review comments before submission | `reviews pending-fetch` -> AI refinement -> `reviews pending-update` |
| `myk-github` | `/myk-github:release` | Validating, versioning, and publishing a GitHub release | `release info` -> `release detect-versions` -> optional `release bump-version` -> `release create` |
| `myk-github` | `/myk-github:review-handler` | Working through human, Qodo, and CodeRabbit feedback end to end | `reviews fetch` -> decision/fix/test loop -> `reviews post` -> `reviews store` |
| `myk-review` | `/myk-review:local` | Reviewing local changes before or instead of a PR | `git diff` -> 3 reviewer tasks |
| `myk-review` | `/myk-review:query-db` | Querying stored review history and analytics | `db stats|patterns|dismissed|query|find-similar` |
| `myk-acpx` | `/myk-acpx:prompt` | Sending prompts to ACP-compatible coding agents through `acpx` | `acpx` session, exec, fix, or peer workflow |

Most of the GitHub and review commands are orchestration layers over the bundled helper CLI:

```toml
[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

The slash command metadata itself is defined in each command file. A typical example looks like this:

```yaml
description: Review a GitHub PR and post inline comments on selected findings
argument-hint: [PR_NUMBER|PR_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task
```

> **Note:** The `allowed-tools` values below come from each command's frontmatter. They describe the command's intended tool budget. Your local Claude Code installation still needs the matching executables and permissions.

## Shared Prerequisites

- `myk-claude-tools` backs most `myk-github` commands and `/myk-review:query-db`.
- `gh` is required for GitHub PR, comment, and release operations.
- `git` is required anywhere the workflow inspects or validates the local worktree.
- `acpx` plus the underlying agent CLI are required for `/myk-acpx:prompt`.
- `/myk-github:pr-review` and `/myk-review:local` both expect the reviewer agents `superpowers:code-reviewer`, `pr-review-toolkit:code-reviewer`, and `feature-dev:code-reviewer` to be available.

> **Tip:** When a command checks for `myk-claude-tools` and cannot find it, the command docs consistently instruct Claude to offer `uv tool install myk-claude-tools`.

## Allowed Tools Cheat Sheet

| Tool token | What it means in practice |
| --- | --- |
| `Bash(myk-claude-tools:*)` | Run the repo's helper CLI subcommands such as `pr diff`, `reviews fetch`, or `release info` |
| `Bash(gh:*)` | Call GitHub CLI for PRs, GraphQL, comments, and releases |
| `Bash(git:*)` | Inspect or update local git state |
| `Bash(acpx:*)` | Run ACP-compatible agent CLIs through `acpx` |
| `AskUserQuestion` | Require an explicit choice or confirmation from you |
| `Task` | Launch structured parallel review tasks |
| `Agent` | Delegate implementation or specialist analysis work |
| `Edit` / `Write` | Update temp handoff files, or in `myk-acpx:prompt`, allow writable workflows |
| `Read`, `Glob`, `Grep` | Read and search the workspace, mainly for `myk-acpx:prompt` |

## `myk-github`

The `myk-github` plugin bundles GitHub-facing workflows: PR review, review follow-up, release automation, and CodeRabbit cooldown handling.

### `/myk-github:coderabbit-rate-limit`

Use this when CodeRabbit has rate-limited a PR and you want Claude to wait, retrigger the review, and watch for it to start.

- `argument-hint`: `[PR_NUMBER|PR_URL]`
- `allowed-tools`: `Bash(myk-claude-tools:*)`, `Bash(uv:*)`, `Bash(git:*)`, `Bash(gh:*)`

Actual usage examples:

```text
/myk-github:coderabbit-rate-limit
/myk-github:coderabbit-rate-limit 123
/myk-github:coderabbit-rate-limit https://github.com/owner/repo/pull/123
```

What it does:

1. Resolves the PR from a URL, a PR number, or the current branch.
2. Runs the helper CLI to check CodeRabbit's current status.
3. If the PR is rate-limited, adds a 30-second safety buffer and triggers a fresh `@coderabbitai review`.
4. Polls every 60 seconds for up to 10 minutes to confirm the review has started.

The core helper calls are exactly these:

```bash
myk-claude-tools coderabbit check <owner/repo> <pr_number>
myk-claude-tools coderabbit trigger <owner/repo> <pr_number> --wait <wait_seconds + 30>
```

A few implementation details matter here:

- The rate-limit detector looks for CodeRabbit's summary comment on the PR and parses the cooldown text from that comment.
- The trigger flow treats two consecutive "summary comment disappeared" checks as success, because that usually means CodeRabbit replaced the summary while starting a new review.
- If the PR is not rate-limited, the command exits early instead of waiting.

> **Warning:** This workflow depends on CodeRabbit's summary comment being present on the PR. If that comment is missing, the check step fails instead of guessing.

### `/myk-github:pr-review`

Use this when you want Claude to review an actual GitHub PR, merge findings from three review agents, and post only the findings you approve.

- `argument-hint`: `[PR_NUMBER|PR_URL]`
- `allowed-tools`: `Bash(myk-claude-tools:*)`, `Bash(uv:*)`, `Bash(git:*)`, `Bash(gh:*)`, `AskUserQuestion`, `Task`

Actual usage examples:

```text
/myk-github:pr-review
/myk-github:pr-review 123
/myk-github:pr-review https://github.com/owner/repo/pull/123
```

What it does:

1. Detects the PR from the current branch when you do not pass an argument.
2. Fetches PR metadata, full diff text, and changed-file data through `myk-claude-tools pr diff`.
3. Fetches project rules through `myk-claude-tools pr claude-md`. The helper checks local `CLAUDE.md` or `.claude/CLAUDE.md` first when you are already in the target repo, then falls back to GitHub.
4. Runs three review agents in parallel and merges their findings.
5. Shows the findings grouped by severity and asks which ones to post.
6. Posts the selected findings back to GitHub as a single review.

The reviewer trio is defined directly in the command workflow:

```text
- superpowers:code-reviewer
- pr-review-toolkit:code-reviewer
- feature-dev:code-reviewer
```

One important detail for fork PRs: the command uses `gh repo view` to determine the base repository context. That avoids accidentally treating the fork as the target repo.

When the posting step runs, it uses the helper CLI's JSON contract for inline review comments:

```python
JSON Input Format (array of comments):
    [
        {
            "path": "src/main.py",
            "line": 42,
            "body": "### [CRITICAL] SQL Injection\n\nDescription..."
        },
        {
            "path": "src/utils.py",
            "line": 15,
            "body": "### [WARNING] Missing error handling\n\nDescription..."
        }
    ]

Severity Markers:
    - ### [CRITICAL] Title - For critical security/functionality issues
    - ### [WARNING] Title  - For important but non-critical issues
    - ### [SUGGESTION] Title - For code improvements and suggestions
```

That means the final post back to GitHub is not just free-form prose. It is a structured review with per-line comments and a summary body.

> **Tip:** Inline review comments only work on lines that are actually part of the PR diff. If posting fails, the helper CLI specifically points to stale line numbers, wrong file paths, or a stale PR head SHA as the most common causes.

### `/myk-github:refine-review`

Use this when you have already started a review in GitHub, added draft comments, and want Claude to polish those comments before you submit them.

- `argument-hint`: `<PR_URL>`
- `allowed-tools`: `Bash(myk-claude-tools:*)`, `Bash(uv:*)`, `AskUserQuestion`, `Edit(/tmp/claude/**)`, `Write(/tmp/claude/**)`

Actual usage example:

```text
/myk-github:refine-review https://github.com/owner/repo/pull/123
```

What it does:

1. Fetches your own pending review with `myk-claude-tools reviews pending-fetch "<PR_URL>"`.
2. Loads the pending review comments plus PR diff context from a temp JSON file.
3. Generates refined wording for each comment while preserving the original technical intent.
4. Shows you each original comment alongside the refined version.
5. Lets you accept all, accept specific comments, keep originals, cancel, or replace individual comments with custom text.
6. Updates the temp JSON and runs `myk-claude-tools reviews pending-update`, optionally with `--submit`.

The backing helper calls are straightforward:

```bash
myk-claude-tools reviews pending-fetch "<PR_URL>"
myk-claude-tools reviews pending-update "<json_path>" --submit
```

The workflow is intentionally conservative:

- It only updates `refined_body` and `status` for each comment during the accept/reject step.
- It only submits the review if you explicitly choose a submit action.
- The lower-level fetcher only works against the authenticated user's latest `PENDING` review on that PR.

> **Warning:** This command requires a full PR URL. A bare PR number is not enough.

> **Note:** The pending-review fetcher stores diff context in the temp JSON, but it truncates very large diffs after 50,000 characters. On very large PRs, refinement happens with shortened context instead of the full diff.

### `/myk-github:release`

Use this when you want Claude to validate the repo state, generate a conventional-commit changelog, optionally bump version files, and publish a GitHub release.

- `argument-hint`: `[--dry-run] [--prerelease] [--draft] [--target <branch>] [--tag-match <pattern>]`
- `allowed-tools`: `Bash(myk-claude-tools:*)`, `Bash(uv:*)`, `Bash(git:*)`, `Bash(gh:*)`, `AskUserQuestion`

Actual usage examples:

```text
/myk-github:release
/myk-github:release --dry-run
/myk-github:release --prerelease
/myk-github:release --draft
```

What it does:

1. Runs `myk-claude-tools release info` to validate branch, worktree cleanliness, and sync with remote.
2. Runs `myk-claude-tools release detect-versions` to discover version files in the current repository.
3. Parses commits since the last matching tag and proposes a major, minor, or patch bump using conventional-commit rules.
4. Shows you the proposed version and changelog, and lets you override the bump type or exclude detected version files.
5. If version files are being updated, runs `myk-claude-tools release bump-version`.
6. Creates a bump branch, commits, pushes, opens a PR, and merges it.
7. Creates the GitHub release with `myk-claude-tools release create`.

The release helper exposes these subcommands:

```bash
myk-claude-tools release info --target <branch> --tag-match <pattern>
myk-claude-tools release detect-versions
myk-claude-tools release bump-version <VERSION> --files <file1> --files <file2>
myk-claude-tools release create <owner/repo> <tag> "<changelog_file>"
```

Version detection is broader than just Python packages. The implementation scans these root-level files:

```python
_ROOT_SCANNERS = [
    ("pyproject.toml", _parse_pyproject_toml, "pyproject"),
    ("package.json", _parse_package_json, "package_json"),
    ("setup.cfg", _parse_setup_cfg, "setup_cfg"),
    ("Cargo.toml", _parse_cargo_toml, "cargo"),
    ("build.gradle", _parse_gradle, "gradle"),
    ("build.gradle.kts", _parse_gradle, "gradle"),
]
```

It also searches Python `__init__.py` and `version.py` files for `__version__`.

Important behaviors to know:

- If you are already on a version branch such as `v2.10`, the validation step auto-detects that branch as the target and scopes tag discovery to `v2.10.*`.
- The bump step expects a version without the `v` prefix, such as `1.2.0`.
- If `uv.lock` exists, the workflow regenerates it after bumping version files.
- The low-level `release create` helper warns if the tag does not look like semantic versioning (`vX.Y.Z`), but it does not hard-block the release.

User choices during approval include:

- `yes` to continue with the proposed version and all detected files
- `major`, `minor`, or `patch` to override the proposed bump
- `exclude N` to remove one detected version file from the bump
- `no` to cancel the release

> **Warning:** This workflow can modify version files, create a branch, push commits, open and merge a PR, and publish a GitHub release. Use `--dry-run` first if you want a preview without creating anything.

### `/myk-github:review-handler`

Use this when you want the full PR review follow-up workflow: fetch all review feedback, choose what to address, delegate fixes, run tests, reply to reviewers, and store the outcome in the local review database.

- `argument-hint`: `[--autorabbit] [REVIEW_URL]`
- `allowed-tools`: `Bash(myk-claude-tools:*)`, `Bash(uv:*)`, `Bash(git:*)`, `Bash(gh:*)`, `AskUserQuestion`, `Task`, `Agent`

Actual usage examples:

```text
/myk-github:review-handler
/myk-github:review-handler https://github.com/owner/repo/pull/123#pullrequestreview-456
/myk-github:review-handler --autorabbit
```

What it does:

1. Runs `myk-claude-tools reviews fetch`, usually against the current branch's PR.
2. Groups unresolved feedback by source: human, Qodo, and CodeRabbit.
3. Shows every item in mandatory tables, including auto-skipped items, and asks you what to address.
4. Delegates approved fixes to specialist agents with the full review thread, not a summary.
5. Requires a fully green test run before moving on.
6. Optionally asks whether to commit and push your changes.
7. Posts replies with `myk-claude-tools reviews post`.
8. Stores the finished review record in `.claude/data/reviews.db` with `myk-claude-tools reviews store`.

The table format is defined directly in the command:

```text
## Review Items: {source} ({total} total, {auto_skipped} auto-skipped)

| # | Priority | File | Line | Summary | Status |
|---|----------|------|------|---------|--------|
| 1 | HIGH | src/storage.py | 231 | Backfill destroys historical chronology | Pending |
| 2 | MEDIUM | src/html_report.py | 1141 | Add/delete leaves badges stale | Pending |
| 3 | LOW | src/utils.py | 42 | Unused import | Auto-skipped (skipped): "style only" |
| 4 | LOW | src/config.py | 15 | Missing validation | Auto-skipped (addressed): "added in prev PR" |
```

The response options are also part of the command contract:

```text
Respond with:
- 'yes' / 'no' (per item number — if 'no', ask for a reason)
- 'all' — address all remaining pending items
- 'skip human/qodo/coderabbit' — skip remaining from that source (ask for a reason)
- 'skip ai' — skip all AI sources (qodo + coderabbit) (ask for a reason)
```

A few user-facing details are easy to miss:

- `reviews fetch` auto-detects the PR from the current branch and can fall back to an `upstream` remote when needed.
- CodeRabbit review bodies can contain outside-diff, nitpick, and duplicate comments that do not have normal GitHub review threads. The post step handles those through consolidated PR comments instead of per-thread replies.
- Human threads with `skipped` or `not_addressed` status stay unresolved on purpose, so the reviewer can follow up. Qodo and CodeRabbit replies are resolved after posting.
- After a successful `reviews store`, the JSON handoff file is deleted and the database entry is appended rather than updated.

The storage step is described in the helper CLI itself:

```python
@reviews.command("store")
@click.argument("json_path")
def reviews_store(json_path: str) -> None:
    """Store completed review to database.

    Stores the completed review JSON to SQLite database for analytics.
    The database is stored at: <project-root>/.claude/data/reviews.db

    This command should run AFTER the review flow completes.
    The JSON file is deleted after successful storage.
```

> **Note:** Previous skip decisions are used for auto-skip suggestions, but those items are still shown in the table so you can override them.

> **Tip:** If `myk-claude-tools reviews post` reports failures, rerun the exact retry command it prints. The post helper is designed to retry only entries that have not been successfully posted yet.

> **Warning:** `--autorabbit` does not stop on its own. It waits 5 minutes between checks, handles CodeRabbit rate limits automatically, and keeps looping until you stop it.

## `myk-review`

The `myk-review` plugin covers local review before GitHub and post-review analytics after GitHub.

### `/myk-review:local`

Use this when you want a three-agent review of your local changes without opening or touching a GitHub PR.

- `argument-hint`: `[BRANCH]`
- `allowed-tools`: `Bash(git:*)`, `Task`, `AskUserQuestion`

Actual usage examples:

```text
/myk-review:local
/myk-review:local main
/myk-review:local feature/branch
```

What it does:

1. If you pass a branch, it reviews `git diff "$ARGUMENTS"...HEAD`.
2. If you do not pass a branch, it reviews `git diff HEAD`, which covers tracked staged and unstaged changes.
3. It sends the diff to the same three review agents used by `/myk-github:pr-review`.
4. It merges and deduplicates findings and presents them as critical issues, warnings, and suggestions.

The diff commands are taken directly from the command file:

```bash
git diff "$ARGUMENTS"...HEAD
git diff HEAD
```

This command does not post comments anywhere. It is purely a local review surface.

> **Tip:** Use `/myk-review:local` before opening a PR, and `/myk-github:pr-review` after the PR exists. The review model is similar, but the data source is different.

### `/myk-review:query-db`

Use this when you want analytics and historical context from the review database created by `/myk-github:review-handler`.

- `argument-hint`: `[stats|patterns|dismissed|query|find-similar] [OPTIONS]`
- `allowed-tools`: `Bash(myk-claude-tools:*)`, `Bash(uv:*)`

Common slash-command examples from the command definition:

```text
/myk-review:query-db stats --by-source
/myk-review:query-db stats --by-reviewer
/myk-review:query-db patterns --min 2
/myk-review:query-db dismissed --owner X --repo Y
/myk-review:query-db query "SELECT * FROM comments WHERE status='skipped' LIMIT 10"
```

Subcommands:

| Subcommand | What it does |
| --- | --- |
| `stats` | Shows addressed rates by source or by reviewer |
| `patterns` | Finds recurring dismissed comments that look like repeat feedback |
| `dismissed` | Returns dismissed review comments for one repo |
| `query` | Runs a raw read-only SQL query |
| `find-similar` | Looks for a previously dismissed comment with the same path and similar body text |

The database location is fixed by the helper code:

- Default path: `<git-root>/.claude/data/reviews.db`
- Override: `--db-path`

A few behavior details are worth knowing:

- `stats` defaults to `--by-source` if you do not pass `--by-source` or `--by-reviewer`.
- `--by-source` and `--by-reviewer` are mutually exclusive.
- `patterns` groups recurring comments by path plus approximate body similarity, not only exact string matches.
- `find-similar` requires both `--owner` and `--repo`, and it expects a single JSON object on stdin.

The actual helper example for `find-similar` is:

```bash
echo '{"path": "foo.py", "body": "Add error handling..."}' | \
    myk-claude-tools db find-similar --owner myk-org --repo claude-code-config --json
```

Read-only SQL is enforced in code:

```python
if not sql_upper.startswith(("SELECT", "WITH")):
    raise ValueError("Only SELECT/CTE queries are allowed for safety")
```

That means `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, and other write operations are rejected.

> **Warning:** `query` is intentionally read-only. It is for analytics and exploration, not for editing the review database.

> **Note:** The `dismissed` view intentionally includes `not_addressed` and `skipped` comments, plus addressed body-only comments that do not have normal GitHub review threads. That behavior supports later auto-skip decisions.

## `myk-acpx`

The `myk-acpx` plugin is the bridge to `acpx`, which in turn can drive multiple ACP-compatible coding agents from one slash command.

### `/myk-acpx:prompt`

Use this when you want to send a prompt to one or more external coding agents such as Codex, Gemini, Cursor, or Claude through `acpx`.

- `argument-hint`: `<agent>[,agent2,...] [--fix | --peer | --exec] [--model <model>] <prompt>`
- `allowed-tools`: `Bash(acpx:*)`, `Bash(git:*)`, `AskUserQuestion`, `Agent`, `Edit`, `Write`, `Read`, `Glob`, `Grep`

Actual usage examples:

```text
/myk-acpx:prompt codex fix the tests
/myk-acpx:prompt cursor review this code
/myk-acpx:prompt gemini explain this function
/myk-acpx:prompt codex --exec summarize this repo
/myk-acpx:prompt codex --model o3-pro review the architecture
/myk-acpx:prompt codex --fix fix the code quality issues
/myk-acpx:prompt gemini --peer review this code
/myk-acpx:prompt codex --peer --model o3-pro review the architecture
/myk-acpx:prompt cursor,codex review this code
/myk-acpx:prompt cursor,gemini,codex --peer review the architecture
```

Supported agents are declared in the command file:

| Agent | Wraps |
| --- | --- |
| `pi` | Pi Coding Agent |
| `openclaw` | OpenClaw ACP bridge |
| `codex` | Codex CLI (OpenAI) |
| `claude` | Claude Code |
| `gemini` | Gemini CLI |
| `cursor` | Cursor CLI |
| `copilot` | GitHub Copilot CLI |
| `droid` | Factory Droid |
| `iflow` | iFlow CLI |
| `kilocode` | Kilocode |
| `kimi` | Kimi CLI |
| `kiro` | Kiro CLI |
| `opencode` | OpenCode |
| `qwen` | Qwen Code |

Modes:

| Mode | Flag | Behavior |
| --- | --- | --- |
| Session | none | Read-only by default, with session persistence |
| Exec | `--exec` | Read-only, one-shot, no session persistence |
| Fix | `--fix` | Writable run, single agent only |
| Peer | `--peer` | Read-only AI-to-AI review loop |

The mode-specific `acpx` calls are defined like this:

```bash
acpx --approve-reads --non-interactive-permissions fail <agent> exec '<prompt>'
acpx --approve-all <agent> '<prompt>'
acpx --approve-reads --non-interactive-permissions fail <agent> '<prompt>'
```

What it does:

1. Checks whether `acpx` is installed and offers `npm install -g acpx@latest` if needed.
2. Validates the agent list and the mode flags.
3. In default session mode, runs `acpx <agent> sessions ensure` and falls back to `sessions new` when needed.
4. In `--fix` or `--peer` mode, checks git state first and offers a checkpoint commit if the worktree is dirty.
5. Runs the selected agent or agents.
6. In `--fix` mode, reads the resulting diff and summarizes file changes.
7. In `--peer` mode, loops until the peer agent confirms there are no remaining actionable issues, or the discussion is recorded as an unresolved disagreement.

Important flag rules:

- `--fix`, `--peer`, and `--exec` are mutually exclusive.
- `--fix` can only be used with a single agent.
- `--model` can only appear once.
- If no prompt is provided, the command aborts with a usage message.

Two implementation details are especially useful:

- In non-fix modes, the command appends a read-only guard to the prompt so the target agent does not try to modify files.
- In `--peer` mode, the workflow includes project `CLAUDE.md` conventions in the peer-review framing when a `CLAUDE.md` file exists.

> **Tip:** Use session mode when you expect follow-up prompts in the same repo. Use `--exec` when you want a one-shot answer with no session state.

> **Warning:** `--fix` can modify files and is single-agent only. In a dirty git worktree, the command may offer to create a checkpoint commit before it proceeds.

> **Note:** If `acpx` session management fails with the known session bugs handled by the command, the workflow falls back to one-shot exec mode instead of simply giving up.
