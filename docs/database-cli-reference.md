# Database CLI Reference

The database CLI lets you inspect the local review history stored in the review database. Use it to answer practical questions like:

- Which review sources produce the most actionable comments?
- Which skipped or not-addressed comments keep repeating?
- Has this comment already been dismissed before?
- What does the raw review data look like?

You can run these queries in two ways:

```bash
myk-claude-tools db stats --by-source
/myk-review:query-db stats --by-source
```

All command examples on this page come from the project’s actual CLI definitions, plugin command, or tests.

## At a glance

| Command | Best for |
| --- | --- |
| `stats` | Addressed-rate reports by source or reviewer |
| `patterns` | Recurring skipped or not-addressed comment patterns |
| `dismissed` | Repo-specific dismissed history and reasons |
| `query` | One-off read-only SQL queries |
| `find-similar` | Comparing a new comment to previously dismissed comments |

## Before you start

If you want to run the CLI directly, install the `myk-claude-tools` console script:

```bash
uv tool install myk-claude-tools
myk-claude-tools --version
```

> **Note:** By default, the CLI looks for the database at `<git-root>/.claude/data/reviews.db`, where `<git-root>` is the Git repository root of your current working directory.

> **Tip:** Every `db` subcommand accepts `--db-path`, so you can point at a different database file when needed.

These analytics commands query an existing database. Review data is stored separately after a completed review flow is written to disk.

A minimal stored review payload looks like this:

```json
{
  "metadata": {
    "owner": "test-owner",
    "repo": "test-repo",
    "pr_number": 123
  },
  "human": [{"body": "human comment"}],
  "qodo": [{"body": "qodo comment"}],
  "coderabbit": [{"body": "coderabbit comment"}]
}
```

The database is append-only: each stored review run creates a new row in `reviews`, then inserts its comments into `comments`.

> **Note:** If the same PR is stored more than once, the database keeps multiple `reviews` rows for that PR. That is useful for history, but it also means custom queries may need `DISTINCT`, grouping, or a “latest review” filter.

## Common options

| Option | Available on | What it does |
| --- | --- | --- |
| `--json` | All `db` subcommands | Returns JSON instead of a formatted table |
| `--db-path` | All `db` subcommands | Uses a specific database file |
| `--owner`, `--repo` | `dismissed`, `find-similar` | Scopes the command to one repository |
| `--min` | `patterns` | Sets the minimum number of repeated matches to report |
| `--threshold` | `find-similar` | Sets the minimum similarity score from `0.0` to `1.0` |

> **Tip:** Table output truncates long values for readability. Use `--json` if you need the full comment body or want to pipe the result into another tool.

## Command reference

### `stats`

Use `stats` to measure how often comments are addressed, skipped, or left unaddressed.

```bash
myk-claude-tools db stats
myk-claude-tools db stats --by-reviewer
myk-claude-tools db stats --by-source --json
```

What it does:

- `--by-source` groups by comment source such as `human`, `qodo`, and `coderabbit`
- `--by-reviewer` groups by the individual `author`
- Source-based output includes an `addressed_rate` percentage

> **Note:** If you do not pass either `--by-source` or `--by-reviewer`, `stats` defaults to source-based output.

> **Warning:** `--by-source` and `--by-reviewer` are mutually exclusive. Passing both returns an error.

### `patterns`

Use `patterns` to find repeated comment clusters that may be worth turning into reviewer guidance or skip rules.

```bash
myk-claude-tools db patterns
myk-claude-tools db patterns --min 3
myk-claude-tools db patterns --json
```

What it returns:

- `path`: the file path where the pattern appears
- `occurrences`: how many similar comments were found
- `reason`: the most common `reply` or `skip_reason` in that cluster
- `body_sample`: the first comment body in the cluster

How matching works:

- The command only looks at comments with status `not_addressed` or `skipped`
- Comments are grouped by exact `path`
- Within a path, comments are clustered when their body similarity is at least `0.6`

> **Note:** `patterns` works across the whole database. It is not scoped to one `owner` or `repo`.

### `dismissed`

Use `dismissed` to list comments for a specific repository that were skipped, not addressed, or otherwise recorded as reusable dismissals.

```bash
myk-claude-tools db dismissed --owner myk-org --repo claude-code-config
myk-claude-tools db dismissed --owner myk-org --repo claude-code-config --json
```

In JSON mode, the command returns fields such as:

- `path`
- `line`
- `body`
- `status`
- `reply`
- `skip_reason`
- `author`
- `type`
- `comment_id`

In table mode, the CLI shows a smaller set of columns:

- `path`
- `line`
- `status`
- `reply`
- `author`

> **Note:** You may see some rows with status `addressed`. That is intentional for `outside_diff_comment`, `nitpick_comment`, and `duplicate_comment`, because those body-comment types do not rely on a normal GitHub review thread for later skipping.

### `query`

Use `query` when you want raw SQL access to the database.

