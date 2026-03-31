# CodeRabbit CLI Reference

Use this reference when CodeRabbit tells you to wait before requesting another review. In `claude-code-config`, the `myk-claude-tools coderabbit` commands are the reusable building blocks behind the GitHub review workflows.

- `check` tells you whether a pull request is currently rate-limited.
- `trigger` waits if needed, posts `@coderabbitai review`, and watches for the next review to start.

The CLI entrypoint is declared directly in the project:

```toml
[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

## Prerequisites

The project declares Python `>=3.10` in `pyproject.toml`. To use the CodeRabbit commands comfortably, you also need:

- `myk-claude-tools` on your `PATH`
- `gh` installed and authenticated, because the implementation shells out to `gh api`
- `uv` if you want to use the install flow referenced by the plugin commands

The plugin workflows in this repo use these exact checks and install command:

```bash
uv --version
myk-claude-tools --version
uv tool install myk-claude-tools
```

> **Note:** The CodeRabbit implementation itself depends on `gh`, even though the plugin command docs focus first on checking `uv` and `myk-claude-tools`.

## Command Summary

The CodeRabbit CLI exposes two subcommands:

```bash
myk-claude-tools coderabbit check <owner/repo> <pr_number>
myk-claude-tools coderabbit trigger <owner/repo> <pr_number> --wait <seconds>
```

The Click command definitions are small and direct:

```python
@coderabbit.command("check")
@click.argument("owner_repo")
@click.argument("pr_number", type=int)
def check(owner_repo: str, pr_number: int) -> None:
    """Check if CodeRabbit is rate limited on a PR.

    Outputs JSON with rate limit status and wait time.
    """
    from myk_claude_tools.coderabbit.rate_limit import run_check

    sys.exit(run_check(owner_repo, pr_number))
```

```python
@coderabbit.command("trigger")
@click.argument("owner_repo")
@click.argument("pr_number", type=int)
@click.option("--wait", "wait_seconds", type=int, default=0, help="Seconds to wait before posting review trigger")
def trigger(owner_repo: str, pr_number: int, wait_seconds: int) -> None:
    """Wait and trigger a CodeRabbit review on a PR.

    Optionally waits, then posts @coderabbitai review and polls
    until the review starts (max 10 minutes).
    """
    from myk_claude_tools.coderabbit.rate_limit import run_trigger

    sys.exit(run_trigger(owner_repo, pr_number, wait_seconds))
```

## `coderabbit check`

Use `check` when you want a machine-readable answer to one question: is this PR still rate-limited?

```bash
myk-claude-tools coderabbit check <owner/repo> <pr_number>
```

### What it returns

On success, `check` writes JSON to standard output and exits with code `0`.

The JSON shape comes straight from `run_check()`:

```python
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
return 0
```

In practice, that means:

- If the PR is not rate-limited, you get `{"rate_limited": false}`.
- If the PR is rate-limited, you get:
  - `rate_limited`
  - `wait_seconds`
  - `comment_id`

On failure, the command prints a human-readable error and exits with code `1`.

### Input rules

The repository name must be in strict `owner/repo` form:

```python
def _validate_owner_repo(owner_repo: str) -> bool:
    """Validate owner/repo format."""
    if "/" not in owner_repo or len(owner_repo.split("/")) != 2:
        print(f"Error: Invalid repository format: {owner_repo}. Expected owner/repo.")
        return False
    return True
```

> **Warning:** `check` does not auto-detect the PR for you. If you want current-branch detection, use the `/myk-github:coderabbit-rate-limit` workflow described later on this page.

## How Rate-Limit Detection Works

The CLI does not talk to a CodeRabbit-specific API. Instead, it inspects the latest CodeRabbit summary comment on the pull request through GitHub issue comments.

The core markers and parser are defined here:

```python
# HTML comment markers in CodeRabbit's summary comment
_SUMMARY_MARKER = "<!-- This is an auto-generated comment: summarize by coderabbit.ai -->"
_RATE_LIMITED_MARKER = "<!-- This is an auto-generated comment: rate limited by coderabbit.ai -->"

