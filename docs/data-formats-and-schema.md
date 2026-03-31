# Data Formats and Schema

This project moves review data through a small set of predictable formats:

- Temporary JSON files under `$TMPDIR/claude` (or `/tmp/claude` if `TMPDIR` is not set)
- Hook payloads passed over stdin/stdout
- Plugin and marketplace metadata files
- A local SQLite database for review history and analytics

If you are debugging a review flow, installing plugins, or querying past review data, these are the formats that matter.

## At A Glance

| Format | Example location | Produced by | Used by |
|---|---|---|---|
| Review snapshot JSON | `$TMPDIR/claude/pr-123-reviews.json` | `reviews fetch` | `reviews post`, `reviews store` |
| Pending review JSON | `$TMPDIR/claude/pr-owner-repo-123-pending-review.json` | `reviews pending-fetch` | `reviews pending-update` |
| Inline comment batch JSON | any file or stdin | user or slash command workflow | `pr post-comment` |
| Review database | `.claude/data/reviews.db` | `reviews store` | `db` commands and auto-skip logic |
| Hook payload JSON | stdin/stdout | Claude Code hooks | hook scripts in `scripts/` |

> **Note:** The command docs often say `/tmp/claude/...`, but the code actually uses `$TMPDIR/claude` when `TMPDIR` is set.

## Temporary JSON Artifacts

### Review snapshot: `pr-<pr_number>-reviews.json`

This is the main handoff file for the review-reply workflow. It is created by `myk-claude-tools reviews fetch` and groups fetched threads by reviewer source.

The file is built in `myk_claude_tools/reviews/fetch.py` like this:

```python
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

A real test fixture from `tests/test_store_reviews_to_db.py` shows the shape that `reviews store` accepts:

```python
data = {
    "metadata": {
        "owner": "org",
        "repo": "repo",
        "pr_number": 1,
    },
    "human": [
        {
            "thread_id": "thread_abc",
            "node_id": "node_xyz",
            "comment_id": 12345,
            "author": "reviewer1",
            "path": "src/main.py",
            "line": 100,
            "body": "Please fix this bug",
            "priority": "HIGH",
            "status": "addressed",
            "reply": "Fixed in commit abc123",
            "skip_reason": None,
            "posted_at": "2024-01-15T10:00:00Z",
            "resolved_at": "2024-01-15T10:05:00Z",
            "type": "outside_diff_comment",
        }
    ],
    "qodo": [],
    "coderabbit": [],
}
```

What you can expect in each thread object:

- GitHub identifiers: `thread_id`, `node_id`, `comment_id`
- Location fields: `path`, `line`
- Review text: `body`, `reply`, `skip_reason`
- Workflow state: `status`, `posted_at`, `resolved_at`
- Classification: `source`, `priority`, and sometimes `type`

When threads are enriched in `process_and_categorize()`, the code adds these defaults:

```python
enriched = {
    **thread,
    "source": source,
    "priority": priority,
    "reply": thread.get("reply"),
    "status": thread.get("status", "pending"),
}
```

That means a freshly fetched thread usually starts with:

- `status: "pending"`
- `reply: null`
- `source: "human"`, `"qodo"`, or `"coderabbit"`
- `priority: "HIGH"`, `"MEDIUM"`, or `"LOW"`

### Special synthesized comment types

Not every review note comes from a normal GitHub review thread. CodeRabbit body-parsed comments are converted into thread-like objects with extra fields.

From `myk_claude_tools/reviews/fetch.py`:

```python
threads.append({
    "thread_id": None,
    "node_id": node_id,
    "comment_id": review_id,
    "author": author,
    "path": path,
    "line": line_int,
    "end_line": end_line_int,
    "body": body,
    "category": comment.get("category", ""),
    "severity": comment.get("severity", ""),
    "replies": [],
    "type": thread_type,
    "review_id": review_id,
    "suggestion_index": idx,
})
```

These special `type` values are currently:

- `outside_diff_comment`
- `nitpick_comment`
- `duplicate_comment`

> **Warning:** These synthesized comments do not behave like normal GitHub review threads. They are handled later as consolidated PR comments rather than replied to inline.

### Status values and resolution rules

The reply/posting step recognizes these statuses in `myk_claude_tools/reviews/post.py`:

```text
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

