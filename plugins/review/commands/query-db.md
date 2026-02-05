---
description: Query the reviews database for analytics and insights
argument-hint: [stats|patterns|dismissed|query] [OPTIONS]
allowed-tools: Bash(myk-claude-tools *), Bash(uv *)
---

# Review Database Query Command

Query the reviews database for analytics and insights about PR review history.

## Prerequisites Check (MANDATORY)

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

**reviews table:** id, pr_number, owner, repo, commit_sha, created_at

**comments table:** id, review_id, source, thread_id, node_id, comment_id, author, path, line, body, priority, status, reply, skip_reason, posted_at, resolved_at

## Workflow

1. Parse $ARGUMENTS to determine which query to run
2. Execute the appropriate myk-claude-tools db command
3. Present results in a clear, formatted way
4. For natural language questions, compose the appropriate query
