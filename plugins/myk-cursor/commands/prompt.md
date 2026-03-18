---
description: Run a prompt via Cursor agent CLI
argument-hint: [--fix | --peer] [--model <model>] <prompt>
allowed-tools: Bash(agent:*), Bash(git:*), Bash(myk-claude-tools:*), Bash(uv:*), AskUserQuestion, Agent, Edit, Write, Read, Glob, Grep
---

# Cursor Agent Prompt Command

Run a prompt through Cursor's agent CLI, enabling access to models like GPT-5.3, Gemini 3 Pro, Grok, and more.

## Usage

- `/myk-cursor:prompt What are best practices for HTML parsing in Python?`
- `/myk-cursor:prompt --model gemini-3-pro Review this codebase for bugs`
- `/myk-cursor:prompt --model gpt-5.3-codex Review the file src/main.py`
- `/myk-cursor:prompt --fix Review and fix the code quality issues`
- `/myk-cursor:prompt --fix --model gemini-3-pro Fix the failing tests`
- `/myk-cursor:prompt --peer review`
- `/myk-cursor:prompt --peer --model gemini-3-pro Review this code`

## Workflow

### Step 1: Prerequisites Check

Verify the Cursor agent CLI is available:

```bash
agent --version
```

If not found, abort with message: "Cursor agent CLI not found at `agent`. Ensure Cursor is installed and the CLI is on your PATH."

### Step 2: Parse Arguments

Parse leading flags from `$ARGUMENTS` before the prompt text:

- Starting at the beginning of `$ARGUMENTS`, consume only these recognized
  flags until you reach the first token that is not a supported flag:
  - `--fix` -- enable fix mode
  - `--peer` -- enable peer review loop (AI-to-AI debate)
  - `--model <model>` -- select a model
- Flags must appear before the prompt text. Once you reach the first
  non-flag token, stop parsing flags and treat the rest as prompt text.
- `--fix` and `--model` may appear in either order before the prompt
  (e.g., `--fix --model gemini-3-pro Fix this`
  or `--model gemini-3-pro --fix Fix this`)
- `--peer` and `--fix` are **mutually exclusive**. If both are passed,
  abort with:
  "`--peer` and `--fix` cannot be used together. `--peer` handles code
  changes autonomously through AI-to-AI debate. Use `--fix` for direct
  Cursor fixes, or `--peer` for iterative peer review."
- If `--peer` appears more than once, abort with:
  "Duplicate --peer flag. Pass --peer at most once."
- After the first non-flag token, treat the rest of `$ARGUMENTS` as the
  prompt verbatim, even if it contains strings like `--fix` or `--model`
- If `--fix` appears more than once, abort with:
  "Duplicate --fix flag. Pass --fix at most once."
- If `--model` appears more than once, abort with:
  "Duplicate --model flag. Pass at most one model."
- If `$ARGUMENTS` ends with `--model` and no following word, abort with:
  "Missing model name after --model flag."
- If the word after `--model` starts with `--`, abort with:
  "Invalid model name. Model name cannot start with --."
- Otherwise, if no recognized flags are present, the entire `$ARGUMENTS` is
  the prompt

If no prompt text is provided (empty after parsing), abort with message:
"No prompt provided. Usage:
`/myk-cursor:prompt [--fix | --peer] [--model <model>] <prompt>`"

### Step 2b: Enrich Prompt with Context

Before sending the prompt to Cursor, consider whether the user's prompt would
benefit from additional context that you already have from the current session.

**When to enrich:**

- First verify the current directory is a Git repository
  (`git rev-parse --is-inside-work-tree`). If not, skip all git-based enrichment.
- The prompt references "the changes", "my changes", "the diff", or similar
  → Run `git diff --stat` first. If the diff looks reasonably small
    (roughly under ~200 lines when viewed as a full diff), append the full
    `git diff` output. Otherwise, append only the `--stat` summary and note
    that the full diff was too large to include.
