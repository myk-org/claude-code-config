# Reviews CLI Reference

`myk-claude-tools reviews` supports two different workflows:

1. Handle feedback that already exists on a pull request: `fetch` -> edit JSON -> `post` -> `store`.
2. Refine your own draft GitHub review before submitting it: `pending-fetch` -> edit JSON -> `pending-update`.

> **Warning:** `reviews post` only works with JSON created by `reviews fetch`. `reviews pending-update` only works with JSON created by `reviews pending-fetch`. The two file formats are different.

## At a Glance

| Command | Use it when you want to | Input | What it writes |
| --- | --- | --- | --- |
| `myk-claude-tools reviews fetch [REVIEW_URL]` | Pull unresolved PR review feedback into a machine-editable file | Optional GitHub PR/review URL | A temp JSON file and the full JSON on stdout |
| `myk-claude-tools reviews post JSON_PATH` | Post replies and resolve review threads from a fetched JSON file | JSON from `reviews fetch` | GitHub replies/resolutions and updated timestamps in the same JSON file |
| `myk-claude-tools reviews pending-fetch PR_URL` | Pull your own pending GitHub review into a refinement file | Required PR URL | A temp JSON file and its path on stdout |
| `myk-claude-tools reviews pending-update JSON_PATH [--submit]` | Push refined pending-review comments back to GitHub | JSON from `reviews pending-fetch` | Updated GitHub review comments, and optionally a submitted review |
| `myk-claude-tools reviews store JSON_PATH` | Archive a completed review run for analytics and later auto-skip behavior | JSON from `reviews fetch` after posting | Rows in `.claude/data/reviews.db`, then deletes the JSON file |

## Requirements and Paths

- `gh` is required for all GitHub operations.
- `git` is required by `reviews fetch`, `reviews pending-fetch`, and `reviews store`.
- Authentication comes from your normal GitHub CLI session. These commands shell out to `gh`; they do not read GitHub tokens directly.
- Temp review files are written under `$TMPDIR/claude` when `TMPDIR` is set, otherwise under the system temp directory.
- `reviews store` writes to `<git-root>/.claude/data/reviews.db`.

```858:866:myk_claude_tools/reviews/fetch.py
tmp_base = Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
out_dir = tmp_base / "claude"
out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
try:
    out_dir.chmod(0o700)
except OSError as e:
    print_stderr(f"Warning: unable to set permissions on {out_dir}: {e}")

json_path = out_dir / f"pr-{pr_number}-reviews.json"
```

> **Note:** The CLI tries to create temp and database directories with `0700` permissions, which is useful on shared machines.

## `reviews fetch`

**Syntax:** `myk-claude-tools reviews fetch [REVIEW_URL]`

Use `fetch` when you want a full, structured view of unresolved PR feedback that you can review, enrich, and feed back into `reviews post`.

```54:60:plugins/myk-github/commands/review-handler.md
myk-claude-tools reviews fetch $ARGUMENTS
# ... later in the same file ...
myk-claude-tools reviews fetch
```

What `fetch` does:

- If you pass a valid GitHub PR URL, it extracts `owner`, `repo`, and `pr_number` directly from that URL.
- If you do not pass a valid PR URL, it falls back to the current branch and asks GitHub which open PR matches that branch.
- If an `upstream` remote exists, it checks that too, which is helpful in fork-based workflows.
- It fetches unresolved GitHub review threads through GraphQL.
- It also parses CodeRabbit comments that are embedded in review bodies rather than exposed as normal review threads.
- It groups everything into `human`, `qodo`, and `coderabbit`.
- It enriches each item with `source`, `priority`, `reply`, and `status`.

The generated file is the input for `reviews post`. The filename pattern is:

- `pr-<pr_number>-reviews.json`

What you should expect in the output:

- `metadata.owner`, `metadata.repo`, `metadata.pr_number`, and `metadata.json_path`
- Arrays named `human`, `qodo`, and `coderabbit`
- A default `status` of `pending`
- A default `reply` of `null`

`priority` is heuristic rather than GitHub-native:

- Comments mentioning security, bugs, crashes, or other critical language become `HIGH`.
- Comments mentioning style, formatting, nitpicks, or minor cleanup become `LOW`.
- Everything else defaults to `MEDIUM`.

> **Note:** If `.claude/data/reviews.db` already exists, `fetch` can auto-skip previously dismissed similar comments from the same repository and include the skip reason directly in the JSON.