```bash
myk-claude-tools db query "SELECT * FROM comments WHERE status = 'skipped'"
myk-claude-tools db query "SELECT status, COUNT(*) as cnt FROM comments GROUP BY status"
myk-claude-tools db query "SELECT * FROM comments LIMIT 5" --json
myk-claude-tools db query "SELECT COUNT(*) as count FROM comments" --json
```

A practical example from the plugin command is:

```bash
myk-claude-tools db query "SELECT * FROM comments WHERE status = 'skipped' ORDER BY id DESC LIMIT 10"
```

This command is useful when you want exact control over:

- filtering by status, source, author, or path
- counting rows
- grouping and sorting
- inspecting raw rows behind `stats`, `patterns`, or `dismissed`

> **Warning:** The query interface is read-only. Only `SELECT` and `WITH` statements are allowed. Multiple statements are blocked, and mutating keywords such as `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `DETACH`, and `PRAGMA` are rejected.

### `find-similar`

Use `find-similar` to compare a new comment against previously dismissed comments in the same repository and file path.

```bash
echo '{"path": "foo.py", "body": "Add error handling..."}' | \
  myk-claude-tools db find-similar --owner myk-org --repo claude-code-config --json
```

The CLI reads JSON from standard input. The input must be a single JSON object with both `path` and `body`.

Actual input shape used by the test suite:

```json
{"path": "path/to/file.py", "body": "Add skip option"}
```

How matching works:

- Repository must match `--owner` and `--repo`
- File path must match exactly
- Only comments with status `not_addressed` or `skipped` are considered
- Similarity is based on case-insensitive word overlap, not semantic meaning
- The default threshold is `0.6`
- Valid threshold values are `0.0` through `1.0`

If a match is found, JSON output includes the matched row plus a `similarity` score. In text mode, the CLI prints:

- the similarity score
- the matched `path:line`
- the matched status
- the matched reason
- the first 100 characters of the original body

> **Warning:** Pass a single JSON object, not a JSON array. The CLI reads `path` and `body` directly from the top-level input object.

## Slash command wrapper

Inside Claude Code, the `myk-review` plugin exposes the same database queries through `/myk-review:query-db`.

```bash
/myk-review:query-db stats --by-source
/myk-review:query-db stats --by-reviewer
/myk-review:query-db patterns --min 2
/myk-review:query-db dismissed --owner X --repo Y
/myk-review:query-db query "SELECT * FROM comments WHERE status='skipped' LIMIT 10"
/myk-review:query-db find-similar < comments.json
```

Use the slash command when you are already working inside Claude Code and want the same analytics without leaving the chat.

## Database schema

The review database has two main tables:

- `reviews`: one row per stored review run
- `comments`: one row per stored comment from `human`, `qodo`, or `coderabbit`

Actual schema snippet:

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

Relevant indexes from the same schema:

```sql
CREATE INDEX IF NOT EXISTS idx_comments_review_id ON comments(review_id);
CREATE INDEX IF NOT EXISTS idx_comments_source ON comments(source);
CREATE INDEX IF NOT EXISTS idx_comments_status ON comments(status);
CREATE INDEX IF NOT EXISTS idx_reviews_pr ON reviews(owner, repo, pr_number);
CREATE INDEX IF NOT EXISTS idx_reviews_commit ON reviews(commit_sha);
```

The most useful fields for day-to-day analytics are:

- `source`: where the comment came from
- `author`: who wrote it
- `path` and `line`: where it applies
- `status`: `pending`, `addressed`, `skipped`, or `not_addressed`
- `reply` and `skip_reason`: why it was resolved, skipped, or not addressed
- `type`: special body-comment categories such as `outside_diff_comment`, `nitpick_comment`, and `duplicate_comment`

## Practical query recipes

### See which sources are most actionable

```bash
myk-claude-tools db stats --by-source
```

Use this when you want a quick view of how often comments from each review source get addressed.

### Compare reviewers

```bash
myk-claude-tools db stats --by-reviewer
```

This is useful when your database contains multiple human or AI reviewers and you want author-level totals.

### Find repeated skipped guidance

```bash
myk-claude-tools db patterns --min 2
```

Use this to surface repeated comment clusters that may be good candidates for future auto-skip rules or reviewer guidance.

### Pull recent skipped rows directly

```bash
myk-claude-tools db query "SELECT * FROM comments WHERE status = 'skipped' ORDER BY id DESC LIMIT 10"
```

This is the quickest way to inspect recent skipped rows without writing a separate script.

### Check whether a comment has already been dismissed

```bash
echo '{"path": "foo.py", "body": "Add error handling..."}' | \
  myk-claude-tools db find-similar --owner myk-org --repo claude-code-config --json
```

Use this when you want to answer, “Have we seen and skipped something like this before?”

## Troubleshooting

> **Note:** If the database file does not exist, the commands return no results rather than creating a new database.

> **Warning:** Default database discovery depends on Git. If you run the CLI outside the repository you want to inspect, the default path may point at the wrong place or fail entirely.

> **Tip:** If the table output looks cut off, rerun the same command with `--json`. The built-in formatter truncates long cell values for readability.
