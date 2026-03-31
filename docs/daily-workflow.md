# Daily Workflow

This configuration is designed to make a Claude session behave like a guided development workflow, not a free-form chat. In a normal session, the main assistant triages the request, routes implementation to the right specialist, runs mandatory review and validation, and uses hooks to keep Git and command usage safe.

If you are using this repo as your Claude Code configuration, this is the day-to-day flow you should expect.

## At a glance

1. The session starts by checking that required tools and plugins are installed.
2. Your request is triaged to decide whether it needs the full issue-first workflow or can be handled directly.
3. The main assistant acts as the orchestrator and routes work to the right specialist agent.
4. Any code change goes through a required three-reviewer loop.
5. Tests and local validation run before work is considered done.
6. Git safety hooks block risky commits and pushes.
7. GitHub review workflows use temporary JSON files in `/tmp/claude/` and store review history in `.claude/data/reviews.db`.

## 1. Session start: check the environment first

When a session starts, this configuration immediately runs a startup check and injects its rules into the prompt flow. In `settings.json`, the hooks are wired like this:

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

That means two things happen automatically:

- Every prompt gets a reminder that the main assistant should act like a manager and delegate work.
- Every new session checks whether the environment can actually support the configured workflow.

The startup checker treats some items as critical, especially:

- `uv`, because the Python hooks run through `uv`
- The three review plugins: `pr-review-toolkit`, `superpowers`, and `feature-dev`

It also checks for useful tools such as `gh`, `jq`, `gawk`, `prek`, and `mcpl`.

> **Note:** The startup check is informational, not blocking. If tools are missing, the session continues, but you should expect parts of the workflow to be unavailable or degraded until you install the missing pieces.

> **Warning:** Without the three review plugins, the mandatory review loop cannot run as intended.

## 2. Intake and triage: decide whether this is full workflow work

Before implementation starts, the config expects the request to be classified. The issue-first rule is written as a checklist:

```text
## Pre-Implementation Checklist (START HERE)

Before ANY code changes, complete this checklist:

1. **Should this workflow be skipped?** (see "SKIP this workflow for" list below)
   - YES → Do directly, skip remaining steps
   - NO → Continue checklist

2. **GitHub issue created?**
   - NO → Create issue first (delegate to `github-expert`)
   - YES → Continue

3. **On correct branch?** (`feat/issue-N-...` or `fix/issue-N-...`)
   - NO → Create branch from origin/main (delegate to `git-expert`)
   - YES → Continue

4. **User confirmed "work on it now"?**
   - NO → Ask user
   - YES → Proceed with implementation
```

In practice, that means:

- Use the full issue-and-branch flow for features, bug fixes, refactors, and multi-file work.
- Skip it for simple questions, exploration, tiny fixes, or when the user explicitly wants a quick one-off change.

This matters because the rest of the workflow assumes work is happening on a safe branch with a clear unit of scope.

> **Tip:** If the task is substantial enough that you would want a branch name, a checklist, or a progress trail, it probably belongs in the full issue-first workflow.

## 3. Delegate implementation instead of doing everything in one place

The repository is built around an orchestrator pattern:

- The main assistant plans, reads, asks questions, and routes work.
- Specialist agents do the actual implementation in their domain.

Routing is based on intent, not just the tool being used. A few important examples from `rules/10-agent-routing.md`:

- Python work goes to `python-expert`
- Local Git work goes to `git-expert`
- GitHub issues, PRs, and releases go to `github-expert`
- Documentation work goes to `technical-documentation-writer`
- Tests go to `test-automator`

This is reinforced both by policy and by command restrictions. For example, `scripts/rule-enforcer.py` blocks direct `python`, `pip`, and `pre-commit` calls and expects `uv`, `uvx`, or `prek` instead:

```python
def is_forbidden_python_command(command: str) -> bool:
    """Check if command uses python/pip directly instead of uv."""
    cmd = command.strip().lower()

    # Allow uv/uvx commands
    if cmd.startswith(("uv ", "uvx ")):
        return False

    # Block direct python/pip
    forbidden = ("python ", "python3 ", "pip ", "pip3 ")
    return cmd.startswith(forbidden)


def is_forbidden_precommit_command(command: str) -> bool:
    """Check if command uses pre-commit directly instead of prek."""
    cmd = command.strip().lower()

    # Block direct pre-commit commands
    return cmd.startswith("pre-commit ")
```

