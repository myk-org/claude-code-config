# Task System Usage

## Scope

> **If you are a SPECIALIST AGENT:**
> IGNORE this rule. This is for the ORCHESTRATOR only.

---

## When to Use the Task System

**USE the task system for:**

- Complex commands with 2+ phases
- Multi-step workflows where user visibility is important
- Operations that benefit from progress tracking
- Slash commands with multiple dependent phases
- Workflows that span multiple user interactions

**DO NOT use tasks for:**

- Simple single-step operations
- Agent work (agents are ephemeral, do not need tracking)
- Quick fixes or trivial operations
- Operations that complete in one action
- Internal agent processing steps

---

## Task Naming Conventions

### Subject (Imperative Form)

Use action-oriented, imperative language for task subjects:

| Good             | Bad                       |
|------------------|---------------------------|
| Run tests        | Running tests             |
| Post comments    | Comments posting          |
| Create release   | Release creation          |
| Update JSON file | JSON file being updated   |

**Keep subjects concise:** 5-10 words maximum.

### ActiveForm (Present Continuous)

The `activeForm` field is displayed in the spinner while the task is in progress:

| Subject                | ActiveForm           |
|------------------------|----------------------|
| Run tests              | Running tests        |
| Post comments          | Posting comments     |
| Create release         | Creating release     |
| Collect user decisions | Collecting decisions |

**Always provide `activeForm`** when creating tasks - this gives users real-time visibility.

---

## Phase Dependency Patterns

### Sequential Phases

Use `blockedBy` to enforce ordering between phases:

```text
Phase 1: Collection
    ↓
Phase 2: Execution (blockedBy: Phase 1)
    ↓
Phase 3: Testing (blockedBy: Phase 2)
    ↓
Phase 4: Post results (blockedBy: Phase 3)
```

### Parallel Execution Within a Phase

Tasks within the same phase can run in parallel if they have no dependencies on each other:

```text
Phase 2 Tasks (all blockedBy: Phase 1):
├── Task: Fix file A (in_progress)
├── Task: Fix file B (in_progress)
└── Task: Fix file C (in_progress)
```

### User Approval Gates

Create blocking tasks for user approval checkpoints:

```text
Phase 3: User approval (blockedBy: Phase 2)
    ↓
Phase 4: Post changes (blockedBy: Phase 3)
```

**Example dependency setup:**

```text
TaskCreate: "Post review replies"
  - blockedBy: [user_approval_task_id]
```

---

## Workflow Example

A typical multi-phase workflow using tasks:

```text
┌─────────────────────────────────────────────┐
│  Phase 1: Collection                        │
│  - TaskCreate: "Collect user decisions"     │
│  - Present items, gather responses          │
│  - Mark completed when done                 │
├─────────────────────────────────────────────┤
│  Phase 2: Execution                         │
│  - Create N tasks (blockedBy: Phase 1)      │
│  - Process in parallel                      │
│  - Mark each completed when done            │
├─────────────────────────────────────────────┤
│  Phase 3: Testing                           │
│  - TaskCreate: "Run tests" (blockedBy: P2)  │
│  - Execute tests                            │
│  - Mark completed when passing              │
├─────────────────────────────────────────────┤
│  Phase 4: Finalization                      │
│  - TaskCreate: "Post results" (blockedBy:P3)│
│  - Execute final actions                    │
│  - Mark completed                           │
├─────────────────────────────────────────────┤
│  Final Cleanup: TaskList + close all        │
└─────────────────────────────────────────────┘
```

---

## Mandatory Cleanup

**CRITICAL: Before completing ANY workflow that uses tasks, you MUST clean up.**

### Cleanup Steps

1. **Run `TaskList`** to see all tasks
2. **Check for incomplete tasks** (status: `pending` or `in_progress`)
3. **Mark all completed work** using `TaskUpdate` with `status: completed`
4. **Verify cleanup** by running `TaskList` again

### Why Cleanup Matters

- Stale tasks accumulate across sessions
- Users see outdated progress indicators
- Task panel becomes cluttered and confusing
- Incomplete tasks may block future workflows

### Example Cleanup

```text
// At end of workflow:
TaskList
→ Shows Task 5 still "in_progress"

TaskUpdate: taskId="5", status="completed"

TaskList
→ All tasks show "completed"
```

---

## Integration with Slash Commands

Slash commands that benefit from task tracking should:

1. **Document task usage** in their implementation notes
2. **Create phase tasks** at workflow start
3. **Use dependencies** to enforce phase ordering
4. **Include cleanup step** as final phase

### Reference Implementation

See `/github-review-handler` for a complete example of task system integration:

- 6 phases with task tracking
- Proper dependency chains
- User approval gates
- Final cleanup step

### Commands That Benefit from Tasks

| Command Type          | Task Usage                       |
|-----------------------|----------------------------------|
| Multi-phase workflows | Create task per phase            |
| User approval gates   | Blocking task for confirmation   |
| Parallel processing   | Multiple tasks at same level     |
| Progress-visible ops  | Task spinner shows status        |

### Commands That Skip Tasks

| Command Type           | Reason              |
|------------------------|---------------------|
| Single-action commands | No tracking benefit |
| Query/read-only cmds   | No phases to track  |
| Simple git operations  | Completes instantly |

---

## Quick Reference

### Task Creation

```text
TaskCreate:
  - subject: "Run tests with coverage"
  - activeForm: "Running tests"
  - description: "Execute test suite and verify coverage thresholds"
```

### Task Dependencies

```text
TaskUpdate:
  - taskId: "2"
  - addBlockedBy: ["1"]
```

### Marking Complete

```text
TaskUpdate:
  - taskId: "1"
  - status: "completed"
```

### Checking Status

```text
TaskList
→ Returns all tasks with status, owner, blockedBy
```

### Get Task Details

```text
TaskGet:
  - taskId: "2"
→ Returns full task details including description and dependencies
```