> **Warning:** If `fetch` cannot infer a PR from the current branch, it exits. Detached HEAD is not supported for branch-based detection.

> **Tip:** A review URL is optional, but it is useful when you want extra context from a specific review or discussion link such as `#pullrequestreview-...` or `#discussion_r...`.

## `reviews post`

**Syntax:** `myk-claude-tools reviews post JSON_PATH`

Use `post` after you have reviewed the JSON from `fetch` and filled in the decision fields you want GitHub to receive.

```239:260:plugins/myk-github/commands/review-handler.md
myk-claude-tools reviews post {json_path}
# ... after output verification ...
myk-claude-tools reviews store {json_path}
```

The fields you usually edit before running `post` are:

| Field | Meaning |
| --- | --- |
| `status` | One of `addressed`, `not_addressed`, `skipped`, `pending`, or `failed` |
| `reply` | The text to post back to GitHub |
| `skip_reason` | Optional explicit reason for a skipped item |

What `post` does with each status:

| Status | Human review thread | Qodo/CodeRabbit review thread | Body-embedded CodeRabbit comment |
| --- | --- | --- | --- |
| `addressed` | Posts a reply and resolves the thread | Posts a reply and resolves the thread | Includes it in a consolidated PR comment to the reviewer |
| `not_addressed` | Posts a reply and leaves the thread open | Posts a reply and resolves the thread | Includes it in a consolidated PR comment to the reviewer |
| `skipped` | Posts a reply and leaves the thread open | Posts a reply and resolves the thread | Includes it in a consolidated PR comment to the reviewer |
| `pending` | Ignores it | Ignores it | Ignores it |
| `failed` | Retries it on the next run | Retries it on the next run | Treats it as eligible for a consolidated retry post |

A few important behaviors are easy to miss:

- If a thread has no `thread_id` but does have a `node_id`, `post` tries to look up the missing thread ID before replying.
- CodeRabbit `outside_diff_comment`, `nitpick_comment`, and `duplicate_comment` entries do not have normal GitHub review threads, so `post` groups them by reviewer and posts one or more consolidated PR comments instead.
- Very large replies are truncated before posting, and large consolidated body-comment replies are split into multiple PR comments.
- After a successful run, the tool updates the JSON with `posted_at` and `resolved_at` timestamps.

> **Tip:** Re-running `reviews post` is safe. Entries with `posted_at` are skipped, and entries with `posted_at` but no `resolved_at` are retried as resolve-only operations.

> **Warning:** If any post fails, the command exits non-zero and prints an `ACTION REQUIRED` retry command to stdout. Run that retry before moving on to `reviews store`.

## `reviews pending-fetch`

**Syntax:** `myk-claude-tools reviews pending-fetch PR_URL`

Use `pending-fetch` when you already started a review on GitHub, saved it as a pending review, and want to polish those draft comments locally before submitting them.

```40:41:plugins/myk-github/commands/refine-review.md
myk-claude-tools reviews pending-fetch "<PR_URL>"
```

What `pending-fetch` does:

- Parses the PR URL and refuses to continue if it is not a GitHub pull request URL.
- Looks up the authenticated `gh` user.
- Fetches that user's `PENDING` review on the PR.
- If more than one pending review exists, it uses the most recent one.
- Fetches all comments from that pending review.
- Fetches the PR diff for context and truncates it to 50,000 characters if needed.
- Saves the result to a temp JSON file and prints only the file path to stdout.

The filename pattern is:

- `pr-<owner>-<repo>-<pr_number>-pending-review.json`

The generated JSON includes metadata, comments, and the diff:

```266:277:myk_claude_tools/reviews/pending_fetch.py
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

Each comment includes these user-facing fields:

- `id`
- `path`
- `line`
- `side`
- `body`
- `diff_hunk`
- `refined_body`
- `status`

> **Warning:** `pending-fetch` only looks for the authenticated `gh` user's pending review. If `gh` is logged into the wrong account, the command will not find the review you expect.

> **Warning:** If no pending review exists yet, the command exits and tells you to start a review on GitHub first by adding comments without submitting.

## `reviews pending-update`

**Syntax:** `myk-claude-tools reviews pending-update JSON_PATH [--submit]`

Use `pending-update` after you have refined one or more comments in the JSON from `pending-fetch`.

```132:138:plugins/myk-github/commands/refine-review.md
myk-claude-tools reviews pending-update "<json_path>" --submit
# ... or keep the review pending ...
myk-claude-tools reviews pending-update "<json_path>"
```

This command only updates comments that meet all of these conditions:

- `status` is exactly `accepted`
- `refined_body` is non-empty
- `refined_body` is actually different from the original `body`

The JSON format it expects includes optional submission metadata:

```7:26:myk_claude_tools/reviews/pending_update.py
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

