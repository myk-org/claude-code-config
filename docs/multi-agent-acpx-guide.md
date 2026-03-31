# Multi-Agent ACPX Guide

`myk-acpx` lets Claude Code route a prompt through [acpx](https://github.com/openclaw/acpx) to another coding agent. It is the plugin to use when you want a second opinion from Codex, Cursor, Gemini, Claude, Copilot, or another supported ACP-compatible tool without leaving your current workflow.

It supports four practical patterns:

- A persistent, read-only session with one agent
- A stateless one-shot run with `--exec`
- A writable fix pass with `--fix`
- A multi-round peer review loop with `--peer`

## Quick examples

These examples are taken from the command definition in `plugins/myk-acpx/commands/prompt.md`:

- `/myk-acpx:prompt codex fix the tests`
- `/myk-acpx:prompt cursor review this code`
- `/myk-acpx:prompt gemini explain this function`
- `/myk-acpx:prompt codex --exec summarize this repo`
- `/myk-acpx:prompt codex --model o3-pro review the architecture`
- `/myk-acpx:prompt codex --fix fix the code quality issues`
- `/myk-acpx:prompt gemini --peer review this code`
- `/myk-acpx:prompt codex --peer --model o3-pro review the architecture`
- `/myk-acpx:prompt cursor,codex review this code`
- `/myk-acpx:prompt cursor,gemini,codex --peer review the architecture`

> **Note:** The mode comes from flags, not from the wording in your prompt. `/myk-acpx:prompt codex fix the tests` is still a read-only run unless you add `--fix`.

## Before you start

If `acpx` is not installed, the command checks `acpx --version` and offers to install it with:

```bash
npm install -g acpx@latest
```

> **Note:** `acpx` can download ACP adapters, but it does not replace the underlying agent CLI. If you want to use `codex`, `cursor`, `gemini`, or another agent, that tool still needs to be installed and available on `PATH`.

## Command format

The command definition declares this interface:

```yaml
description: Run a prompt via acpx to any supported coding agent
argument-hint: <agent>[,agent2,...] [--fix | --peer | --exec] [--model <model>] <prompt>
allowed-tools: Bash(acpx:*), Bash(git:*), AskUserQuestion, Agent, Edit, Write, Read, Glob, Grep
```

That means:

- The first token is the agent name, or a comma-separated list of agent names.
- `--exec`, `--fix`, and `--peer` choose the mode.
- `--model <model>` is optional and agent-dependent.
- Everything after the flags becomes the prompt text.

Supported agents currently listed in the command definition:

| Agent | Wraps |
|---|---|
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

## How the workflow runs

`/myk-acpx:prompt` is a slash command, so it runs its own workflow directly instead of handing the whole request off to another agent. The slash-command rules in this repository state:

```markdown
1. **EXECUTE IT DIRECTLY YOURSELF** - NEVER delegate to any agent
2. **ALL internal operations run DIRECTLY** - scripts, bash commands, everything
3. **Slash command prompt takes FULL CONTROL** - its instructions override general CLAUDE.md rules
4. **General delegation rules are SUSPENDED** for the duration of the slash command
```

That direct execution model is what allows this command to manage sessions, inspect Git state, run `acpx`, and orchestrate peer-review rounds on its own.

## Modes at a glance

| Mode | Keeps session state? | Can the external `acpx` agent write files? | Best for |
|---|---|---|---|
| Default session mode | Yes | No | Follow-up conversations and ongoing read-only analysis |
| `--exec` | No | No | One-shot answers and session fallback |
| `--fix` | Yes | Yes | Making changes in one repository |
| `--peer` | Yes | No | Structured review and debate; Claude may still apply fixes between rounds |

## Default session mode

If you do not pass `--exec`, the command tries to keep a session for the current directory. It first runs:

```bash
acpx <agent> sessions ensure
```

If that fails, it tries:

```bash
acpx <agent> sessions new
```

Successful runs stay attached to that working directory, so follow-up prompts can keep using the same agent context.

Non-fix runs are explicitly read-only. The command appends this guard to your prompt:

```text
IMPORTANT: This is a read-only request. Do NOT modify, create, or
delete any files. Report your findings only.
```

> **Note:** If session setup fails with known `acpx` session errors such as `"Invalid params"` or missing session responses, the command falls back to `--exec` for that run and points to upstream issues `acpx#152` and `acpx#161`.

> **Tip:** Use default session mode when you expect follow-up questions. Use `--exec` when you want a clean, disposable run.

## Exec mode

`--exec` skips session setup entirely and runs a stateless command:

```bash
acpx --approve-reads --non-interactive-permissions fail <agent> exec '<prompt>'
acpx --approve-reads --non-interactive-permissions fail <agent> exec --model <model> '<prompt>'
```

Use `--exec` when you want:

- A one-off summary
- A quick read-only review
- A fallback when session management is unreliable for a specific agent

## Fix mode

`--fix` is the writable mode. It runs the selected agent with full approval:

```bash
acpx --approve-all <agent> '<prompt>'
acpx --approve-all <agent> --model <model> '<prompt>'
```

The command also makes the permission explicit in the prompt it sends:

```text
You have full permission to modify, create, and delete files as needed.
Make all necessary changes directly.
```

### Dirty-worktree safeguards

Before `--fix` runs, the command checks whether the current directory is a Git repository and whether the worktree is already dirty.

If the directory is not a Git repository, the command warns that it will not be able to show a Git diff or give you an easy rollback point.

If the directory is a Git repository and `git status --short` shows existing changes, the command asks you to choose one of these options:

1. `Commit first (Recommended)` creates a checkpoint commit with the exact message `chore: checkpoint before acpx changes`.
2. `Continue anyway` keeps going, but the later diff summary may include pre-existing edits.
3. `Abort` stops the run immediately.

This safeguard is there so agent-made changes are easier to isolate and review.

### What happens after the fix

After the agent finishes, the command reads the Git diff using:

```bash
git status --short
git diff --stat
git diff
git diff --cached --stat
git diff --cached
```

If the diff is large, the workflow can fall back to the `--stat` view instead of dumping the entire patch. The final summary is designed to tell you:

- Which files were modified, created, or deleted
- What changed in plain language
- What to run next to verify the result

> **Warning:** `--fix` only works with a single agent. If you pass multiple agents with `--fix`, the command aborts.

## Peer mode

`--peer` is not a one-shot review. It is a multi-round debate loop.

At a high level, the workflow is:

1. The external reviewer inspects the code.
2. Claude evaluates each finding.
3. Valid findings are fixed, and disputed findings get a technical counter-argument.
4. The updated result goes back to the reviewer for another round.
5. The loop continues until the reviewer says there are no actionable issues left.

The command definition is explicit about the convergence rule:

```markdown
Claude orchestrates an AI-to-AI debate loop with the target agent(s) until
all participants agree on the code. When multiple agents are specified,
each agent reviews independently in parallel, and Claude evaluates the
merged findings.

**CRITICAL RULE: Only the peer agent can end the loop.** Claude fixing
code does NOT count as convergence. After EVERY fix round, Claude MUST
send the fixes back to the peer agent (Step 9c) for re-review. The loop
ends ONLY when the peer agent confirms no remaining issues.
```

If the repository contains a `CLAUDE.md`, peer mode tells the reviewer to use it as part of the review standard before it starts judging the code.

One subtle but important point: the external `acpx` reviewer stays read-only, but the overall peer workflow can still change your code because Claude may fix accepted findings between review rounds. That is why the same dirty-worktree safeguard runs before `--peer` as well as before `--fix`.

If a disagreement survives three or more rounds, the workflow records it as an unresolved disagreement and moves on. The final peer summary is designed to show:

- Findings addressed
- Agreements reached after debate
- Unresolved disagreements
- Items where no change was needed

> **Warning:** Peer mode does not end when Claude thinks the code is good. It ends when the reviewer says there are no remaining actionable issues.

## Parallel multi-agent runs

You can pass several agents as a comma-separated list. The command sends the same prompt to each agent in parallel, using the same mode and the same optional `--model` value.

Results are grouped by agent:

```text
## Results from <agent1>:
<agent1 output>

## Results from <agent2>:
<agent2 output>
```

In peer mode, the initial review and later re-review rounds are also sent to all selected agents in parallel. Claude then merges and deduplicates overlapping findings.

Parallel runs are most useful when you want breadth rather than depth:

- Use multi-agent default mode to compare viewpoints on the same code or design.
- Use multi-agent peer mode when you want several reviewers to challenge the code independently.
- Use single-agent session mode when you want follow-up continuity.
- Use single-agent fix mode when you want controlled edits and a clean diff summary.

> **Tip:** Multi-agent runs are best for review, explanation, and comparison. `--fix` is intentionally limited to one agent so changes stay attributable and easier to inspect.

## Guardrails and failure cases

| Situation | What happens |
|---|---|
| No agent name or no prompt text | The command aborts and shows the usage pattern. |
| Unknown agent | The command aborts and lists supported agents. |
| `--fix` with `--peer`, `--fix` with `--exec`, or `--peer` with `--exec` | The command aborts because those modes are mutually exclusive. |
| Duplicate `--fix`, `--peer`, `--exec`, or `--model` | The command aborts with a duplicate-flag error. |
| `--model` with no value, or a model name that starts with `--` | The command aborts. |
| `--fix` with multiple agents | The command aborts. |
| A read-only run tries to write files anyway | The command retries once with stricter read-only wording, then aborts if the agent still tries to write. |
| Session setup fails with known ACP session errors | The command falls back to `--exec` for that invocation. |

> **Note:** When the command builds the raw `acpx` shell command, it single-quotes the prompt and escapes embedded single quotes as `'\''` to avoid shell expansion issues.
