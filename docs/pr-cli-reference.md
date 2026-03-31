# PR CLI Reference

`myk-claude-tools pr` is the PR-focused part of the CLI used by this repository's review workflows. It gives you three building blocks:

- `pr diff` fetches pull request metadata, the full diff, and per-file patch data
- `pr claude-md` loads the target repository's `CLAUDE.md` instructions
- `pr post-comment` posts one structured GitHub review with inline comments

## Before You Start

The CLI is exposed as the `myk-claude-tools` console script:

```toml
[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

The repository's own PR workflow checks the toolchain like this:

```bash
uv --version
myk-claude-tools --version
```

If the CLI is not installed, the documented install command is:

```bash
uv tool install myk-claude-tools
```

You also need:

- Python 3.10 or newer
- GitHub CLI (`gh`)
- Access to the GitHub repository you want to review

> **Note:** `pr diff` and remote `pr claude-md` call `gh` directly. `pr post-comment` also depends on `gh`, but it does not do its own friendly preflight check first, so install and verify `gh` before using it.

## Command Overview

| Command | What it returns | Best used for |
|---|---|---|
| `myk-claude-tools pr diff` | JSON | Fetching everything you need to review a PR |
| `myk-claude-tools pr claude-md` | Plain text | Loading repository-specific instructions before reviewing |
| `myk-claude-tools pr post-comment` | JSON | Posting a single review with multiple inline findings |

A typical workflow looks like this:

```bash
myk-claude-tools pr diff $ARGUMENTS
myk-claude-tools pr claude-md $ARGUMENTS
mkdir -p /tmp/claude
myk-claude-tools pr post-comment {owner}/{repo} {pr_number} {head_sha} /tmp/claude/pr-review-comments.json
```

> **Tip:** Save `metadata.head_sha` from `pr diff` and reuse it as the `commit_sha` for `pr post-comment`. That is the safest way to keep inline comment locations aligned with the exact revision you reviewed.

## Shared PR Target Formats

`pr diff` and `pr claude-md` share the same input rules. They accept any of these forms:

```bash
myk-claude-tools pr diff <owner/repo> <pr_number>
myk-claude-tools pr diff https://github.com/owner/repo/pull/123
myk-claude-tools pr diff <pr_number>

