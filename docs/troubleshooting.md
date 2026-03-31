# Troubleshooting

Most problems in this repository come from one of six places: hook policy, missing prerequisites, GitHub CLI auth, `acpx` session state, review-state files, or stale task/temp data. Start with the quick checks below, then jump to the section that matches what you are seeing.

## Start Here

Run the same basic checks the project itself expects:

```bash
uv --version
myk-claude-tools --version
gh api user --jq .login
acpx --version
```

If one of those fails, fix that first.

- If `uv --version` fails, Python-backed hooks and CLI flows will not work.
- If `myk-claude-tools --version` fails, the GitHub review and release commands cannot run.
- If `gh api user --jq .login` fails, PR, review, and release commands will usually fail too.
- If `acpx --version` fails, `/myk-acpx:prompt` cannot start.

> **Tip:** `gh api user --jq .login` is the quickest way to tell whether a "GitHub problem" is really an auth problem.

## Hook and startup failures

This repo wires its behavior through `settings.json`. The important hook events are `PreToolUse`, `UserPromptSubmit`, and `SessionStart`:

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
  },
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "uv run ~/.claude/scripts/git-protection.py"
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

If hook behavior looks inconsistent after you add or change an allowed script, check both permission lists. The repo keeps the same entries in `permissions.allow` and `allowedTools`:

```json
"_scriptsNote": "Script entries must be duplicated in both permissions.allow and allowedTools arrays. When adding new scripts, update BOTH locations."
```

If you update only one list, Claude Code may still deny the tool use even though the hook script exists.

### "Direct python/pip commands are forbidden"

This is `scripts/rule-enforcer.py` doing exactly what it was written to do:

```python
# Block direct python/pip
forbidden = ("python ", "python3 ", "pip ", "pip3 ")
return cmd.startswith(forbidden)

def is_forbidden_precommit_command(command: str) -> bool:
    """Check if command uses pre-commit directly instead of prek."""
    cmd = command.strip().lower()

    # Block direct pre-commit commands
    return cmd.startswith("pre-commit ")
```

The same hook also tells you what to use instead:

```python
"You attempted to run python/pip directly. Instead:\n"
"1. Delegate Python tasks to the python-expert agent\n"
"2. Use 'uv run script.py' to run Python scripts\n"
"3. Use 'uvx package-name' to run package CLIs\n"

"You attempted to run pre-commit directly. Instead:\n"
"1. Use the 'prek' command which wraps pre-commit\n"
"2. Example: prek run --all-files\n"
```

Practical replacements that are already covered by tests in this repo:

- Use `uv run script.py` instead of `python script.py`
- Use `uvx ruff check .` instead of installing a tool ad hoc with `pip`
- Use `prek run --all-files` instead of `pre-commit run --all-files`

### "Session start says tools are missing"

`scripts/session-start-check.sh` does a non-blocking dependency sweep. It treats `uv` and the three review plugins as critical, and several other tools as optional:

```bash
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

# CRITICAL: Review plugins - Required for mandatory code review loop
critical_marketplace_plugins=(
  pr-review-toolkit
  superpowers
  feature-dev
)
```

If you see a `MISSING_TOOLS_REPORT`, prioritize fixes in this order:

- `uv`
- Missing review plugins: `pr-review-toolkit`, `superpowers`, `feature-dev`
- `gh` if you use GitHub-backed commands
- `prek` if you run pre-commit checks locally
- `mcpl`, `jq`, `gawk`, and optional marketplace plugins as needed

The script also prints the exact plugin install pattern it expects, including:

```text
/plugin marketplace add claude-plugins-official
/plugin install pr-review-toolkit@claude-plugins-official
/plugin install superpowers@claude-plugins-official
/plugin install feature-dev@claude-plugins-official
```

### "The security gate blocked my Bash command"

`settings.json` includes a second `PreToolUse` prompt that inspects destructive Bash. It can `approve`, `block`, or `ask`. That is expected for commands involving things like system directories, raw disk writes, filesystem formatting, or risky `sudo` deletes.

If you get asked for confirmation on a command that feels safe, the command probably looks risky to the prompt because of chained operators, delete targets, or elevated permissions.

> **Warning:** This prompt is intentionally conservative. If you are doing something destructive on purpose, expect it to stop and ask.

## Git commits and pushes are blocked

`scripts/git-protection.py` intercepts `git commit` and `git push` and blocks a few categories of mistakes:

