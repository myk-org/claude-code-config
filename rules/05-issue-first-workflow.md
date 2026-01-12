# Issue-First Workflow

## Scope

> **If you are a SPECIALIST AGENT:**
> IGNORE this rule. This is for the ORCHESTRATOR only.

---

## When This Workflow Applies

**USE this workflow for:**
- New features or enhancements
- Bug fixes that require code changes
- Refactoring tasks
- Any request that will modify multiple files
- Tasks that benefit from tracking and documentation

**SKIP this workflow for:**
- Trivial fixes (typos, single-line changes)
- Questions or explanations (no code changes)
- Exploration or research tasks
- When user explicitly says "just do it" or "quick fix"
- Urgent hotfixes where user indicates time pressure

---

## Workflow

```text
User Request
     ↓
Analyze and understand the request
     ↓
Is this trivial? ──YES──→ Do it directly (skip workflow)
     │
    NO
     ↓
Delegate to github-expert to create issue with:
  - Type (fix/feat/refactor/docs)
  - Problem/feature description
  - Requirements
  - Deliverables checklist
     ↓
Ask: "Issue #N created. Do you want to work on it now?"
     ↓
     │
  ┌──┴──┐
 YES    NO
  │      │
  ↓      └──→ Done (user triggers later)
Fetch main & create issue branch
     ↓
Work on the issue
  - Check off items as completed
  - Follow code review loop
     ↓
All items done → Close issue
```

---

## Branch Workflow

When user confirms they want to work on the issue, **delegate to git-expert**:

1. **Fetch main**: `git fetch origin main`
2. **Create issue branch**: `git checkout -b <type>/issue-<number>-<short-description> origin/main`

**Branch naming:**
- `feat/issue-70-issue-first-workflow`
- `fix/issue-42-memory-leak`
- `refactor/issue-99-cleanup-utils`
- `docs/issue-15-update-readme`

---

## Issue Format

The `github-expert` agent handles issue formatting. When delegating issue creation, provide:
- Type (fix/feat/refactor/docs)
- Problem/feature description
- Requirements list
- Deliverables checklist

The agent will format the title and body according to its template.

---

## Tracking Progress

**As you work on the issue:**

1. **Check off deliverables** - Update the issue to mark completed items
2. **Follow code review loop** - All code changes go through `code-reviewer`
3. **Update issue with progress** - Add comments if significant updates occur

**When all deliverables are complete:**

1. Verify all checklist items are checked
2. Ensure code review passed
3. Ensure tests pass (if applicable)
4. Close the issue with a summary comment

---

## Integration with Code Review Loop

The issue-first workflow integrates with the existing code review loop:

```text
Issue created & branch ready
          ↓
    ┌─────────────────────────────────┐
    │     CODE REVIEW LOOP            │
    │  (from 20-code-review-loop.md)  │
    │                                 │
    │  Write code → Review → Fix     │
    │       ↓                         │
    │  Tests pass?                    │
    │       ↓                         │
    │     YES                         │
    └─────────────────────────────────┘
          ↓
Check off deliverable in issue
          ↓
More deliverables? ──YES──→ Next item (loop)
          │
         NO
          ↓
Close issue
```

---

## Asking User to Work on Issue

After creating the issue, always ask:

> **Issue #N created: [title]**
>
> URL: [issue URL]
>
> Do you want to work on it now?

Wait for explicit confirmation before:
- Creating the branch
- Starting any implementation work

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| User says "just fix it" | Skip workflow, do directly |
| User provides partial requirements | Ask clarifying questions, then create issue |
| Issue already exists | Ask if user wants to continue existing issue |
| Urgent/hotfix request | Skip workflow, note in commit message |
| Multiple unrelated requests | Create separate issues for each |
