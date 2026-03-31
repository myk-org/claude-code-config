# Review Workflows

This project gives you a complete review loop inside Claude Code: you can review local changes before you push, review a GitHub PR and post selected findings, process comments from multiple review sources on an open PR, refine your own draft review before submitting it, and store the outcome so future review rounds get smarter.

| If you want to... | Use |
|---|---|
| Review uncommitted or branch-to-branch changes | `/myk-review:local [branch]` |
| Review a GitHub PR and optionally post findings | `/myk-github:pr-review [PR number or URL]` |
| Process incoming human, Qodo, and CodeRabbit comments on a PR | `/myk-github:review-handler [--autorabbit] [review URL]` |
| Polish your own draft review before submitting it | `/myk-github:refine-review <PR_URL>` |
| Inspect stored review history and patterns | `/myk-review:query-db ...` or `myk-claude-tools db ...` |

> **Note:** The shipped configuration enables both review plugins:

```96:103:settings.json
  "enabledPlugins": {
    "pyright-lsp@claude-plugins-official": true,
    "jdtls-lsp@claude-plugins-official": true,
    "lua-lsp@claude-plugins-official": true,
    "github@claude-plugins-official": true,
    "myk-review@myk-org": true,
    "myk-github@myk-org": true,
    "code-simplifier@claude-plugins-official": true,
```

> **Note:** GitHub-facing review commands check for `uv`, `myk-claude-tools`, and `gh` before they run.

## Local Diff Review

Use `/myk-review:local` when you want fast feedback without touching GitHub. It is the lightest-weight workflow in the repo.

How it works:

- `/myk-review:local` reviews your staged and unstaged changes with `git diff HEAD`.
- `/myk-review:local <branch>` reviews your branch against another branch with `git diff "<branch>"...HEAD`.
- The diff is sent to three review agents in parallel, then their findings are merged and deduplicated before you see them.

In practice, this is the best workflow for pre-push review or for checking a feature branch before you open a PR.

> **Tip:** Use `/myk-review:local main` when you want “what changed since I branched?” and `/myk-review:local` when you want “what have I changed right now?”

## GitHub PR Review

Use `/myk-github:pr-review` when you want Claude to review a real PR and optionally post selected findings back to GitHub.

This workflow does more than just fetch a diff. It also resolves the base repository context, which matters for fork-based PRs, and pulls the repository’s `CLAUDE.md` so the review agents can judge the PR in project context.

The PR diff command produces a structured payload with metadata, the full diff, and the changed-file list:

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

That data is then analyzed by the three review agents. After you choose which findings to post, the tool sends them to GitHub as a single review with a summary body and inline comments:

```281:295:myk_claude_tools/pr/post_comment.py
    payload = {
        "commit_id": commit_sha,
        "body": review_body,
        "event": "COMMENT",
        "comments": [
            {
                "path": c.path,
                "line": c.line,
                "body": c.body,
                "side": "RIGHT",
            }
            for c in comments
        ],
    }
```

What this means for you:

- You can run `/myk-github:pr-review` with no argument to auto-detect the current branch’s PR.
- You can also pass a PR number or full PR URL.
- You stay in control of what gets posted: all findings, none, or only selected ones.

> **Tip:** Inline comments can only be posted on lines that are part of the PR diff. If posting fails, the first things to check are the file path, the line number, and whether the PR head SHA changed since the review started.

## Multi-Source Review Handling

Use `/myk-github:review-handler` when a PR already has reviewer feedback and you want to work through it systematically.

This is the full review-processing workflow. It fetches unresolved review threads, categorizes them by source, lets you decide what to do with each item, applies fixes, posts replies, and stores the results for future analytics and auto-skip matching.

Fetched review items are enriched with a source, priority, reply field, and status:

