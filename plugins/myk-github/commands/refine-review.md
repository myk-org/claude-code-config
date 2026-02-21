---
description: Refine pending PR review comments with AI before submitting
argument-hint: <PR_URL>
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), AskUserQuestion
---

# Refine Pending Review Command

Refines the user's pending GitHub PR review comments using AI before submitting. The user starts a review on GitHub, adds comments, then calls this command to polish and submit.

## Prerequisites Check (MANDATORY)

### Step 0: Check uv

```bash
uv --version
```

If not found, install from <https://docs.astral.sh/uv/getting-started/installation/>

### Step 1: Check myk-claude-tools

```bash
myk-claude-tools --version
```

If not found, prompt user: "myk-claude-tools is required. Install with: `uv tool install myk-claude-tools`. Install now?"

## Usage

- `/myk-github:refine-review https://github.com/owner/repo/pull/123`

## Workflow

### Phase 1: Fetch Pending Review

Parse `$ARGUMENTS` as the PR URL. If empty, abort with: "PR URL required. Usage: `/myk-github:refine-review https://github.com/owner/repo/pull/123`"

```bash
myk-claude-tools reviews pending-fetch <PR_URL>
```

This returns JSON with:

- `metadata`: owner, repo, pr_number, review_id, username, json_path
- `comments`: array of pending review comments with id, path, line, body, diff_hunk
- `diff`: PR diff text for context

If the command fails (exit code 1), display the error and abort.

Save the `json_path` from metadata for later phases.

### Phase 2: Refine Comments

For each comment in the JSON, use the PR diff context, file path, line number, and diff hunk to generate a refined version.

**Refinement goals:**

- Improve clarity and conciseness
- Make comments more actionable (suggest specific fixes when possible)
- Fix grammar and formatting
- Add code suggestions in markdown code blocks where appropriate
- Preserve the original intent and technical accuracy
- Keep the tone professional and constructive

### Phase 3: Present Side-by-Side

Display each comment with its refinement, numbered for reference. If a comment has no line number (file-level comment), show only the path:

```text
Comment #1 (path/to/file.py:42):
  Original: <user's original comment>
  Refined:  <AI-refined version>

Comment #2 (src/main.py):
  Original: <file-level comment>
  Refined:  <AI-refined version>
```

### Phase 4: User Approval

Ask the user which refinements to accept using AskUserQuestion:

Options:

- **Accept all** - Use all refined versions
- **Pick specific** - Enter comment numbers to accept (e.g., "1,3,5")
- **Keep originals** - Skip refinement, go straight to submit step
- **Cancel** - Abort without making any changes

If "Pick specific": ask user to enter comma-separated numbers. Validate that numbers are within range (1 to N). Ignore duplicates. Re-prompt on invalid input.

### Phase 5: Update JSON

Update the JSON file at `json_path`:

- For each accepted refinement: set `refined_body` to the refined text and `status` to `"accepted"`
- For comments kept as original: leave `refined_body` as null and `status` as `"pending"`

### Phase 6: Submit Decision

Ask the user what review action to take using AskUserQuestion:

Options:

- **Comment** - Submit as general feedback
- **Approve** - Approve the PR
- **Request changes** - Request changes
- **Don't submit yet** - Keep the review pending

If user chooses to submit, optionally ask for a review summary (can be empty).

Update the JSON metadata:

- Set `submit_action` to the chosen action (COMMENT/APPROVE/REQUEST_CHANGES), or omit if keeping pending
- Set `submit_summary` to the summary text

### Phase 7: Execute Updates

```bash
myk-claude-tools reviews pending-update <json_path>
```

This updates accepted comment bodies on GitHub and optionally submits the review.

If the command fails, display the error. If it reports a 404, inform the user their pending review may have been submitted or deleted externally.

### Phase 8: Summary

Display:

- Number of comments refined vs kept as original
- Review action taken (submitted as COMMENT/APPROVE/REQUEST_CHANGES, or kept pending)
- PR URL for reference

---

**CRITICAL RULES:**

- NEVER update comments or submit the review without explicit user confirmation
- Always show what will change before changing it
- The user controls which refinements are accepted
- If an API call fails with 404/422, the pending review may have been externally submitted or deleted - inform the user