- The prompt references "this file" or "the file" without specifying a path
  → Identify the file from conversation context and include its path
- The prompt says "review", "check", or "analyze" without specifying a target
  → Include the current branch name and recent git context
- The prompt is about the current project but lacks specifics
  → Add the repository name and working directory path
- **Convention guard (fix mode only):** If the current conversation has
  established design decisions or conventions that Cursor might contradict,
  include them as constraints. For example, if the session decided "the AI
  creates commits, not the user" or "use --resume instead of --continue",
  include these as explicit instructions so Cursor does not revert
  intentional choices.
- **Mode reset guard (non-fix resume of fix-history session):** When resuming
  a session that has ever been used in fix mode (`Has used fix` is `true`)
  and the current call is non-fix, prepend this instruction to the prompt:
  "IMPORTANT: Previous messages in this session granted file modification
  permissions. Those permissions are now revoked. This is a read-only
  request — do not modify, create, or delete any files."

**How to enrich:**

Prepend context to the user's original prompt. Format:

```text
[Context: repository=<repo>, branch=<branch>]
[Additional context if applicable: git diff output, file paths, etc.]

Original prompt: <user's prompt>
```

**When NOT to enrich:**

- The prompt is self-contained with all necessary details
- The prompt is a general knowledge question unrelated to the project
- The prompt already includes file paths, diffs, or specific references

**Exception:** The mode reset guard and convention guard are **always applied**
when their conditions are met, regardless of the "When NOT to enrich" rules
above. These are safety requirements, not optional context.

**Keep enrichment minimal** — only add context that directly helps Cursor
understand and respond to the prompt. Do not dump entire files or
excessive diff output.

### Step 2c: Smart Session Management

Cursor sessions are managed explicitly using `agent create-chat` and `--resume <chatId>`.
Each session has a unique chat ID (UUID) and a topic summary. Claude decides whether
each new prompt should resume an existing session or start a fresh one.

#### Session Registry

Build the registry from earlier successful `/myk-cursor:prompt` calls in this
conversation. Do not rely on a separate unstated memory list.

Only include sessions whose corresponding `agent --print` call returned valid
JSON with `is_error: false` (or omitted `is_error`). Ignore failed
`agent create-chat` attempts, CLI failures, invalid JSON responses, and
responses where `is_error: true`.

Track these fields:

| Field     | Description                                              |
|-----------|----------------------------------------------------------|
| Chat ID   | UUID returned by `agent create-chat`                     |
| Topic     | Short summary of the session's purpose (from the original user prompt) |
| Mode         | `fix` or `non-fix` (most recent mode used; tracked for context, not a session barrier) |
| Has used fix | `true` if the session has ever been used in fix mode; never resets to `false` |
| Last used    | Conversation turn number of the most recent successful use |

#### Decision Logic

**`--peer` mode exception:** When `--peer` is active, ALWAYS create a new
session. Never resume an existing session for `--peer` mode. All rounds
within the peer loop use `--resume` on the session created at the start
of the loop.

For each new `/myk-cursor:prompt` call, decide:

1. **Scan the registry** of all previous successful sessions (regardless of mode)
2. **Evaluate the new prompt's intent** against each existing session's topic
3. **Resume** if the new prompt is clearly a follow-up, continuation, or
   refinement of an existing session's topic — use `--resume <chatId>`.
   This includes same-topic mode switches (e.g., a non-fix review followed
   by `--fix` to apply the suggested changes)
4. **Create new** if the prompt introduces a different topic, task, or
   focus area, or if no matching successful session exists
   — run `agent create-chat` to get a fresh UUID
5. **Tiebreaker** — if multiple sessions match, prefer the most recently used
   session in this conversation

**Resume indicators** (follow-up to existing session):

- Refers to prior output: "what about...", "also check...", "expand on..."
- Same subject matter with deeper dive or different angle
- Asks for clarification or elaboration on prior response
- Continues the same review/analysis from a different aspect
- Same-topic mode switch: e.g., non-fix review → `--fix` to apply the findings

