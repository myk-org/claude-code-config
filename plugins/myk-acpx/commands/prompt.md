---
description: Run a prompt via acpx to any supported coding agent
argument-hint: <agent>[,agent2,...] [--fix | --peer | --exec] [--model <model>] <prompt>
allowed-tools: Bash(acpx:*), Bash(git:*), AskUserQuestion, Agent, Edit, Write, Read, Glob, Grep
---

# acpx Multi-Agent Prompt Command

Run a prompt through [acpx](https://github.com/openclaw/acpx) to any ACP-compatible coding agent.

## Supported Agents

| Agent | Wraps |
|-------|-------|
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

## Usage

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

## Workflow

### Step 1: Prerequisites Check

#### 1a: Check acpx

```bash
acpx --version
```

If not found, ask the user via AskUserQuestion:

"acpx is not installed. It provides structured access to multiple coding agents (Codex, Cursor, Gemini, etc.) via the Agent Client Protocol.

Install it now?"

Options:

- **Yes (Recommended)** — Install globally with `npm install -g acpx@latest`
- **No** — Abort

If user selects Yes, run:

```bash
npm install -g acpx@latest
```

Verify installation:

```bash
acpx --version
```

If installation fails, display the error and abort.

#### 1b: Verify Agent Prerequisite

The underlying coding agent must be installed separately. acpx auto-downloads ACP adapters, but the agent itself (e.g., Codex CLI, Cursor CLI) must be available.

### Step 2: Parse Arguments

Parse `$ARGUMENTS` to extract the agent name and prompt:

1. The **first token** is the agent name (required). Multiple agents can be
   specified as a comma-separated list (e.g., `cursor,codex`). Each name
   must be one of the supported agents listed above.
2. After the agent name, consume optional flags:
   - `--exec` — one-shot mode (no session persistence, stateless)
   - `--fix` — enable fix mode (agent can modify files)
   - `--peer` — enable peer review loop (AI-to-AI debate)
   - `--model <model>` — select a specific model (agent-dependent)
3. Everything after flags is the prompt text.

**Flag validation:**

- If `--exec` appears more than once, abort with: "Duplicate --exec flag."
- If `--model` appears more than once, abort with: "Duplicate --model flag."
- If the input ends with `--model` and no following word, abort with:
  "Missing model name after --model flag."
- If the word after `--model` starts with `--`, abort with:
  "Invalid model name. Model name cannot start with --."
- `--fix` and `--peer` are **mutually exclusive**. If both are passed,
  abort with: "`--fix` and `--peer` cannot be used together."
- `--fix` and `--exec` are **mutually exclusive**. If both are passed,
  abort with: "`--fix` and `--exec` cannot be used together."
- `--peer` and `--exec` are **mutually exclusive**. If both are passed,
  abort with: "`--peer` and `--exec` cannot be used together."
- Multiple agents and `--fix` are **mutually exclusive**. If more than one
  agent is specified with `--fix`, abort with:
  "`--fix` can only be used with a single agent."
- If `--fix` appears more than once, abort with: "Duplicate --fix flag."
- If `--peer` appears more than once, abort with: "Duplicate --peer flag."

If no agent name is provided, abort with:
"No agent specified. Usage: `/myk-acpx:prompt <agent> [--fix | --peer | --exec] [--model <model>] <prompt>`

Supported agents: pi, openclaw, codex, claude, gemini, cursor, copilot, droid, iflow, kilocode, kimi, kiro, opencode, qwen"

If the agent name is not recognized, abort with:
"Unknown agent: `<name>`. Each agent in a comma-separated list
must be recognized. Supported agents: pi, openclaw, codex, claude,
gemini, cursor, copilot, droid, iflow, kilocode, kimi, kiro,
opencode, qwen"

If no prompt is provided after the agent name, abort with:
"No prompt provided. Usage: `/myk-acpx:prompt <agent> [--fix | --peer | --exec] [--model <model>] <prompt>`"

### Step 3: Session Management

**If `--exec` was passed, skip this step** (exec mode is stateless).

Ensure a session exists for the current directory:

**Multi-agent:** Run `sessions ensure` for each agent in the list.

```bash
acpx <agent> sessions ensure
```

If this fails, try creating a new session:

```bash
acpx <agent> sessions new
```

If session creation also fails, check the error output:

- If the error contains "Invalid params" or "session" and "not found", display:

  "acpx session management failed for `<agent>`. This is a known issue — see:
  - <https://github.com/openclaw/acpx/issues/152>
  - <https://github.com/openclaw/acpx/issues/161>

  Falling back to one-shot mode (`--exec`)."

  Then proceed with exec mode for this invocation.

- For any other error, display the error and abort.

### Step 4: Workspace Safety Check (--fix and --peer modes)

**Skip this step if neither --fix nor --peer was passed.**

Before running in fix or peer mode, inspect the workspace state.

```bash
git rev-parse --is-inside-work-tree
git status --short
```

Follow this decision process:

1. If the current directory is not a Git repository, ask the user via
   AskUserQuestion:
   "This directory is not a Git repository. Continue anyway?
   I won't be able to show a git diff or provide an easy rollback point."
2. If the current directory is a Git repository and `git status --short`
   shows any output (modified, staged, or untracked files), ask the user via
   AskUserQuestion with the following options (in this order):
   - **Commit first (Recommended)** — Create a checkpoint commit of the
     current changes before proceeding, so the agent's changes are
     cleanly isolated
   - **Continue anyway** — Proceed despite uncommitted changes; the final
     diff summary may include pre-existing edits
   - **Abort** — Stop here to handle changes manually
3. Handle the response:
   - **Commit first**: Stage all changes with `git add -A` and create a
     checkpoint commit with the message `chore: checkpoint before acpx changes`.
     After the commit, verify with `git status --porcelain -z` that the
     output is empty (workspace is clean) before proceeding. If the commit
     fails or the workspace is still dirty, display the raw output and abort.
   - **Continue anyway**: Proceed and remember the workspace was dirty.
   - **Abort**: Stop immediately.
4. If the user declines the non-git prompt from step 1, abort.
5. If proceeding despite a dirty worktree (via **Continue anyway**),
   remember that state so Steps 7-8 (`--fix`) or Step 9e (`--peer`)
   can warn that diffs may include pre-existing edits.

### Step 5: Run Prompt

**If `--peer` was passed, skip Steps 5-8 and jump to Step 9 (Peer Review Loop).**

Build and execute the acpx command:

**Exec mode (stateless):**

```bash
acpx --approve-reads --non-interactive-permissions fail <agent> exec '<prompt>'
acpx --approve-reads --non-interactive-permissions fail <agent> exec --model <model> '<prompt>'
```

**Fix mode:**

```bash
acpx --approve-all <agent> '<prompt>'
acpx --approve-all <agent> --model <model> '<prompt>'
```

**Read-only prompt guard (non-fix modes):**

When `--fix` is NOT passed, append to the user's prompt:

```text
IMPORTANT: This is a read-only request. Do NOT modify, create, or
delete any files. Report your findings only.
```

In fix mode, append to the user's prompt:

```text
You have full permission to modify, create, and delete files as needed.
Make all necessary changes directly.
```

**Session mode (persistent, default):**

```bash
acpx --approve-reads --non-interactive-permissions fail <agent> '<prompt>'
acpx --approve-reads --non-interactive-permissions fail <agent> --model <model> '<prompt>'
```

**Permissions summary:**

| Mode | Flag | Description |
|------|------|-------------|
| Default | `--approve-reads --non-interactive-permissions fail` | Agent can read files only, writes blocked |
| Fix (`--fix`) | `--approve-all` | Agent can read and write files |
| Peer (`--peer`) | `--approve-reads --non-interactive-permissions fail` | Agent reviews only, writes blocked |

**Multi-agent execution:**

When multiple agents are specified, run all agents **in parallel**:

- Send the same prompt to each agent simultaneously
- Collect results from all agents
- Display results grouped by agent:

```text
## Results from <agent1>:
<agent1 output>

## Results from <agent2>:
<agent2 output>
```

Each agent uses the same mode and flags (exec, session, model).

**Shell safety:** Single-quote the prompt to prevent shell expansion. Replace any single quotes in the prompt with `'\''` before interpolation.

**Error handling:**

If the command exits with a non-zero code:

- If the error indicates a **permission failure** (write denied, permission
  rejected, or similar), this means the agent attempted to modify files
  without `--fix` mode. Retry the prompt once with a stricter instruction
  appended:

  ```text
  CRITICAL: You are NOT allowed to modify any files. Your previous
  attempt was blocked because you tried to write files. This is a
  read-only review. Report findings as text only. Do NOT use any
  file modification tools.
  ```

  If the retry also fails with a permission error, display the error
  and abort.

- For any other error, display the raw output as an error.

### Step 6: Display Result

Display the output from acpx to the user. acpx formats output as a readable stream with tool updates by default.

After successful execution, display:

```text
Agent: <agent>
Mode: [session | fix | exec (one-shot)]
```

If in session mode, also show:

```text
Session active. Send follow-up prompts with: /myk-acpx:prompt <agent> <follow-up>
```

### Step 7: Read Diff (--fix mode only)

**Skip this step if --fix was NOT passed or if the command failed.**

After the agent completes in fix mode, inspect what changed:

```bash
git status --short
git diff --stat
git diff
git diff --cached --stat
git diff --cached
```

If the diff is too large (over ~200 lines), use `--stat` summary only.

If the workspace was already dirty before running, note that the diff
may include pre-existing edits.

Report to the user:

- Which files were modified/created/deleted
- A summary of the changes
- Verify suggestion: what command to run to confirm changes work

### Step 8: Summary (--fix mode only)

**Skip this step if --fix was NOT passed or if the command failed.**

Present a clear summary:

1. **Files changed** — List each file with what was modified
2. **What was done** — Brief description in plain language
3. **Impact** — Behavioral changes, new dependencies, verification steps

### Step 9: Peer Review Loop (--peer mode only)

**Skip this step if --peer was NOT passed.**

Claude orchestrates an AI-to-AI debate loop with the target agent(s) until
all participants agree on the code. When multiple agents are specified,
each agent reviews independently in parallel, and Claude evaluates the
merged findings.

#### 9a: Initial Agent Review

Before sending the peer framing prompt, check if `CLAUDE.md` exists
in the project. If it does, reference it in the framing prompt so the
agent reads it itself.

Send the first prompt to the agent with peer review framing:

```text
IMPORTANT FRAMING: You are participating in a peer-to-peer AI code
review. The other participant is another AI (Claude). This is NOT a
human interaction. Do NOT be agreeable or sycophantic. Hold your
position when you have valid technical reasoning. Push back when you
disagree. Only concede a point when the other AI provides a genuinely
better technical argument.

[If CLAUDE.md exists in the project:]
IMPORTANT: This project has a CLAUDE.md file with coding conventions
and project guidelines. Read it before reviewing. Flag any violations
of those conventions as findings.

Your role: Review the code and report findings. Be direct, specific,
and technically rigorous. For each finding, explain WHY it matters and
provide a concrete fix or suggestion.

Original prompt: <user's prompt>
```

Execute via acpx:

```bash
acpx --approve-reads --non-interactive-permissions fail <agent> '<peer_framing_prompt>'
acpx --approve-reads --non-interactive-permissions fail <agent> --model <model> '<peer_framing_prompt>'
```

Do NOT display intermediate results to the user.
If the command fails, abort the peer loop and report the error.

**Multi-agent:** Send the peer framing prompt to ALL agents in parallel.
Collect and merge findings from all agents, deduplicating where the same
issue is raised by multiple agents.

If the agent reports no findings, skip to Step 9e.

#### 9b: Claude Acts on Findings

For each finding from the agent:

1. **Evaluate the finding** — Does Claude agree it's a valid issue?
2. **If Claude agrees** — Fix the code by delegating to the
   appropriate specialist agent (follow the normal agent routing rules).
3. **If Claude disagrees** — Prepare a technical counter-argument
   explaining WHY the finding is not valid, not applicable, or would
   cause other issues.

**Rules for disagreement:**

- Claude MUST provide specific technical reasoning, not just "I disagree"
- Reference the actual code, explain trade-offs, cite patterns or conventions
- If the project has established conventions (CLAUDE.md, etc.) that
  support Claude's position, cite them explicitly
- Claude should be open to changing its mind if the agent makes a good
  point in the next round

#### 9c: Claude Responds to Agent

After acting on all findings, send a response back to the agent:

```text
PEER REVIEW RESPONSE — Round {N}

IMPORTANT FRAMING: You are in an ongoing peer-to-peer AI code review
with another AI (Claude). This is NOT a human interaction. Do NOT back
down from valid technical positions just to be agreeable.

Here is what I (Claude) did with your findings:

ADDRESSED:
{For each addressed finding:
  "- Finding: {summary} → Fixed: {what was done}"}

NOT ADDRESSED (with reasoning):
{For each disagreement:
  "- Finding: {summary} → Disagreed: {technical reason}"}

Please re-review the code. Focus on:
1. Verify that addressed findings were fixed correctly
2. Re-evaluate your positions on the disagreements
3. Report any NEW issues you find in the updated code.
```

Execute via acpx (same command pattern). Do NOT display intermediate results.

**Multi-agent:** Send the response to ALL agents in parallel. Each agent
re-reviews independently.

#### 9d: Loop Until Convergence

Parse the agent's response:

- **No findings and no remaining disagreements** — All AIs agree. Exit loop.
- **New findings or continued disagreements** — Go to Step 9b.

**Convergence criteria:**

- All agents explicitly state no remaining issues, OR
- All agents' responses contain no actionable findings (only acknowledgments)

**Claude's behavior across rounds:**

- Claude SHOULD change its mind when the agent provides a better argument
- Claude SHOULD NOT stubbornly hold a position just to "win"
- If a disagreement persists for 3+ rounds on the same point, note it as
  "unresolved disagreement" and move on

#### 9e: Summary to User

After the loop exits, present a comprehensive summary:

```text
## Peer Review Complete — {N} round(s)

Agent(s): <agent>[, <agent2>, ...]

### Findings Addressed ({count})

| # | File | Line | Finding | Fix Applied |
|---|------|------|---------|-------------|
| 1 | src/foo.py | 42 | Missing null check | Added guard clause |

### Agreements Reached After Debate ({count})

| # | File | Finding | Rounds | Resolution |
|---|------|---------|--------|------------|
| 1 | src/baz.py | Error swallowing | 2 | Claude conceded, added logging |

### Unresolved Disagreements ({count})

| # | File | Finding | Claude's Position | Agent(s) Position |
|---|------|---------|-------------------|------------------|
| 1 | src/qux.py | Naming convention | Follows project style | Prefers stdlib convention |

### No Changes Needed ({count})

Items where the agent initially flagged but later agreed no change was needed.
```

**Summary rules:**

- **Always use tables** — consistent format
- **Show both sides** for unresolved disagreements
- **Include round count** for debated items
- **Next steps reminder** — If any code was changed, end with:
  "Next steps: Run tests and the standard review workflow before committing."
- **Dirty worktree warning** — If the workspace was already dirty before
  the peer review, note: "Workspace had pre-existing changes; resulting
  diffs may include edits not made during this peer review."