```682:691:myk_claude_tools/reviews/fetch.py
        source = detect_source(author)
        priority = classify_priority(body)

        enriched = {
            **thread,
            "source": source,
            "priority": priority,
            "reply": thread.get("reply"),
            "status": thread.get("status", "pending"),
        }
```

The workflow groups review threads into three top-level buckets:

- `human`
- `qodo`
- `coderabbit`

CodeRabbit also gets special handling because some of its comments are embedded in the review body instead of normal GitHub review threads:

```1:14:myk_claude_tools/reviews/coderabbit_parser.py
"""Parse CodeRabbit review body comments (outside diff range, nitpick, and duplicate).

CodeRabbit embeds certain comments directly in the review body text
(not as inline threads). This module extracts those comments into
structured data. Three kinds of body-embedded sections are supported:

- **Outside diff range** comments (code outside the PR diff range)
- **Nitpick** comments (minor suggestions)
- **Duplicate** comments (comments repeated from previous reviews)

The expected format is a blockquoted ``<details>`` section with nested
```

That matters because `review-handler` is designed to give you one place to process:

- regular human review threads
- Qodo comments
- CodeRabbit inline threads
- CodeRabbit outside-diff, nitpick, and duplicate comments

A typical flow looks like this:

1. Fetch open review items from the current PR.
2. Show everything to the user, including auto-skipped items.
3. Decide what to address, what to skip, and why.
4. Make code changes and run tests.
5. Post replies to GitHub.
6. Store the completed review result in the local database.

> **Note:** Auto-skipped items are still shown in the review tables. The workflow treats auto-skip as a suggested default, not as a hidden deletion.

If you use `--autorabbit`, CodeRabbit items are auto-approved for action while human and Qodo items still follow the normal decision flow.

> **Warning:** `--autorabbit` is a polling loop. It keeps checking for new CodeRabbit comments until you stop it.

## Pending-Review Refinement

Use `/myk-github:refine-review <PR_URL>` when you already started a review in the GitHub UI and want help rewriting your draft comments before you submit them.

This workflow is intentionally different from `review-handler`:

- It does not fetch all unresolved review feedback on the PR.
- It fetches only your own `PENDING` review.
- It is meant for editing your draft review comments, not responding to other reviewers.

The update command expects a JSON structure like this:

```7:31:myk_claude_tools/reviews/pending_update.py
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

Status handling:
  - accepted: Update comment body with refined_body
  - Other statuses: Skip (no update)
```

When `pending-fetch` builds the comment list, each comment starts in a neutral state with the original body preserved and a place for an accepted refinement:

```163:172:myk_claude_tools/reviews/pending_fetch.py
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

Only accepted comments with a changed `refined_body` are updated, and submission is guarded very deliberately:

```254:276:myk_claude_tools/reviews/pending_update.py
    # Optionally submit the review (requires both JSON submit_action AND --submit flag)
    submit_action = metadata.get("submit_action")
    if submit_action and submit:
        if submit_action not in VALID_SUBMIT_ACTIONS:
            print_stderr(
                f"Error: Invalid submit_action '{submit_action}'. "
                f"Must be one of: {', '.join(sorted(VALID_SUBMIT_ACTIONS))}"
            )
            return 1

        if fail_count > 0:
            print_stderr(f"Skipping review submission due to {fail_count} failed update(s)")
        else:
            submit_summary = metadata.get("submit_summary", "")
            print_stderr(f"Submitting review with action: {submit_action}...")
    elif submit_action and not submit:
        print_stderr(f"Note: submit_action='{submit_action}' set but --submit flag not passed. Skipping submission.")