That gives you a simple rule of thumb:

- Use specialist agents for implementation.
- Use `uv` and `uvx` for Python execution.
- Use `prek` instead of calling `pre-commit` directly.

### The big exception: slash commands

Slash commands do not follow the normal "delegate everything" rule. Once you invoke a slash command, that command's own workflow takes over. The slash-command rule makes that explicit:

- The orchestrator executes the slash command directly.
- Its internal steps run directly unless the slash command itself tells the assistant to use an agent.
- Normal delegation rules are suspended for the duration of that slash command.

This is why commands like `/myk-github:pr-review` and `/myk-github:review-handler` feel more like guided tools than normal chat prompts.

## 4. Review is mandatory, and it is parallel

After any code change, the configured session is expected to enter the review loop. The rule is very direct:

```text
┌───────────────────────────────────────────────────────────────────┐
│  1. Specialist writes/fixes code                                 │
│              ↓                                                   │
│  2. Send to ALL 3 review agents IN PARALLEL:                     │
│     - `superpowers:code-reviewer`                                │
│     - `pr-review-toolkit:code-reviewer`                          │
│     - `feature-dev:code-reviewer`                                │
│              ↓                                                   │
│  3. Merge findings from all 3 reviewers                          │
│              ↓                                                   │
│  4. Has comments from ANY reviewer? ──YES──→ Fix code (go to 2)  │
│              │                                                   │
│             NO                                                   │
│              ↓                                                   │
│  5. Run `test-automator`                                         │
│              ↓                                                   │
│  6. Tests pass? ──NO──→ Fix code                                 │
│              │              ↓                                    │
│              │         Minor fix (test/config only)?             │
│              │           YES → re-run tests (go to 5)           │
│              │           NO  → full re-review (go to 2)         │
│             YES                                                  │
│              ↓                                                   │
│  ✅ DONE                                                         │
└───────────────────────────────────────────────────────────────────┘
```

A few practical points follow from this:

- The three reviewers are not optional.
- They are expected to run in parallel, not one after another.
- Duplicate feedback is merged before the next fix round.
- If any reviewer still has a real issue, the code goes back for changes.

The deduplication rule prioritizes findings in this order:

1. Security
2. Correctness
3. Performance
4. Style

> **Warning:** In this configuration, "looks good enough" is not the same as "done." A change is done only after the review loop is clear and tests pass.

## 5. Validation happens locally, with `tox`, `pytest`, and pre-commit tooling

This repo does not rely on an in-repo GitHub Actions workflow to define the normal validation path. There are no `.github/workflows` files here. Instead, the day-to-day workflow is enforced locally through hooks, `tox`, and pre-commit configuration.

The test environment is defined in `tox.toml`:

```toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

So the underlying unit-test path is:

- `pytest`
- run through `uv`
- scoped to the `tests` directory

The repository also has a substantial `.pre-commit-config.yaml` with checks such as:

- `ruff`
- `ruff-format`
- `flake8`
- `mypy`
- `gitleaks`
- `detect-secrets`
- `markdownlint`

That means a normal local validation pass is expected to include both test execution and code-quality checks.

> **Tip:** If you are validating changes yourself, think in two layers: "Does the code work?" and "Does it pass the repo's local quality gates?"

## 6. Use task tracking for long or multi-phase work

For complex workflows, the session is expected to create and maintain tasks rather than trying to keep everything in short-term conversational memory.

The task rules say tasks are persisted to disk under `~/.claude/tasks/<session-uuid>/` and are useful for:

- multi-step work
- work that may be interrupted
- workflows with clear phases
- work where progress visibility helps

They also require cleanup at the end. If a workflow created tasks, those tasks should be marked complete before the session moves on.

This is especially relevant for multi-phase slash commands, where there is a clear progression like:

1. collect input
2. execute changes
3. test
4. post results
5. clean up tasks

> **Note:** The task system is for longer-running orchestration. It is not meant for every tiny action inside a short, one-step task.

## 7. Git safety is enforced, not just recommended

This configuration protects Git history aggressively. The Git hook intercepts `git commit` and `git push` and blocks unsafe cases, including:

- committing on `main` or `master`
- committing or pushing from a branch whose PR is already merged
- committing on a branch that is already merged into the main branch
- committing in detached HEAD
- pushing from protected branches

It also has an explicit escape hatch for one safe case: amending unpushed work.

In plain language, the expected behavior is:

- work on a feature or issue branch
- do not commit directly to `main`
- do not keep adding commits to a branch that is already merged
- if you need to amend a commit that has not been pushed yet, that is allowed

> **Warning:** If the hook blocks a commit or push, the fix is usually to create or switch to the right branch, not to force the action through.

## 8. Review work has its own workflow

This repo includes custom plugins for local review, GitHub PR review, and review-thread handling. In `settings.json`, those plugins are enabled alongside the official review plugins.

### Local review

Use the local review command when you want a three-reviewer pass on your current work:

- `/myk-review:local`
- `/myk-review:local main`
- `/myk-review:local feature/branch`

The command definition says it reviews either:

- uncommitted changes with `git diff HEAD`, or
- changes against a target branch with `git diff "$ARGUMENTS"...HEAD`

That makes it the quickest way to sanity-check work before committing.

### PR review

Use the PR review command when you want to review a GitHub PR and post findings:

- `/myk-github:pr-review`
- `/myk-github:pr-review 123`
- `/myk-github:pr-review https://github.com/owner/repo/pull/123`