Valid `submit_action` values are:

| Value | Meaning |
| --- | --- |
| `COMMENT` | Submit the pending review as general feedback |
| `APPROVE` | Approve the PR |
| `REQUEST_CHANGES` | Submit the review as a request for changes |

> **Note:** Submitting a review is a two-part opt-in. You must set `metadata.submit_action` in the JSON and also pass `--submit` on the command line. Providing only one of them is not enough.

> **Tip:** If you want to refine comments now but keep the review pending on GitHub, leave `submit_action` unset or run the command without `--submit`.

> **Warning:** If GitHub returns `404` while updating a comment, the command aborts the remaining updates because the pending review may already have been submitted or deleted elsewhere.

## `reviews store`

**Syntax:** `myk-claude-tools reviews store JSON_PATH`

Use `store` at the end of the review-thread workflow, after `reviews post` has finished successfully and the JSON reflects the final timestamps and statuses.

`store` does three things:

- Writes a new review record to the local SQLite database.
- Writes one comment row for every item in `human`, `qodo`, and `coderabbit`.
- Deletes the JSON file after a successful import.

It records the current commit SHA from the current checkout, so the stored review is tied to a specific code state. The storage model is append-only: if you run `store` again for the same PR later, it creates another review record instead of overwriting the old one.

```214:260:myk_claude_tools/reviews/store.py
db_path = project_root / ".claude" / "data" / "reviews.db"

# ... insert a new review row and one row per comment ...

conn.commit()

# Delete JSON file after successful storage
json_path.unlink()
```

The stored comment data includes, among other things:

- Source (`human`, `qodo`, or `coderabbit`)
- Thread and comment identifiers
- Author, file path, and line number
- Comment body
- Priority
- Status
- Reply text
- Skip reason
- `posted_at` and `resolved_at`
- Optional comment type such as `outside_diff_comment`, `nitpick_comment`, or `duplicate_comment`

> **Tip:** `store` is what makes later `reviews fetch` runs smarter. `fetch` can use this database to auto-skip previously dismissed comments.

> **Warning:** `reviews store` deletes the JSON file after a successful import. Run it last.

> **Warning:** The database path is based on the current git root, not on the PR URL inside the JSON. Run it from the checkout that should own the stored review data.

## JSON Fields You Will Usually Edit

### Review-thread JSON from `reviews fetch`

| Field | What you set | Used by |
| --- | --- | --- |
| `status` | `addressed`, `not_addressed`, `skipped`, `pending`, or `failed` | `reviews post` |
| `reply` | The message that should be posted back to GitHub | `reviews post` |
| `skip_reason` | A reason for skipping the comment | `reviews post` |

You normally do **not** set these manually:

- `posted_at`
- `resolved_at`
- `priority`
- `source`
- `json_path`

### Pending-review JSON from `reviews pending-fetch`

| Field | What you set | Used by |
| --- | --- | --- |
| `comments[].refined_body` | The polished replacement comment body | `reviews pending-update` |
| `comments[].status` | `accepted` to update the GitHub comment, or leave `pending` to skip it | `reviews pending-update` |
| `metadata.submit_action` | `COMMENT`, `APPROVE`, or `REQUEST_CHANGES` | `reviews pending-update --submit` |
| `metadata.submit_summary` | Optional review summary text | `reviews pending-update --submit` |

> **Tip:** Leave `metadata.owner`, `metadata.repo`, `metadata.pr_number`, `metadata.review_id`, and `metadata.json_path` alone unless you are deliberately debugging the workflow.

## Common Workflows

1. To handle incoming PR review feedback, run `reviews fetch`, update the generated JSON with decisions, run `reviews post`, then run `reviews store`.
2. To refine your own draft GitHub review, start a pending review on GitHub, run `reviews pending-fetch`, update `refined_body` and `status`, optionally add `submit_action` and `submit_summary`, then run `reviews pending-update` with or without `--submit`.
3. If you want future `fetch` runs to remember skipped or dismissed feedback, always finish the review-thread workflow with `reviews store`.