myk-claude-tools pr claude-md <owner/repo> <pr_number>
myk-claude-tools pr claude-md https://github.com/owner/repo/pull/123
myk-claude-tools pr claude-md <pr_number>
```

When you pass only a PR number, the CLI resolves the repository from the current working directory with:

```bash
gh repo view --json owner,name -q '.owner.login + "/" + .name'
```

A few practical details matter here:

- `owner/repo` must match the normal GitHub format
- `pr_number` must be numeric
- PR URLs can include an optional protocol and optional trailing path segments
- Wrong argument counts print usage and exit with status `1`

> **Warning:** Number-only mode depends on the current repository context. If you are outside the target repository, working across multiple repositories, or dealing with forks, prefer `owner/repo + pr_number` or a full PR URL.

## `pr diff`

### What it does

`pr diff` collects three kinds of data for the target PR:

- PR metadata from `GET /repos/{owner}/{repo}/pulls/{pr_number}`
- The full unified diff from `gh pr diff`
- The changed file list from `GET /repos/{owner}/{repo}/pulls/{pr_number}/files`

The file list request is paginated, so large PRs are handled across multiple API pages.

### Usage

```bash
myk-claude-tools pr diff <owner/repo> <pr_number>
myk-claude-tools pr diff https://github.com/owner/repo/pull/123
myk-claude-tools pr diff <pr_number>
```

### Output

`pr diff` always writes JSON to stdout. Its top-level structure is built like this:

```json
{
  "metadata": {
    "owner": pr_info.owner,
    "repo": pr_info.repo,
    "pr_number": pr_info.pr_number,
    "head_sha": head_sha,
    "base_ref": base_ref,
    "title": pr_title,
    "state": pr_state
  },
  "diff": pr_diff,
  "files": files
}
```

Each file entry is normalized to this shape:

```json
{
  "path": f["filename"],
  "status": f["status"],
  "additions": f["additions"],
  "deletions": f["deletions"],
  "patch": f.get("patch", "")
}
```

What those fields are most useful for:

- `metadata.head_sha` is the commit SHA you should pass to `pr post-comment`
- `metadata.base_ref` tells you which branch the PR targets
- `diff` contains the full text diff from GitHub CLI
- `files` gives you a per-file summary plus patch text when GitHub includes it

> **Note:** `files[].patch` falls back to an empty string when GitHub does not include patch text, which can happen for some large or non-text changes.

### Failure behavior

`pr diff` exits with status `1` when it cannot produce a complete result. Important cases include:

- `gh` is not installed
- the GitHub API call fails
- `gh pr diff` fails
- the file list request fails
- the PR metadata does not include `head.sha`
- the PR metadata does not include `base.ref`

Timeouts are also explicit:

- PR metadata fetch: 60 seconds
- Diff fetch: 120 seconds
- File list fetch: 120 seconds

> **Tip:** If you are scripting around `pr diff`, treat stdout as machine-readable JSON and stderr as diagnostics.

## `pr claude-md`

### What it does

`pr claude-md` resolves the same PR target formats as `pr diff`, but its output is plain text instead of JSON. The command tries to find the repository's instructions file in a specific order and stops on the first match.

### Usage

```bash
myk-claude-tools pr claude-md <owner/repo> <pr_number>
myk-claude-tools pr claude-md https://github.com/owner/repo/pull/123
myk-claude-tools pr claude-md <pr_number>
```

### Lookup order

The command checks these locations in order:

1. Local `./CLAUDE.md`, but only if the current repo matches the target repo
2. Local `./.claude/CLAUDE.md`, but only if the current repo matches the target repo
3. Remote `CLAUDE.md` from the GitHub Contents API
4. Remote `.claude/CLAUDE.md` from the GitHub Contents API
5. If nothing is found, it prints an empty line and exits successfully

Local repository matching is based on `git remote get-url origin`, and it supports both GitHub HTTPS and SSH remote formats.

> **Note:** Local files win over GitHub when the current repository matches the target repository. That makes local testing fast and lets you review unpublished `CLAUDE.md` edits before they exist upstream.

> **Tip:** The local match is based on `origin`. If your local checkout points `origin` at a fork instead of the target repository, the command usually falls back to GitHub and fetches the upstream file instead.

### Output behavior

`pr claude-md` prints one of two things:

- The raw contents of the matched `CLAUDE.md`
- An empty line if no supported file exists

That empty output is intentional.

> **Warning:** A missing `CLAUDE.md` is not treated as an error. If your automation needs to distinguish "file not found" from "file exists but is empty," you need to handle that outside this command.

### Failure behavior

You will get a non-zero exit when:

- argument parsing fails
- the current directory cannot resolve the repo and you only passed a PR number
- local matching does not apply and `gh` is not installed

Remote fetch failures are intentionally quiet. If GitHub does not return the file, the command keeps trying the next location and eventually prints empty output.

## `pr post-comment`

### What it does

`pr post-comment` takes a list of inline review comments and posts them to GitHub as one pull request review. It does not create one review per finding. Instead, it sends:

- one review summary body
- one `comments` array containing all inline comments

That makes it a good fit for "review first, then post a selected set of findings" workflows.

### Usage

```bash
myk-claude-tools pr post-comment <owner/repo> <pr_number> <commit_sha> <json_file>
myk-claude-tools pr post-comment <owner/repo> <pr_number> <commit_sha> -  # stdin
```

### Required input

The final argument is either:

- a path to a JSON file
- `-` to read JSON from stdin

The expected JSON format is an array of comment objects:

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

Each object must contain:

- `path`
- `line`
- `body`

A few small but useful details:

- `line` is converted with `int(...)`, so numeric strings work too
- missing fields cause an immediate error and exit
- invalid JSON causes an immediate error and exit
- if extra shell or hook output appears before the JSON array, the loader looks for the first line starting with `[` and tries to parse from there

> **Tip:** Stdin mode is handy when another step in your pipeline produces the JSON array dynamically and you do not want to write an intermediate file.

### Severity markers and summary generation

The first line of each comment body controls how the review summary is grouped. Supported markers are:

```text
### [CRITICAL] Title
### [WARNING] Title
### [SUGGESTION] Title
```

If no marker is present, the comment is treated as a suggestion.

The command uses those markers to generate a review body with:

- a `## Code Review` heading
- a total issue count
- grouped sections for critical issues, warnings, and suggestions
- Markdown tables listing file, line, and issue title
- a closing footer: `*Review generated by Claude Code*`

The issue title comes from the first line of the comment body after removing the severity marker. It is truncated to 80 characters for the summary table.

### What gets posted to GitHub

The review payload is built like this:

```json
{
  "commit_id": commit_sha,
  "body": review_body,
  "event": "COMMENT",
  "comments": [
    {
      "path": c.path,
      "line": c.line,
      "body": c.body,
      "side": "RIGHT"
    }
  ]
}
```

Important implications:

- the review event is always `"COMMENT"`
- every inline comment is posted on the `"RIGHT"` side
- the `commit_sha` needs to match the PR revision GitHub expects for inline comments

> **Warning:** Inline comments only work for lines GitHub considers part of the PR diff for that commit. If the line is outside the diff, the file path does not exist at that revision, or the SHA is stale, GitHub will reject the review.

> **Note:** The module defines a `validate_commit_sha()` helper, but the command does not currently call it before posting. In practice, you should pass the exact `metadata.head_sha` returned by `pr diff` instead of inventing or reusing an older SHA.

### Output

When you pass one or more comments, the command:

- prints a progress message to stderr
- posts the review
- prints a JSON result to stdout

If the comment list is empty, it skips the GitHub API call and immediately prints a success object with zero counts:

```json
{"status": "success", "comment_count": 0, "posted": [], "failed": []}
```

For normal success and failure cases, the output shape is:

```json
{
  "status": result.status,
  "comment_count": result.comment_count,
  "posted": result.posted,
  "failed": result.failed
}
```

On failure, the command also includes `error` in the JSON output and prints common troubleshooting hints to stderr:

- line numbers might not be part of the diff
- file paths might not exist in the named commit
- the commit SHA might not be the PR head

## Putting The Commands Together

The repository's own PR review command uses these subcommands in sequence:

```bash
myk-claude-tools pr diff {pr_number}
myk-claude-tools pr claude-md {pr_number}
```

When arguments are passed through directly, it uses:

```bash
myk-claude-tools pr diff $ARGUMENTS
myk-claude-tools pr claude-md $ARGUMENTS
```

After analysis, it posts the selected findings with:

```bash
myk-claude-tools pr post-comment {owner}/{repo} {pr_number} {head_sha} /tmp/claude/pr-review-comments.json
```

In practice, the flow is:

1. Run `pr diff` and keep the JSON output
2. Read `metadata.head_sha` from that output
3. Run `pr claude-md` to load repository-specific review instructions
4. Generate a JSON array of findings
5. Run `pr post-comment` with the same PR and the `head_sha` from step 2

> **Tip:** Keep `pr diff` and `pr post-comment` tied to the same review session. Re-fetch the diff if the PR head changes before you post comments.

## Configuration Snippet For Claude Code Plugins

If you are wrapping these commands in a Claude Code plugin or slash command, this repository's own PR review command uses this frontmatter:

```markdown
---
description: Review a GitHub PR and post inline comments on selected findings
argument-hint: [PR_NUMBER|PR_URL]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion, Task
---
```

That configuration captures the two important runtime requirements for this CLI:

- allow the plugin to call `myk-claude-tools`
- allow the plugin to call `gh`

If you are automating around these commands, it is also useful to remember the output contract:

- `pr diff` returns JSON
- `pr claude-md` returns plain text
- `pr post-comment` returns JSON, but also writes progress and troubleshooting output to stderr