**New session indicators** (different topic):

- Entirely different task: code review → test plan review
- Different files or components under discussion
- Unrelated question or new analysis target

**Note:** A mode switch alone (fix ↔ non-fix) does **not** create a new session
if the topic is the same. Only a topic change triggers a new session.

#### Creating a New Session

```bash
CHAT_ID=$(agent create-chat)
if [ $? -ne 0 ]; then
  # stderr was already emitted by agent create-chat
  echo "Failed to create chat session" >&2
  exit 1
fi
# Validate UUID format
if ! echo "$CHAT_ID" | grep -qE '^[0-9a-f-]{36}$'; then
  echo "agent create-chat returned invalid ID: $CHAT_ID" >&2
  exit 1
fi
```

Keep the new `CHAT_ID` available for the current invocation. Add it to the
session registry only after
Step 4 confirms the response succeeded.

#### Resuming an Existing Session

Use the stored chat ID from a previous successful call:

```bash
agent --print --resume <chatId> --trust --output-format json '<escaped_prompt>'
```

#### Session Info in Output

After each successful call, display the session info to the user:

```text
Session: <chatId> (topic: "<topic summary>")
[New session | Resumed session]
Resume with: agent --resume <chatId>
```

Always show the full chat ID so the user can resume the session directly
via the Cursor CLI if needed (e.g., `agent --resume <chatId> "follow-up prompt"`).

#### Multi-Session Routing Example

```text
Call 1: /myk-cursor:prompt Review this code for bugs
  → agent create-chat → chat-id-A
  → Topic: "code review for bugs", Mode: non-fix
  → agent --print --resume "chat-id-A" --trust ...

Call 2: /myk-cursor:prompt What about the error handling?
  → Matches chat-id-A (follow-up to code review)
  → agent --print --resume "chat-id-A" --trust ...

Call 3: /myk-cursor:prompt --fix Fix the issues you found
  → Matches chat-id-A (same topic, mode switch non-fix → fix)
  → agent --print --resume "chat-id-A" --trust ...

Call 4: /myk-cursor:prompt --fix Fix the failing tests in test_api.py
  → Different topic → agent create-chat → chat-id-B
  → Topic: "fix failing tests", Mode: fix
  → agent --print --resume "chat-id-B" --trust ...

Call 5: /myk-cursor:prompt Also check for SQL injection in the code
  → Matches chat-id-A (back to code review topic)
  → Prepend mode reset guard ("permissions revoked"; read-only)
  → agent --print --resume "chat-id-A" --trust ...
```

### Step 2d: Workspace Safety Check (--fix and --peer modes)

**Skip this step if neither --fix nor --peer was passed.**

Before calling Cursor in fix or peer mode, inspect the workspace state first.

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
     current changes before proceeding, so Cursor's changes are
     cleanly isolated
   - **Continue anyway** — Proceed despite uncommitted changes; the final
     diff summary may include pre-existing edits
   - **Abort** — Stop here to handle changes manually
3. Handle the response as follows:
   - If the user selects **Commit first (Recommended)**, stage all changes
     with `git add -A` and create a checkpoint commit with the message
     `chore: checkpoint before cursor changes`.
     After the commit, verify with `git status --porcelain -z` that the
     output is empty (workspace is clean) before proceeding.
     If the commit fails, or the workspace is still dirty afterward,
     display the raw git output and abort instead of proceeding.
     If the commit succeeds and the workspace is clean, proceed with
     the command and treat it as a clean-worktree run.
   - If the user selects **Continue anyway**, proceed and remember that the
     workspace was already dirty
   - If the user selects **Abort**, stop immediately
4. If the user declines the non-git prompt from step 1, abort.
5. If proceeding despite an already dirty worktree (via **Continue anyway**),
   remember that state so Steps 5-6 (`--fix`) or Step 7f (`--peer`) can warn
   that the final diff may include pre-existing staged or unstaged edits.