Its workflow fetches:

- PR metadata and diff via `myk-claude-tools pr diff`
- the target repository's `CLAUDE.md` via `myk-claude-tools pr claude-md`

Then it sends the result through the same three-reviewer pattern before posting inline comments.

### Review-thread handling

Use the review handler when you are processing existing review comments on a PR:

- `/myk-github:review-handler`
- `/myk-github:review-handler --autorabbit`
- `/myk-github:review-handler <review URL>`

Under the hood, the CLI writes the fetched review state to a temp JSON file in `/tmp/claude`:

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

That review JSON is then used to:

1. present human, Qodo, and CodeRabbit items
2. decide what to address
3. post replies and resolve threads
4. store the completed result for analytics

The stored history goes into a local SQLite database inside the repo:

```python
project_root = get_project_root()

# Get current commit SHA (anchored to repo root for correctness)
commit_sha = get_current_commit_sha(cwd=project_root)

log(f"Storing reviews for {owner}/{repo}#{pr_number} (commit: {commit_sha[:7]})...")

db_path = project_root / ".claude" / "data" / "reviews.db"

log(f"Database: {db_path}")
```

A few practical consequences matter to users:

- AI review sources are handled alongside human comments, not separately.
- Previously dismissed comments can be auto-skipped, but the review-handler workflow still expects them to be surfaced in the decision flow.
- Human skipped or not-addressed threads stay open for follow-up, while AI-source threads are resolved after reply posting.

> **Tip:** If you are working through a large AI review backlog, `/myk-github:review-handler --autorabbit` is the advanced path. It is designed to keep polling for new CodeRabbit comments after each pass.

## 9. Advanced option: `/myk-acpx:prompt`

The `myk-acpx` plugin is the "power user" path for running prompts through external coding agents via `acpx`.

Examples from the command definition include:

- `/myk-acpx:prompt codex fix the tests`
- `/myk-acpx:prompt cursor review this code`
- `/myk-acpx:prompt cursor,codex review this code`
- `/myk-acpx:prompt codex --fix fix the code quality issues`
- `/myk-acpx:prompt gemini --peer review this code`

This is not the default daily flow, but it is useful when you want:

- a second opinion from another coding agent
- a fix-mode pass in an isolated workflow
- a peer-review debate loop

If you use it, the command does its own safety checks before modifying files.

## What "done" looks like

A task is truly complete in this configuration when all of the following are true:

- The request was triaged correctly.
- Issue and branch workflow was used when appropriate.
- Implementation was routed to the right specialist or handled through the right slash command.
- All three reviewers are clear, or their findings were addressed and re-reviewed.
- Tests and local validation passed.
- Git safety hooks are satisfied.
- Any long-running task tracking was cleaned up.
- If GitHub review handling was part of the job, replies were posted and the review data was stored.

That is the core promise of this repository: a Claude session should not just produce changes. It should move work through a predictable, reviewable, and safer daily workflow.
