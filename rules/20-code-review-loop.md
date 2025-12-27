# Code Review Loop (MANDATORY)

After ANY code change, follow this loop:

```
┌─────────────────────────────────────────────┐
│  1. Specialist writes/fixes code            │
│              ↓                              │
│  2. Send to `code-reviewer`                 │
│              ↓                              │
│  3. Has comments? ──YES──→ Fix code (go to 2)
│              │                              │
│             NO                              │
│              ↓                              │
│  4. Run `test-automator`                    │
│              ↓                              │
│  5. Tests pass? ──NO──→ Fix code (go to 2)  │
│              │                              │
│             YES                             │
│              ↓                              │
│  ✅ DONE                                    │
└─────────────────────────────────────────────┘
```

## Key Rules

**Never skip code review. Loop until approved.**

The process is iterative:
1. Code is written or modified by a specialist
2. Code reviewer provides feedback
3. If there are comments, fix the code and repeat from step 2
4. Once approved, run tests
5. If tests fail, fix the code and repeat from step 2
6. Only complete when code is reviewed AND tests pass