### Step 3: Run Prompt

Execute the Cursor agent CLI. Every `agent --print` call in this workflow uses
`--resume <chatId>` and `--trust`:

- For a **new session**, first create a chat with `agent create-chat`, then
  pass the returned `CHAT_ID` to `--resume`
- For an **existing session**, reuse the stored `chatId`

`--trust` is always included so Cursor can access workspace files for reading
and analysis. In fix mode, this also enables file writes.

**New session:**

```bash
# `CHAT_ID` was created and validated in Step 2c.
agent --print --resume "$CHAT_ID" --trust --output-format json '<escaped_prompt>'
agent --print --resume "$CHAT_ID" --trust --output-format json --model <model> '<escaped_prompt>'
```

**Resuming existing session:**

```bash
agent --print --resume <chatId> --trust --output-format json '<escaped_prompt>'
agent --print --resume <chatId> --trust --output-format json --model <model> '<escaped_prompt>'
```

**Additional prompt enrichment for fix mode:**

Append to the user's prompt:

```text
You have full permission to modify, create, and delete files as needed
to fix this. Make all necessary changes directly.
```

Then, if Step 2b identified any convention guards, also append:

```text
Important project conventions to respect:
- <convention 1>
- <convention 2>
Do not revert or contradict these conventions in your changes.
```

**Guard placement:** The mode reset guard and convention guard are always
appended to the end of the prompt (not prepended), so they have the highest
priority in the model's context. Step 2b's context enrichment (repository info,
diffs, etc.) is prepended before the user's prompt text.

Only include conventions that are directly relevant to the files being
reviewed or modified. Do not dump all project conventions — keep it
targeted to what Cursor needs to avoid contradicting.

**Shell safety:** Single-quote the prompt to prevent shell expansion. Replace any single quotes in the prompt with `'\''` before interpolation.

**Timeout:** Set the Bash tool timeout to 300000ms (5 minutes) to prevent the command from hanging indefinitely.

If the command exits with a non-zero code, display the raw output as
an error and stop. Do not continue to Steps 4, 5, or 6 for fix-mode commands.

### Step 4: Parse and Display Result

The JSON output has this structure:

```json
{
  "result": "The actual response text...",
  "is_error": false
}
```

In fix mode, still parse and display the `result` field first. Proceed to
Steps 5 and 6 only if the JSON indicates success.

1. Parse the JSON output
2. Check `is_error` — if `true`, display the error from `result` and abort.
   If `is_error` is missing from the JSON, treat it as `false`.
3. If successful, display the `result` field content to the user
4. Include a note about which model was used (if `--model` was specified) or "default model" otherwise
5. Update that session's `Last used` value to the current conversation turn,
   its `Mode` to the current call's mode (`fix` or `non-fix`), and its
   `Has used fix` value:
   - set `Has used fix` to `true` if the current call used `--fix`
   - otherwise preserve the existing value for resumed sessions, or set it
     to `false` for a brand-new session
6. Display the session info: session ID, topic summary, and whether it was a new or resumed session (see Step 2c)
7. Treat that session as eligible for future reuse in the current conversation

**Error handling:**

- If the Bash tool reports a timeout, report: "Cursor agent timed out. Try a shorter prompt or check Cursor's status with `agent status`."
- If the command exits with a non-zero code, display the raw output as an error.
- If the output is not valid JSON, display the raw output with a note that JSON parsing failed.
- If the JSON is missing the `result` field, display the full JSON response.

### Step 5: Read Diff (--fix mode only)

**Skip this step if --fix was NOT passed, if the fix-mode `agent`
command exited non-zero, or if Step 4 reported an error.**

After Cursor completes successfully in fix mode, inspect what changed.

If the current directory is a Git repository, read the resulting workspace
state:

```bash
git status --short
git diff --stat
git diff
git diff --cached --stat
git diff --cached
```