```

That gives you a safe review flow:

- refine everything
- accept only the edits you want
- optionally submit as `COMMENT`, `APPROVE`, or `REQUEST_CHANGES`
- or leave the review pending and come back later

> **Warning:** Submission requires both the metadata field `submit_action` and the CLI flag `--submit`. If one is missing, the review will not be submitted.

> **Warning:** A `404` during pending-review update usually means the draft review was already submitted or deleted somewhere else.

## Auto-Skip Behavior

One of the most useful features in this repo is automatic skipping of repeated, previously dismissed review comments.

When the tool fetches new review items, it checks the review database for similar comments that were previously marked `skipped` or `not_addressed`, and in some cases `addressed` for body-comment types. If it finds a close enough match, it enriches the new item so it already carries the earlier decision and reason.

Here is the core matching logic:

```717:740:myk_claude_tools/reviews/fetch.py
                    if candidates:
                        best = None
                        best_score = 0.0
                        for prev in candidates:
                            prev_body = (prev.get("body") or "").strip()
                            if not prev_body:
                                continue
                            score = similarity(thread_body, prev_body)
                            if score >= 0.6 and score > best_score:
                                best = prev
                                best_score = score
                                if best_score == 1.0:
                                    break

                        if best:
                            reason = (best.get("skip_reason") or best.get("reply") or "").strip()
                            if reason:
                                original_status = best.get("status", "skipped")
                                enriched["status"] = "skipped"
                                enriched["skip_reason"] = reason
                                enriched["original_status"] = original_status  # Display-only, not persisted to DB
                                enriched["reply"] = f"Auto-skipped ({original_status}): {reason}"
                                enriched["is_auto_skipped"] = True
```

A few practical details matter here:

- Matching is based on exact path first, with a `comment_id` fallback for pathless body comments.
- The similarity threshold is `0.6`.
- The similarity function is Jaccard-style word overlap, not exact string equality.
- The original reason is carried forward so you can see why the new item was auto-skipped.

The database query is intentionally conservative about what counts as safe auto-skip input:

```193:202:myk_claude_tools/db/query.py
        Retrieves comments that were dismissed during review processing:
        - ``not_addressed`` and ``skipped`` comments are always included (any type).
        - ``addressed`` comments are only included when their type is
          ``outside_diff_comment``, ``nitpick_comment``, or
          ``duplicate_comment``.  These types lack a GitHub review thread
          that can be resolved, so the database is the only mechanism to
          auto-skip them on subsequent fetches.  Normal
          inline thread comments rely on GitHub's ``isResolved`` filter in
          the GraphQL query, so including them here could incorrectly
          auto-skip a similar new finding in a different PR.
```

> **Tip:** Auto-skip gets better over time only if you store completed review results. If you skip `reviews store`, future review rounds lose that memory.

## Reply Posting And Thread Resolution

`myk-claude-tools reviews post <json_path>` is the command that actually replies on GitHub after statuses and messages have been set.

It handles two different kinds of review feedback:

- normal GitHub review threads that have a resolvable thread ID
- body-only comments such as CodeRabbit outside-diff, nitpick, and duplicate comments

The resolution policy is intentionally different for human and AI reviewers:

```538:582:myk_claude_tools/reviews/post.py
            # Outside-diff and nitpick comments have no GitHub thread to post to or resolve.
            # They are tracked via the review database only.
            comment_type = thread_data.get("type")
            if comment_type in ("outside_diff_comment", "nitpick_comment", "duplicate_comment"):
                if status == "pending":
                    pending_count += 1
                    eprint(f"Skipping {category}[{i}] ({path}): {comment_type} status is pending")
                    continue
                if status in ("addressed", "not_addressed", "skipped", "failed"):
                    # Skip if already posted (idempotency)
                    if posted_at:
                        already_posted_count += 1
                        eprint(f"Skipping {category}[{i}] ({path}): {comment_type} already posted at {posted_at}")
                        continue

                    # Skip auto-skipped entries — they were already replied to in a previous cycle
                    if thread_data.get("is_auto_skipped"):
                        already_posted_count += 1
                        eprint(
                            f"Skipping {category}[{i}] ({path}): {comment_type}"
                            " auto-skipped (already replied in previous cycle)"
                        )
                        continue
