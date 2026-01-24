---
name: ask-review-db
description: Query the reviews database for analytics and insights about PR review history.
skipConfirmation: true
---

# Ask Review Database

**Description:** Query the reviews database for analytics and insights about PR review history.

---

## Instructions

This command provides access to the reviews database for analytics. You can ask questions about review history, patterns, and statistics.

### Available Queries

#### 1. Stats by Source
Show addressed rate by source (human vs AI reviewers).

```bash
uv run ~/.claude/commands/scripts/general/review_db.py stats --by-source --json
```

#### 2. Stats by Reviewer
Show statistics by individual reviewer.

```bash
uv run ~/.claude/commands/scripts/general/review_db.py stats --by-reviewer --json
```

#### 3. Duplicate Patterns
Find recurring dismissed suggestions (things AI keeps suggesting that you keep rejecting).

```bash
uv run ~/.claude/commands/scripts/general/review_db.py patterns --min 2 --json
```

#### 4. Dismissed Comments
Get all dismissed comments for a specific repo.

```bash
uv run ~/.claude/commands/scripts/general/review_db.py dismissed --owner <owner> --repo <repo> --json
```

#### 5. Custom Query
Run a custom SELECT query (SELECT only, for safety). Always include a `LIMIT` to keep output manageable.

```bash
uv run ~/.claude/commands/scripts/general/review_db.py query 'SELECT * FROM comments WHERE status = "skipped" ORDER BY id DESC LIMIT 10' --json
```

### How to Use

1. **User asks a question** about review history (e.g., "Which reviewer gives the most comments?")
2. **Run the appropriate query** from the list above
3. **Present results** in a clear, formatted way
4. **For complex questions**, compose multiple queries or use custom SQL

### Example Questions and Queries

| Question | Query |
|----------|-------|
| "What's Qodo's addressed rate?" | `stats --by-source` |
| "Who gives the most duplicate comments?" | `patterns --min 2` |
| "What did I skip from CodeRabbit?" | `dismissed --owner X --repo Y` + filter |
| "Show recent skipped comments" | `query "SELECT * FROM comments WHERE status='skipped' ORDER BY id DESC LIMIT 10"` |

### Database Schema Reference

**reviews table:**
- id, pr_number, owner, repo, commit_sha, created_at

**comments table:**
- id, review_id, source, thread_id, node_id, comment_id
- author, path, line, body, priority
- status (addressed/not_addressed/skipped), reply, skip_reason
- posted_at, resolved_at

### Natural Language Support

For questions not covered by predefined queries, use the `query` subcommand with custom SQL. Always use SELECT only.

Example: "Show me all HIGH-priority comments that were skipped"

```bash
uv run ~/.claude/commands/scripts/general/review_db.py query 'SELECT path, line, body, reply FROM comments WHERE priority = "HIGH" AND status = "skipped"' --json
```