Use `git status --short` to detect newly created untracked files that
`git diff` won't show.

If either the unstaged diff or staged diff is empty, omit that section from
the report.

If the combined diff output is too large (over ~200 lines), use the
available `--stat` summaries only and note the full diff was too large to
display inline.

If the workspace was already dirty before running `--fix`, explicitly note
that the final diff may include pre-existing staged or unstaged edits in
addition to Cursor's changes.

If the current directory is not a Git repository, report that git diff is
unavailable and summarize Cursor's output instead.

Report to the user:

- Which files were modified/created/deleted
- A summary of the changes
- The unstaged diff and any staged diff (or stat summaries if too large)

### Step 6: Summary (--fix mode only)

**Skip this step if --fix was NOT passed, if the fix-mode `agent`
command exited non-zero, or if Step 4 reported an error.**

Present a clear summary of what Cursor changed:

1. **Files changed** — List each file with what was modified
2. **What was done** — Brief description of the changes in plain language
3. **Impact** — Note any behavioral changes, new dependencies,
   or things the user should verify

If the workspace was already dirty before the run, or the current directory
is not a Git repository, call out that limitation in the summary.

Example format:

```text
Cursor made the following changes:

Files changed (3):
  M src/auth.py — Added input validation to login handler
  M tests/test_auth.py — Added 2 new test cases for validation
  A src/validators.py — New file with email/password validators

Summary: Added input validation to the login handler with email
format and password length checks. Added corresponding tests.

Verify: Run `pytest tests/test_auth.py` to confirm new tests pass.
```

### Step 7: Peer Review Loop (--peer mode only)

**Skip this step if --peer was NOT passed.**

When `--peer` is active, this step replaces the normal Steps 3-6 flow.
The handler orchestrates an autonomous AI-to-AI debate loop between
Claude (the local AI) and Cursor (the remote AI) until both agree on
the code.

#### 7a: Session Setup

The `--peer` session was already created in Step 2c (which always creates
a new session when `--peer` is active). Reuse that `CHAT_ID` here.
All rounds within the loop use `--resume` on that session.

#### 7b: Initial Cursor Review

Send the first prompt to Cursor with peer review framing:

```text
[Context: repository=<repo>, branch=<branch>]
[Git diff or branch context as per Step 2b enrichment rules]

IMPORTANT FRAMING: You are participating in a peer-to-peer AI code
review. The other participant is another AI (Claude). This is NOT a
human interaction. Do NOT be agreeable or sycophantic. Hold your
position when you have valid technical reasoning. Push back when you
disagree. Only concede a point when the other AI provides a genuinely
better technical argument.

Your role: Review the code and report findings. Be direct, specific,
and technically rigorous. For each finding, explain WHY it matters and
provide a concrete fix or suggestion.

Original prompt: <user's prompt>
```

**Execution:** Use the same command contract as Step 3:

```bash
agent --print --resume "$CHAT_ID" --trust --output-format json '<prompt>'
agent --print --resume "$CHAT_ID" --trust --output-format json --model <model> '<prompt>'
```

Set timeout to 300000ms. Parse the JSON response using Step 4's
**error-handling rules only** (steps 1-2: parse JSON, check `is_error`).
Do NOT display intermediate results to the user or update the session
registry — peer rounds are internal. If `is_error` is true or the
command fails, abort the peer loop and report the error to the user.

Parse Cursor's response. If Cursor reports no findings, skip to
Step 7f.

#### 7c: Claude Acts on Findings

For each finding from Cursor:

1. **Evaluate the finding** — Does Claude agree it's a valid issue?
2. **If Claude agrees** — Fix the code by delegating to the
   appropriate specialist agent (follow the normal agent routing
   rules).
3. **If Claude disagrees** — Prepare a technical counter-argument
   explaining WHY the finding is not valid, not applicable, or would
   cause other issues.

**Rules for disagreement:**

- Claude MUST provide specific technical reasoning, not just
  "I disagree"