- Committing directly on `main` or `master`
- Pushing directly on `main` or `master`
- Committing on a branch whose PR is already merged
- Pushing on a branch whose PR is already merged
- Committing in detached `HEAD`

It also checks GitHub merge state when the remote is on GitHub. That lookup uses `gh`, so an auth or API failure can surface as a blocked commit or push.

The important behavior to know is that this hook fails closed. If the GitHub lookup errors, the command is denied.

> **Warning:** A broken `gh` session can look like a Git protection problem, even when your branch is otherwise fine.

Two details that surprise people:

- Commits in detached `HEAD` are blocked, because the script warns that those commits can become orphaned.
- Pushes from detached `HEAD` are not automatically blocked, because the code treats an explicit detached push as potentially intentional.

If you see a Git protection message that mentions a hook error, fix the `gh` problem first. The hook is not asking you to bypass it; it is telling you the merge-status check did not complete safely.

## GitHub CLI auth and API problems

The GitHub-backed flows in `myk_claude_tools` use both REST and GraphQL through `gh`. For example, `reviews pending-fetch` checks the authenticated user like this:

```python
result = subprocess.run(
    ["gh", "api", "user", "--jq", ".login"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    timeout=30,
)
...
if result.returncode != 0:
    stderr = result.stderr or ""
    print_stderr(f"Error: Could not get authenticated user: {stderr.strip()}")
    return None
```

If `gh` is not installed, several commands fail fast with messages like:

- `Error: GitHub CLI (gh) not found. Install gh to fetch PR diff.`
- `Error: GitHub CLI (gh) not found. Install gh to fetch CLAUDE.md.`

If `gh` is installed but not authenticated, you will usually see one of these patterns instead:

- `Error: Could not get authenticated user: ...`
- `Error: Could not determine authenticated user`
- `Warning: GraphQL query failed: ...`
- `Warning: API call to ... failed: ...`

The quickest way to narrow this down is:

1. Run `gh api user --jq .login`
2. If that fails, fix GitHub CLI auth before retrying anything else
3. Retry the original command only after the user lookup succeeds

### "No pending review found"

`myk_claude_tools/reviews/pending_fetch.py` is used by `/myk-github:refine-review`. It expects you to already have a pending review on GitHub:

- `Error: No pending review found for user '<username>' on PR #<number>`
- `Start a review on GitHub first by adding comments without submitting.`

That is not a bug. It means there is nothing pending for the tool to refine yet.

### "Could not infer PR from branch"

`reviews fetch` can auto-detect the PR from the current branch, but it refuses to guess in detached `HEAD`:

- `Error: Detached HEAD; cannot infer PR from branch. Check out a branch with an open PR.`

If you are on a detached commit, check out the branch that owns the PR or pass an explicit PR URL where the command supports it.

## acpx session failures

`/myk-acpx:prompt` tries to use persistent sessions by default. The workflow in `plugins/myk-acpx/commands/prompt.md` is:

```bash
acpx <agent> sessions ensure
acpx <agent> sessions new
```

If both fail, the command documentation is explicit about what to do next:

```text
If the error contains "Invalid params" or "session" and "not found", display:

"acpx session management failed for `<agent>`. This is a known issue — see:
- <https://github.com/openclaw/acpx/issues/152>
- <https://github.com/openclaw/acpx/issues/161>

Falling back to one-shot mode (`--exec`)."
```

If you hit session problems:

- Use `--exec` to bypass session persistence for that run
- Confirm `acpx --version` works
- Confirm the underlying agent CLI is installed separately
- Retry session mode later if you specifically need follow-up prompts in the same agent session

`--fix`, `--peer`, and `--exec` are also mutually exclusive in several combinations. If the command rejects your flags, treat that as input validation, not a runtime failure.

> **Tip:** If you only need one answer and do not need conversation state, `--exec` is the most reliable mode.

## CodeRabbit problems

### Rate limit handling does not start or resume

The CodeRabbit helper looks for a specific summary comment and parses the cooldown from its body. The core behavior is in `myk_claude_tools/coderabbit/rate_limit.py`:

```python
if comment_id is None or body is None:
    print(f"Error: {error}")
    return 1

if _RATE_LIMITED_MARKER not in body:
    print(json.dumps({"rate_limited": False}))
    return 0

wait_seconds = _parse_wait_seconds(body)
if wait_seconds is None:
    print("Error: Could not parse wait time from rate limit message.")
    snippet = "\n".join(body.split("\n")[:10])
    print(f"Comment snippet:\n{snippet}")
    return 1

print(json.dumps({"rate_limited": True, "wait_seconds": wait_seconds, "comment_id": comment_id}))
```