That source-specific rule is important if you are reading `posted_at` and `resolved_at` later:

- AI review threads are usually both replied to and resolved.
- Human review threads may be replied to without being resolved.

### Atomic writes and cleanup

The review snapshot is written atomically and the temp directory is created with restricted permissions:

```python
tmp_base = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
out_dir = tmp_base / "claude"
out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
```

The file itself is written through a temp file and renamed into place:

```python
fd, tmp_json_path = tempfile.mkstemp(
    prefix=f"pr-{pr_number}-reviews.json.",
    dir=str(out_dir),
)
...
os.replace(tmp_path, json_path)
```

The fetch module also tracks temp files and removes any orphaned `.new` files during cleanup.

> **Tip:** `reviews fetch` prints the full JSON to stdout as well as saving it to disk. `reviews pending-fetch` behaves differently and prints only the saved file path.

### Pending review snapshot: `pr-<owner>-<repo>-<pr_number>-pending-review.json`

This file is created by `myk-claude-tools reviews pending-fetch`. It is used for the “refine an existing draft review” workflow.

The exact output shape comes from `myk_claude_tools/reviews/pending_fetch.py`:

```python
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

Each comment starts with this structure:

```python
comment: dict[str, Any] = {
    "id": c.get("id"),
    "path": c.get("path"),
    "line": c.get("line"),
    "side": c.get("side", "RIGHT"),
    "body": c.get("body", ""),
    "diff_hunk": c.get("diff_hunk", ""),
    "refined_body": None,
    "status": "pending",
}
```

What each field is for:

- `id`: the GitHub review comment ID to patch later
- `path`, `line`, `side`: where the draft comment is attached
- `body`: the original comment text
- `diff_hunk`: nearby diff context
- `refined_body`: where your edited version goes
- `status`: workflow state, typically moved from `pending` to `accepted`

If you later run `pending-update`, the file may also include optional submission metadata. The module documents the expected structure like this:

```text
Expected JSON structure:
  {
    "metadata": {
      "owner": "...",
      "repo": "...",
      "pr_number": 123,
      "review_id": 456,
      "submit_action": "COMMENT",        # optional
      "submit_summary": "Summary text"    # optional
    },
    "comments": [
      {
        "id": 789,
        "path": "src/main.py",
        "line": 42,
        "body": "original comment",
        "refined_body": "refined version",
        "status": "accepted"
      }
    ]
  }
```

Valid `submit_action` values come directly from code:

```python
VALID_SUBMIT_ACTIONS = {"COMMENT", "APPROVE", "REQUEST_CHANGES"}
```

> **Note:** `reviews pending-update` reads this JSON and updates GitHub comments, but it does not rewrite the local JSON file the way `reviews post` does.

### Batched inline comment input

`myk-claude-tools pr post-comment` accepts a much simpler format: a JSON array of `{path, line, body}` objects.

The exact example in `myk_claude_tools/pr/post_comment.py` is:

```json
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
```

Severity markers are parsed from the first line of `body`:

```text
Severity Markers:
    - ### [CRITICAL] Title - For critical security/functionality issues
    - ### [WARNING] Title  - For important but non-critical issues
    - ### [SUGGESTION] Title - For code improvements and suggestions