...
            # Determine if we should resolve this thread (MUST be before resolve_only_retry check)
            should_resolve = True
            if category == "human" and status != "addressed":
                should_resolve = False
```

What that means in practice:

- `addressed` replies resolve normal threads.
- `not_addressed` and `skipped` still post a reply.
- Human `not_addressed` and `skipped` threads stay open so the human reviewer can follow up.
- Qodo and CodeRabbit threads resolve after reply.
- Outside-diff, nitpick, and duplicate comments are collected into consolidated PR comments per reviewer instead of thread replies.

If something fails, the command is designed to be rerun safely. Already-posted entries are skipped, and partially processed entries can retry the missing step.

> **Note:** If a post fails, rerun the exact `myk-claude-tools reviews post <json_path>` command the tool prints. The workflow is intentionally idempotent enough to retry without reposting everything.

## Review Result Storage And Analytics

After replies are posted, `myk-claude-tools reviews store <json_path>` persists the finished review to SQLite so the repo can support analytics and future auto-skip matching.

The storage path is inside the project, not in a global database:

```206:214:myk_claude_tools/reviews/store.py
    # Get project root and database path
    project_root = get_project_root()

    # Get current commit SHA (anchored to repo root for correctness)
    commit_sha = get_current_commit_sha(cwd=project_root)

    log(f"Storing reviews for {owner}/{repo}#{pr_number} (commit: {commit_sha[:7]})...")

    db_path = project_root / ".claude" / "data" / "reviews.db"
```

A few important storage behaviors are worth knowing:

- The current `HEAD` SHA is stored with each review record.
- Review history is append-only, so multiple review passes on the same PR build history instead of overwriting each other.
- Per-comment data includes source, author, path, line, body, priority, status, reply, timestamps, and comment type.

> **Warning:** `reviews store` deletes the JSON file after successful storage. Treat the JSON as a working file, not a permanent artifact.

Once the data is stored, you can query it either through `/myk-review:query-db` or directly with the CLI.

Useful commands:

- `myk-claude-tools db stats --by-source`
- `myk-claude-tools db stats --by-reviewer`
- `myk-claude-tools db patterns --min 2`
- `myk-claude-tools db dismissed --owner <owner> --repo <repo>`
- `myk-claude-tools db query "SELECT status, COUNT(*) AS cnt FROM comments GROUP BY status"`
- `echo '{"path":"src/main.py","body":"Consider adding error handling"}' | myk-claude-tools db find-similar --owner <owner> --repo <repo> --json`

Raw SQL queries are intentionally locked down to read-only entry points:

```562:588:myk_claude_tools/db/query.py
        # Safety check: only allow SELECT/CTE statements
        sql_stripped = sql.strip()
...
        # Block multiple statements (semicolon separating statements, not in strings/comments)
        sql_stmt_check = _strip_sql_strings(sql_for_checks).rstrip(";")
        if ";" in sql_stmt_check:
            raise ValueError("Multiple SQL statements are not allowed")

        # Allow SELECT and WITH (CTE) as read-only entrypoints
        if not sql_upper.startswith(("SELECT", "WITH")):
            raise ValueError("Only SELECT/CTE queries are allowed for safety")
```

That makes the analytics side safe for exploration while still giving you useful ways to answer questions like:

- Which review source has the highest addressed rate?
- Which reviewer keeps raising the same suggestion?
- Which comments were skipped, and why?
- Has this “new” CodeRabbit comment already been dismissed in an earlier cycle?

## Recommended Flow

For most teams, the smoothest path looks like this:

1. Use `/myk-review:local` before pushing or opening a PR.
2. Use `/myk-github:pr-review` when you want Claude-generated PR findings and optional inline GitHub comments.
3. Use `/myk-github:review-handler` after human, Qodo, or CodeRabbit feedback arrives.
4. Use `/myk-github:refine-review` only for your own draft GitHub review comments.
5. Always store completed review runs so auto-skip and analytics keep getting better.