Common meanings:

- `No CodeRabbit summary comment found on this PR` means the handler could not find the comment it depends on
- `Could not parse wait time from rate limit message` means the comment exists, but its text no longer matches the expected format
- A JSON response with `rate_limited: true` means the helper successfully parsed the cooldown and can trigger later

The trigger flow also treats a replaced summary comment as success after two consecutive misses:

```python
elif status == "no_comment":
    none_streak += 1
    if none_streak >= 2:
        print("Review started (comment replaced).")
        return 0
    print("Warning: Could not find comment. Retrying...")
```

That is why the tool can say `Review started (comment replaced).` even though it no longer sees the original summary comment.

### Body comments seem to be missing

CodeRabbit findings are not always inline threads. `myk_claude_tools/reviews/coderabbit_parser.py` parses three body-embedded sections:

```python
_OUTSIDE_SECTION_START_RE = re.compile(
    r"<summary>\s*(?:\S+\s+)*?Outside diff range comments?\s*(?:\(\d+\))?\s*</summary>\s*<blockquote>",
)

_NITPICK_SECTION_START_RE = re.compile(
    r"<summary>\s*(?:\S+\s+)*?Nitpick comments?\s*(?:\(\d+\))?\s*</summary>\s*<blockquote>",
)

_DUPLICATE_SECTION_START_RE = re.compile(
    r"<summary>\s*(?:\S+\s+)*?Duplicate comments?\s*(?:\(\d+\))?\s*</summary>\s*<blockquote>",
)
```

It also strips AI-only helper text before building the final comment body:

```python
_AI_PROMPT_RE = re.compile(
    r"<details>\s*\n?\s*<summary>\s*\S*\s*Prompt for AI Agents\s*</summary>.*?</details>",
    re.DOTALL,
)
```

The tests in `tests/test_coderabbit_parser.py` cover the edge cases that matter in practice:

- single-line references like `` `42` ``
- file paths with spaces
- missing sections
- truncated HTML with unclosed tags, which intentionally returns an empty parse
- trailing `Prompt for AI Agents` blocks, which are intentionally removed
- mixed bodies that contain outside-diff, nitpick, and duplicate sections together

If you expect a body-embedded comment and do not see it after fetch, compare the current CodeRabbit comment HTML to those parser expectations first.

### Outside-diff comments are grouped into PR comments

Outside-diff, nitpick, and duplicate items do not have normal GitHub review threads to reply to. `myk_claude_tools/reviews/post.py` groups them into one or more PR-level comments per reviewer:

```python
max_len = 55000  # Leave margin below GitHub's ~65KB limit
header_template = "@{reviewer}\n\nThe following review comments were reviewed and a decision was made:\n\n"
```

That means you should expect:

- a PR comment, not an inline thread reply
- one comment per reviewer, sometimes split into parts when large
- body-comment items to be tracked in the review database, even though there was no inline thread to resolve

> **Note:** If a CodeRabbit item was outside the diff, it is normal for it to show up as a consolidated PR comment instead of an inline thread resolution.

### "Why did my reply post but the human thread stay open?"

That is deliberate. In `myk_claude_tools/reviews/post.py`, human review threads are only resolved when the status is `addressed`. For human `skipped` or `not_addressed`, the tool replies but keeps the thread open. On rerun, you may see the exact text `reply already posted at ... (not resolving by policy)`.

AI threads behave differently. Qodo and CodeRabbit replies are resolved after replying for the handled statuses.

## Review JSON, temp files, and database state

Review commands intentionally keep intermediate state on disk so they can retry safely.

`myk_claude_tools/reviews/fetch.py` writes review JSON under `$TMPDIR/claude` and sets restrictive permissions:

```python
tmp_base = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
out_dir = tmp_base / "claude"
out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
try:
    out_dir.chmod(0o700)
except OSError as e:
    print_stderr(f"Warning: unable to set permissions on {out_dir}: {e}")

json_path = out_dir / f"pr-{pr_number}-reviews.json"
```

That aligns with the repo rule in `rules/40-critical-rules.md`: temp files belong in `/tmp/claude/`, not in the project tree.

`reviews post` then updates the JSON with `posted_at` and `resolved_at`. This is what makes retries safe:

- If a reply posted but resolution failed, rerunning can do a resolve-only retry
- If both `posted_at` and `resolved_at` are already present, reruns skip that entry
- If posting fails, the tool prints `ACTION REQUIRED` and a retry command: `myk-claude-tools reviews post <json_path>`

After the whole flow is done, `reviews store` imports the finished JSON into SQLite at `<project-root>/.claude/data/reviews.db` and deletes the JSON on success.

That means two things are normal:

- The JSON file disappearing after `myk-claude-tools reviews store`
- The database directory being created with `0700`

It also means you should not delete the JSON too early if you still need `reviews post` to retry.

> **Note:** Review tools honor `TMPDIR`. On systems with a custom temp directory, your files may be under `<TMPDIR>/claude` instead of `/tmp/claude`.

### Why a dismissed comment can disappear automatically later

`reviews fetch` can preload dismissed comments from the review database and mark matching items as auto-skipped. The exact display string comes from `fetch.py`:

- `Auto-skipped (skipped): ...`
- `Auto-skipped (addressed): ...`

The database logic is intentionally conservative:

- `not_addressed` and `skipped` comments are always treated as dismissed
- `addressed` comments are only reused for body-comment types such as `outside_diff_comment`, `nitpick_comment`, and `duplicate_comment`

Regular inline thread comments rely on GitHub's own resolved-thread state instead of body-similarity matching. If an inline thread seems to "come back" in a later PR, that is usually why.

## Stale task state

Task state persists on disk at:

`~/.claude/tasks/<session-uuid>/`

The repo's task-system rule is explicit that stale tasks cause confusing progress indicators, clutter, and blocked-looking workflows. The documented cleanup pattern is:

```text
TaskList
TaskUpdate: taskId="5", status="completed"
TaskList
```

If your task panel looks wrong after a multi-phase workflow, do a cleanup pass:

- Run `TaskList`
- Look for `pending` or `in_progress` items that should be closed
- Update them to `completed`
- Run `TaskList` again to confirm the state is clean

## Local validation and "does this repo expect me to run that another way?"

The supported local test command comes from `tox.toml`:

```toml
[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

That matches the Python tooling defined in `pyproject.toml` and the hook stack in `.pre-commit-config.yaml`, which includes `ruff`, `ruff-format`, `flake8`, `mypy`, `markdownlint`, `gitleaks`, `detect-secrets`, and other hygiene checks.

A short example from `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: v0.14.14
  hooks:
    - id: ruff
    - id: ruff-format
```

Two practical takeaways:

- Use `uv run --group tests pytest tests` for the test suite
- Use `prek`, not raw `pre-commit`, because the hook policy blocks direct `pre-commit ...`

The CodeRabbit config also enables several analyzers, including `ruff`, `pylint`, `eslint`, `shellcheck`, `yamllint`, `gitleaks`, `semgrep`, `actionlint`, and `hadolint`. If review feedback seems unfamiliar, it may be mirroring one of those configured tools.

## Quick symptom index

| Symptom | Most likely cause | What to do |
| --- | --- | --- |
| `Direct python/pip commands are forbidden` | `rule-enforcer.py` | Switch to `uv run`, `uvx`, or `prek` |
| `Direct pre-commit commands are forbidden` | `rule-enforcer.py` | Run `prek run --all-files` instead |
| Missing tools report on startup | `session-start-check.sh` | Install `uv` first, then required review plugins, then optional tools you actually use |
| Commit or push blocked unexpectedly | `git-protection.py` | Check branch state, then verify `gh api user --jq .login` works |
| `Could not determine authenticated user` | `gh` auth or API problem | Fix GitHub CLI auth before rerunning review commands |
| `No pending review found` | No draft review exists yet | Start a review on GitHub, add comments, leave it pending, then rerun |
| `Detached HEAD; cannot infer PR from branch` | Branch auto-detection cannot work | Check out the PR branch or use an explicit PR URL if supported |
| `acpx` session errors mentioning invalid params or session not found | Known upstream session issue | Use `--exec` and retry later if you need persistent sessions |
| CodeRabbit rate-limit handler cannot continue | Missing summary comment or changed cooldown text | Check for `No CodeRabbit summary comment found` or `Could not parse wait time...` |
| CodeRabbit outside-diff comment did not resolve inline | It was a body comment, not a thread | Look for the consolidated PR-level comment instead |
| Review JSON disappeared after storage | Normal `reviews store` behavior | Check `.claude/data/reviews.db` instead |
| Task UI shows stale progress | Old tasks still marked open | Run `TaskList`, then complete stale tasks |