```

One practical detail from the loader: it can recover from prepended shell or hook output by scanning for the first line that starts with `[` and attempting JSON parsing from there.

### Other JSON you may see: `pr diff` output

`myk-claude-tools pr diff` prints a JSON object to stdout rather than saving a fixed temp file. This is often used as structured input for PR review workflows.

From `myk_claude_tools/pr/diff.py`:

```python
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

Each `files` entry includes:

```python
{
    "path": f["filename"],
    "status": f["status"],
    "additions": f["additions"],
    "deletions": f["deletions"],
    "patch": f.get("patch", ""),
}
```

## Hook Payload Expectations

Hook registration lives in `settings.json`. The repo uses four hook event types:

```json
"hooks": {
  "Notification": [...],
  "PreToolUse": [...],
  "UserPromptSubmit": [...],
  "SessionStart": [...]
}
```

### `PreToolUse`: stdin JSON in, optional deny JSON out

Both `scripts/rule-enforcer.py` and `scripts/git-protection.py` read JSON from stdin and look for `tool_name` plus `tool_input`.

From `rule-enforcer.py`:

```python
input_data = json.loads(sys.stdin.read())
tool_name = input_data.get("tool_name", "")
tool_input = input_data.get("tool_input", {})
```

The test suite shows the expected input shape clearly:

```python
input_data = {
    "tool_name": "Bash",
    "tool_input": {"command": "python script.py"},
}
```

When a command is denied, the scripts return a JSON envelope under `hookSpecificOutput`. From `rule-enforcer.py`:

```python
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
```

In practice:

- `tool_name` is usually `"Bash"` for these hooks
- `tool_input.command` is the important field for command hooks
- allow decisions are normally represented by exiting successfully without printing a deny payload

> **Warning:** The two command hooks have different failure behavior. `rule-enforcer.py` fails open on unexpected errors, while `git-protection.py` fails closed and returns a deny payload if it crashes.

### The prompt-based destructive-command gate

There is also a prompt-style `PreToolUse` hook in `settings.json`. It asks an LLM to classify destructive shell commands and requires a very small JSON response.

The configured prompt ends with this exact contract:

```text
Respond with JSON: {"decision": "approve" or "block" or "ask", "reason": "brief explanation"}
```

If you are building tooling around this repo, those are the only three supported decisions for that gate:

- `approve`
- `block`
- `ask`

### `UserPromptSubmit`: stdin ignored, context JSON returned

`scripts/rule-injector.py` reads stdin only because the hook protocol expects it, then returns structured JSON with additional prompt context.

From the script:

```python
output = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": rule_reminder}}
```

That means the payload contract is simple:

- input: whatever Claude Code provides on stdin
- output: JSON with `hookSpecificOutput.hookEventName` and `additionalContext`

### `Notification`: JSON with a top-level `message`

`scripts/my-notifier.sh` expects JSON on stdin and reads one field:

```bash
if ! notification_message=$(echo "$input_json" | jq -r '.message' 2>&1); then
    echo "Error: Failed to parse JSON - $notification_message" >&2
    exit 1
fi
```

Practical rules for this hook:

- `message` must be present
- `message` must not be empty or `null`
- the script does not read nested fields

A minimal valid payload looks like:

```json
{
  "message": "Review completed"
}
```

### `SessionStart`: plain text, not JSON

`scripts/session-start-check.sh` is the outlier. It does not parse JSON input, and when it finds missing tools or plugins it prints a plain-text report.

The report starts like this:

```text
MISSING_TOOLS_REPORT:

[AI INSTRUCTION - YOU MUST FOLLOW THIS]
Some tools required by this configuration are missing.
```

It then prints sections for critical and optional tools, install hints, and explicit instructions about asking the user for help installing them.

> **Warning:** `SessionStart` output is plain text, not JSON. If you are consuming hook output programmatically, do not assume every hook in this repo uses the same encoding.

## Plugin And Marketplace Metadata

### Marketplace manifest: `.claude-plugin/marketplace.json`

The marketplace index describes which plugins are published from this repository.

A real entry looks like this:

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

What the fields mean:

- `name`: marketplace namespace
- `owner.name`: display owner for the marketplace
- `plugins[]`: published plugin entries
- `source`: repo-relative plugin directory
- `version`: marketplace-published version for that plugin entry

### Per-plugin manifest: `plugins/<plugin>/.claude-plugin/plugin.json`

Each plugin also ships its own manifest. For example, `plugins/myk-github/.claude-plugin/plugin.json`:

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

The manifest format used across this repo is intentionally small:

- `name`
- `version`
- `description`
- `author.name`
- `repository`
- `license`
- `keywords`

### Command metadata in `plugins/*/commands/*.md`

Each slash command is a Markdown file with YAML frontmatter. A real example from `plugins/myk-github/commands/pr-review.md`:

```yaml
---
description: Review a GitHub PR and post inline comments on selected findings
argument-hint: [PR_NUMBER|PR_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task
---
```

Those frontmatter keys are the command schema used in this repo:

- `description`: what the command does
- `argument-hint`: how the command should be invoked
- `allowed-tools`: which Claude Code tools the command is allowed to use

You can see the same pattern repeated across command files such as:

- `plugins/myk-review/commands/local.md`
- `plugins/myk-review/commands/query-db.md`
- `plugins/myk-github/commands/release.md`
- `plugins/myk-acpx/commands/prompt.md`

### Runtime plugin metadata in `settings.json`

The checked-in `settings.json` also records which plugins are enabled and which extra marketplaces are known.

From the file:

```json
"enabledPlugins": {
  "myk-review@myk-org": true,
  "myk-github@myk-org": true,
  "myk-acpx@myk-org": true
},
"extraKnownMarketplaces": {
  "cli-anything": {
    "source": {
      "source": "github",
      "repo": "HKUDS/CLI-Anything"
    }
  },
  "worktrunk": {
    "source": {
      "source": "github",
      "repo": "max-sixty/worktrunk"
    }
  }
}
```

This is runtime configuration rather than plugin packaging metadata, but it is still part of the repo’s plugin schema story.

## SQLite Review Database Schema

### Location and lifecycle

The review database lives at:

```text
<git-root>/.claude/data/reviews.db
```

The storage path is set in `myk_claude_tools/reviews/store.py`:

```python
db_path = project_root / ".claude" / "data" / "reviews.db"
```

The storage workflow is:

1. Read a completed review JSON file
2. Create the database directory if needed
3. Insert one row into `reviews`
4. Insert one row per comment into `comments`
5. Commit the transaction
6. Delete the JSON file on success

The delete step is explicit:

```python
json_path.unlink()
```

> **Warning:** `reviews store` is intentionally destructive for the temp artifact. After a successful import, the JSON file is removed.

### Table definitions

The schema is defined directly in Python as SQL:

```sql
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_number INTEGER NOT NULL,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL REFERENCES reviews(id),
    source TEXT NOT NULL,
    thread_id TEXT,
    node_id TEXT,
    comment_id INTEGER,
    author TEXT,
    path TEXT,
    line INTEGER,
    body TEXT,
    priority TEXT,
    status TEXT,
    reply TEXT,
    skip_reason TEXT,
    posted_at TEXT,
    resolved_at TEXT,
    type TEXT DEFAULT NULL
);
```

Indexes are also created for the most common lookups:

```sql
CREATE INDEX IF NOT EXISTS idx_comments_review_id ON comments(review_id);
CREATE INDEX IF NOT EXISTS idx_comments_source ON comments(source);
CREATE INDEX IF NOT EXISTS idx_comments_status ON comments(status);
CREATE INDEX IF NOT EXISTS idx_reviews_pr ON reviews(owner, repo, pr_number);
CREATE INDEX IF NOT EXISTS idx_reviews_commit ON reviews(commit_sha);
```

### What the columns mean

For end users, the important columns are:

- `reviews.id`: one stored review run
- `reviews.pr_number`, `owner`, `repo`: which PR the review belongs to
- `reviews.commit_sha`: the commit SHA captured at store time
- `reviews.created_at`: when that database row was written

And in `comments`:

- `review_id`: foreign key back to `reviews.id`
- `source`: `human`, `qodo`, or `coderabbit`
- `thread_id`, `node_id`, `comment_id`: GitHub-side identifiers
- `path`, `line`: where the comment points
- `body`: the original review text
- `priority`: `HIGH`, `MEDIUM`, or `LOW`
- `status`: `pending`, `addressed`, `not_addressed`, `skipped`, or `failed`
- `reply`: the reply text posted back to GitHub
- `skip_reason`: why something was skipped
- `posted_at`, `resolved_at`: workflow timestamps
- `type`: special synthesized comment type such as `outside_diff_comment`

A real test confirms that all of these fields are stored as expected:

```python
assert row[0] == "thread_abc"
assert row[1] == "node_xyz"
assert row[2] == 12345
assert row[3] == "reviewer1"
assert row[4] == "src/main.py"
assert row[5] == 100
assert row[6] == "Please fix this bug"
assert row[7] == "HIGH"
assert row[8] == "addressed"
assert row[9] == "Fixed in commit abc123"
assert row[10] == "2024-01-15T10:00:00Z"
assert row[11] == "2024-01-15T10:05:00Z"
assert row[12] == "outside_diff_comment"
```

### Append-only behavior

Stored reviews are append-only. Re-running storage for the same PR creates a new `reviews` row instead of overwriting the old one.

That behavior is tested explicitly:

```python
review_id1 = store_reviews.insert_review(conn, "owner", "repo", 123, "abc1234567")
review_id2 = store_reviews.insert_review(conn, "owner", "repo", 123, "def7890123")

assert review_id1 != review_id2
```

This means the database preserves history across multiple review passes on the same PR.

### Schema migration: the `type` column

Older databases may not have `comments.type`. The code upgrades them automatically on startup.

From `create_tables()`:

```python
cursor = conn.execute("PRAGMA table_info(comments)")
columns = {row[1] for row in cursor.fetchall()}
if "type" not in columns:
    conn.execute("ALTER TABLE comments ADD COLUMN type TEXT DEFAULT NULL")
```

From `ReviewDB._migrate_schema()`:

```python
cursor = conn.execute("PRAGMA table_info(comments)")
columns = {row[1] for row in cursor.fetchall()}
if "type" not in columns:
    conn.execute("ALTER TABLE comments ADD COLUMN type TEXT DEFAULT NULL")
    conn.commit()
```

> **Note:** There is no separate migration framework in this repo for the review database. The migration is code-driven and safe to run repeatedly.

### Read-only query rules

The analytics/query layer is intentionally read-only. `ReviewDB.query()` only accepts `SELECT` and `WITH` statements.

The key safety check is:

```python
if not sql_upper.startswith(("SELECT", "WITH")):
    raise ValueError("Only SELECT/CTE queries are allowed for safety")
```

It also rejects multiple statements and blocks modifying keywords such as:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `CREATE`
- `ATTACH`
- `DETACH`
- `PRAGMA`

This is why `myk-claude-tools db query` is safe for analytics but not for schema changes.

### Dismissed-comment lookups and auto-skip semantics

The database is not only for reporting. It also powers auto-skip behavior during `reviews fetch`.

`get_dismissed_comments()` deliberately includes:

- all `not_addressed` comments
- all `skipped` comments
- only some `addressed` comments, when `type` is a special synthesized type

The SQL condition is:

```sql
AND (
    c.status IN ('not_addressed', 'skipped')
    OR (c.status = 'addressed'
        AND c.type IN ('outside_diff_comment', 'nitpick_comment', 'duplicate_comment'))
)
```

That rule exists because those special comment types do not map cleanly to resolvable GitHub review threads. The database becomes the only reliable place to remember that they were already handled.

### `db find-similar` stdin format

`myk-claude-tools db find-similar` reads JSON from stdin and expects a single object with `path` and `body`.

The CLI implementation does this:

```python
input_data = json.load(sys.stdin)
path = input_data.get("path", "")
body = input_data.get("body", "")
```

The test suite uses this exact input:

```python
input_json = json.dumps({"path": "path/to/file.py", "body": "Add skip option"})
```

> **Tip:** Pass a single JSON object to `db find-similar`, not an array.

## Practical Rules Of Thumb

- Use `reviews fetch` when you need a full review snapshot grouped into `human`, `qodo`, and `coderabbit`.
- Use `reviews pending-fetch` when you already have a pending GitHub review and want to refine its draft comments.
- Use `pr post-comment` when you only need to post a simple batch of inline comments.
- Treat `reviews.db` as append-only history, not as a scratch database.
- Expect JSON for `PreToolUse`, `UserPromptSubmit`, and `Notification`, but plain text for `SessionStart`.
- If a comment has `type: outside_diff_comment`, `nitpick_comment`, or `duplicate_comment`, expect different posting and storage behavior than a normal inline thread.