- Reference the actual code, explain trade-offs, cite patterns or
  conventions
- If the project has established conventions (CLAUDE.md, etc.) that
  support Claude's position, cite them explicitly
- Claude should be open to changing its mind if Cursor makes a good
  point in the next round

#### 7d: Claude Responds to Cursor

After acting on all findings, send a response back to Cursor in the
same session using `--resume`:

```text
PEER REVIEW RESPONSE — Round {N}

IMPORTANT FRAMING: You are in an ongoing peer-to-peer AI code review
with another AI (Claude). This is NOT a human interaction. Do NOT back
down from valid technical positions just to be agreeable. Re-examine
the code with fresh eyes and maintain your position if your original
concern still applies.

Here is what I (Claude) did with your findings:

ADDRESSED:
{For each addressed finding:
  "- Finding: {summary} → Fixed: {what was done}"}

NOT ADDRESSED (with reasoning):
{For each disagreement:
  "- Finding: {summary} → Disagreed: {technical reason}"}

Please re-review the code. Focus on:
1. Verify that addressed findings were fixed correctly
2. Re-evaluate your positions on the disagreements — if my reasoning
   is valid, acknowledge it. If you still disagree, explain why with
   specific technical arguments.
3. Report any NEW issues you find in the updated code.

Original review prompt for context: <user's original prompt>
```

**Execution:** Same command contract — use `--resume`, `--trust`,
`--output-format json`, optional `--model`, 300000ms timeout, and
Step 4 error-handling rules only (no user display, no session registry).
If the command fails, abort the peer loop.

#### 7e: Loop Until Convergence

Parse Cursor's response:

- **No findings and no remaining disagreements** — Both AIs agree.
  Exit loop.
- **New findings or continued disagreements** — Go to Step 7c.

**Convergence criteria:**

- Cursor explicitly states no remaining issues, OR
- Cursor's response contains no actionable findings (only
  acknowledgments)

**Claude's behavior across rounds:**

- Claude SHOULD change its mind when Cursor provides a better argument
- Claude SHOULD NOT stubbornly hold a position just to "win"
- If a disagreement persists for 3+ rounds on the same point, Claude
  should note it as "unresolved disagreement" and move on

**Tracking:** Keep a running log of:

- Round number
- Findings addressed (with file/line)
- Findings disagreed on (with both sides' arguments)
- Findings where Claude changed its mind
- Findings where Cursor conceded

#### 7f: Summary to User

After the loop exits, present a comprehensive summary:

```text
## Peer Review Complete — {N} round(s)

### Findings Addressed ({count})
| # | File | Line | Finding | Fix Applied |
|---|------|------|---------|-------------|
| 1 | src/foo.py | 42 | Missing null check | Added guard clause |
| 2 | src/bar.py | 100 | SQL injection risk | Parameterized query |

### Agreements Reached After Debate ({count})
| # | File | Finding | Rounds | Resolution |
|---|------|---------|--------|------------|
| 1 | src/baz.py | Error swallowing | 2 | Claude conceded, added logging |

### Unresolved Disagreements ({count})
| # | File | Finding | Claude's Position | Cursor's Position |
|---|------|---------|-------------------|-------------------|
| 1 | src/qux.py | Naming convention | Follows project style | Prefers stdlib convention |

### No Changes Needed ({count})
Items where Cursor initially flagged but later agreed no change was
needed.

Session: {chatId}
```

**Summary rules:**

- **Always use tables** — consistent with the review-handler format
- **Show both sides** for unresolved disagreements
- **Include round count** for debated items so the user sees the depth
  of discussion
- **Next steps reminder** — If any code was changed during the peer review,
  end the summary with: "Next steps: Run tests and the standard review
  workflow before committing."
- **Dirty worktree warning** — If the workspace was already dirty before
  the peer review started, note: "Workspace had pre-existing changes;
  resulting diffs may include edits not made during this peer review."
