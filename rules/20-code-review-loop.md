# Code Review Loop (MANDATORY)

After ANY code change, follow this loop:

```text
┌──────────────────────────────────────────────────────────────┐
│  1. Specialist writes/fixes code                            │
│              ↓                                              │
│  2. Send to ALL 3 review agents IN PARALLEL:                │
│     - `superpowers:code-reviewer`                           │
│     - `pr-review-toolkit:code-reviewer`                     │
│     - `feature-dev:code-reviewer`                           │
│              ↓                                              │
│  3. Merge findings from all 3 reviewers                     │
│              ↓                                              │
│  4. Has comments? ──YES──→ Fix code (go to 2)               │
│              │                                              │
│             NO                                              │
│              ↓                                              │
│  5. Run `test-automator`                                    │
│              ↓                                              │
│  6. Tests pass? ──NO──→ Fix code (go to 2)                  │
│              │                                              │
│             YES                                             │
│              ↓                                              │
│  ✅ DONE                                                    │
└──────────────────────────────────────────────────────────────┘
```

## Review Agents

Three plugin agents review code in parallel for comprehensive coverage:

| Agent | Focus |
|---|---|
| `superpowers:code-reviewer` | General code quality and maintainability |
| `pr-review-toolkit:code-reviewer` | Project guidelines and style adherence (CLAUDE.md) |
| `feature-dev:code-reviewer` | Bugs, logic errors, and security vulnerabilities |

**All 3 MUST be called in a single message using parallel Task tool calls.**

## Key Rules

**Never skip code review. Loop until all reviewers approve.**

The process is iterative:

1. Code is written or modified by a specialist
2. All 3 review agents run in parallel
3. Merge and deduplicate findings from all reviewers
4. If there are comments, fix the code and repeat from step 2
5. Once approved, run tests
6. If tests fail, fix the code and repeat from step 2
7. Only complete when all reviewers approve AND tests pass