# Regex to parse wait time from rate limit message
_WAIT_TIME_RE = re.compile(r"Please wait \*\*(?:(\d+) minutes? and )?(\d+) seconds?\*\*")

_POLL_INTERVAL = 60  # seconds between polls
_MAX_POLL_ATTEMPTS = 10  # max 10 minutes
```

To find the comment, the implementation asks GitHub for PR issue comments and selects the last matching summary comment:

```python
code, output, _stderr = _run_gh(
    [
        "api",
        f"repos/{owner}/{repo}/issues/{pr_number}/comments",
        "--jq",
        f'[.[] | select(.body | contains("{_SUMMARY_MARKER}"))] | last | {{id: .id, body: .body}}',
    ],
    timeout=60,
)
```

That means `check` works like this:

1. Find the most recent issue comment whose body contains the CodeRabbit summary marker.
2. Look for the rate-limit marker in that comment body.
3. If present, parse the cooldown from the message text.

The tests in `tests/test_coderabbit_rate_limit.py` cover both full minute-and-second messages and seconds-only messages, including examples like:

- `Please wait **22 minutes and 57 seconds**`
- `Please wait **45 seconds**`

> **Tip:** If `check` says it cannot parse the wait time, the CLI prints the first few lines of the comment body to help you see what changed.

## `coderabbit trigger`

Use `trigger` when you already know the PR should be retried and you want the CLI to handle the waiting and polling for you.

```bash
myk-claude-tools coderabbit trigger <owner/repo> <pr_number> --wait <seconds>
```

### What it does

`run_trigger()` performs three steps:

1. Wait for the requested number of seconds, if `--wait` is greater than zero.
2. Post a fresh `@coderabbitai review` comment to the PR.
3. Poll until the review appears to have started, or time out.

The implementation is explicit:

```python
if wait_seconds > 0:
    minutes, secs = divmod(wait_seconds, 60)
    print(f"Waiting {minutes}m {secs}s before triggering review...")
    time.sleep(wait_seconds)

print("Posting @coderabbitai review...")
if not _post_review_trigger(owner_repo, pr_number):
    print("Error: Failed to post review trigger comment.")
    return 1
print("Review trigger posted.")
```

The trigger comment is posted as a GitHub issue comment:

```python
code, _, stderr = _run_gh(
    [
        "api",
        f"repos/{owner}/{repo}/issues/{pr_number}/comments",
        "-f",
        "body=@coderabbitai review",
    ],
    timeout=30,
)
```

### Polling behavior

After posting the trigger, the CLI polls once per minute, for up to ten attempts:

```python
none_streak = 0
for attempt in range(1, _MAX_POLL_ATTEMPTS + 1):
    print(f"Polling for review start (attempt {attempt}/{_MAX_POLL_ATTEMPTS})...")
    status = _is_rate_limited(owner_repo, pr_number)
    if status == "error":
        print("Warning: API error while checking status. Retrying...")
        none_streak = 0  # API errors don't count toward comment-gone detection
    elif status == "no_comment":
        none_streak += 1
        if none_streak >= 2:
            print("Review started (comment replaced).")
            return 0
        print("Warning: Could not find comment. Retrying...")
    elif not status:
        print("Review started!")
        return 0
    else:
        none_streak = 0
    if attempt < _MAX_POLL_ATTEMPTS:
        time.sleep(_POLL_INTERVAL)

