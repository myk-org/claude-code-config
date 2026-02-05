---
description: Query the reviews database for analytics and insights
argument-hint: [stats|patterns|dismissed|query] [OPTIONS]
allowed-tools: Bash(myk-claude-tools *), Bash(uv *)
---

# Review Database Query Command

Query the reviews database for analytics and insights about PR review history.

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

If not found, prompt to install: `uv tool install myk-claude-tools`

## Usage

```bash
/review:query-db stats --by-source        # Stats by source
/review:query-db stats --by-reviewer      # Stats by reviewer
/review:query-db patterns --min 2         # Find duplicate patterns
/review:query-db dismissed --owner X --repo Y
/review:query-db query "SELECT * FROM comments WHERE status='skipped' LIMIT 10"
```

## Available Queries

### Stats by Source

Show addressed rate by source (human vs AI reviewers):

```bash
myk-claude-tools db stats --by-source
```

### Stats by Reviewer

Show statistics by individual reviewer:

```bash
myk-claude-tools db stats --by-reviewer
```

### Duplicate Patterns

Find recurring dismissed suggestions:

```bash
myk-claude-tools db patterns --min 2
```

### Dismissed Comments

Get all dismissed comments for a specific repo:

```bash
myk-claude-tools db dismissed --owner <owner> --repo <repo>
```

### Custom Query

Run a custom SELECT query:

```bash
myk-claude-tools db query "SELECT * FROM comments WHERE status = 'skipped' ORDER BY id DESC LIMIT 10"
```

## Database Schema

**reviews table:**

| Column | Type |
|--------|------|
| id | INTEGER PRIMARY KEY |
| pr_number | INTEGER |
| owner | TEXT |
| repo | TEXT |
| commit_sha | TEXT |
| created_at | TEXT (ISO 8601) |

**comments table:**

| Column | Type |
|--------|------|
| id | INTEGER PRIMARY KEY |
| review_id | INTEGER (FK -> reviews.id) |
| source | TEXT (human/qodo/coderabbit) |
| thread_id | TEXT |
| node_id | TEXT |
| comment_id | INTEGER |
| author | TEXT |
| path | TEXT |
| line | INTEGER |
| body | TEXT |
| priority | TEXT (HIGH/MEDIUM/LOW) |
| status | TEXT (pending/addressed/skipped/not_addressed) |
| reply | TEXT |
| skip_reason | TEXT |
| posted_at | TEXT (ISO 8601) |
| resolved_at | TEXT (ISO 8601) |

## Database Location and Constraints

The reviews database is located at `<project-root>/.claude/data/reviews.db`.

**Query Constraints:**

- Only SELECT statements and CTEs (Common Table Expressions) are allowed
- INSERT, UPDATE, DELETE, DROP, and other modifying statements are blocked
- This ensures the database remains read-only for analytics queries

## Workflow

1. Parse $ARGUMENTS to determine which query to run
2. Execute the appropriate myk-claude-tools db command
3. Present results in a clear, formatted way
4. For natural language questions, compose the appropriate query