print("Error: Timeout waiting for review to start (10 minutes).")
```

There are two success paths:

- The summary comment is still present, but it no longer contains the rate-limit marker.
- The summary comment disappears twice in a row, which the CLI treats as a strong signal that CodeRabbit replaced it with a new review state.

> **Note:** Two consecutive `no_comment` results count as success on purpose. The tests document this as the expected behavior when the old summary comment has been replaced.

## Workflow Integration in `myk-github`

In this repository, the GitHub review workflows live in plugin command files under `plugins/myk-github/commands/`. These workflows are where most users will encounter the CodeRabbit CLI.

### `/myk-github:coderabbit-rate-limit`

This workflow supports three forms:

```bash
/myk-github:coderabbit-rate-limit
/myk-github:coderabbit-rate-limit 123
/myk-github:coderabbit-rate-limit https://github.com/owner/repo/pull/123
```

Its documented flow is:

1. Detect the PR from the current branch, a PR number, or a full PR URL.
2. Run `coderabbit check`.
3. If the PR is rate-limited, add a 30-second buffer and run `coderabbit trigger`.

The exact commands in the workflow file are:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
gh pr view --json number,url -q '.number'
myk-claude-tools coderabbit check <owner/repo> <pr_number>
myk-claude-tools coderabbit trigger <owner/repo> <pr_number> --wait <wait_seconds + 30>
```

> **Note:** The extra 30-second buffer is added by the workflow, not by the `trigger` command itself. If you call the CLI directly, it waits for exactly the `--wait` value you pass.

### `/myk-github:review-handler --autorabbit`

The longer-running review handler also uses the same CodeRabbit commands. In its `--autorabbit` loop, it checks for a CodeRabbit cooldown before fetching new review comments again:

```bash
myk-claude-tools coderabbit check <owner/repo> <pr_number>
myk-claude-tools coderabbit trigger <owner/repo> <pr_number> --wait <wait_seconds + 30>
```

That makes the CodeRabbit CLI the shared mechanism for both:

- one-off rate-limit recovery
- automatic retry behavior inside the review handler loop

## Related CodeRabbit Configuration

The repository also enables CodeRabbit review behavior in `.coderabbit.yaml`:

```yaml
reviews:
  profile: assertive
  request_changes_workflow: true
  high_level_summary: true
  review_status: true
  collapse_walkthrough: false

  auto_review:
    enabled: true
    drafts: false
```

This config does not replace the CLI commands. Instead, it explains why the repo expects CodeRabbit summary comments and review status to exist in the first place.

## Tested Behavior

The behavior described above is backed by `tests/test_coderabbit_rate_limit.py`. The test coverage includes:

- wait-time parsing for minute-and-second and seconds-only formats
- strict `owner/repo` validation
- rate-limited and not-rate-limited JSON responses from `check`
- waiting before a trigger
- timeout handling
- failed trigger posting
- the two-consecutive-`no_comment` success heuristic
- API errors during polling

> **Tip:** If you change the detection markers or wait-time format in the implementation, update the tests at the same time. The tests already capture the edge cases that matter most for real review workflows.

## Troubleshooting

### `Error: Invalid repository format`

Use exactly `owner/repo`. The CLI rejects anything with no slash or more than one slash.

### `Error: No CodeRabbit summary comment found on this PR`

The command only works after CodeRabbit has posted its summary comment. If the PR is brand new, or CodeRabbit has not finished reviewing yet, wait and try again.

### `Error: Could not parse wait time from rate limit message`

The command found the rate-limit marker but could not match the expected wait text. The CLI prints a snippet of the comment body to help you inspect what changed.

### `gh CLI not found`

Install `gh` and make sure it is available on `PATH`. The implementation calls `gh api` directly for both detection and trigger posting.

### `Error: Failed to post review trigger comment`

Check your GitHub authentication and permissions. This step creates a PR issue comment with the body `@coderabbitai review`.

### `Error: Timeout waiting for review to start (10 minutes).`

The trigger comment was posted, but the CLI never saw a clear sign that the new review started. At that point, inspect the PR manually and retry later if needed.

> **Warning:** The detection logic depends on CodeRabbit's current comment markers and wait-message wording. If CodeRabbit changes those formats upstream, `check` may stop recognizing the cooldown until the parser is updated.
