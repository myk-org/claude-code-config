# Review Plugin for Claude Code

Local code review operations and review database queries.

## Prerequisites

For database commands, install `myk-claude-tools`:

```bash
uv tool install myk-claude-tools
```

Or from this repository:

```bash
uv tool install git+https://github.com/myk-org/claude-code-config
```

## Installation

```bash
/plugin marketplace add myk-org/claude-code-config
/plugin install review@myk-org
```

## Available Commands

### /review:local

Review uncommitted changes or changes compared to a branch.

```bash
/review:local              # Review uncommitted changes
/review:local main         # Compare against main branch
/review:local feature/xyz  # Compare against specific branch
```

### /review:query-db

Query the reviews database for analytics and insights.

```bash
/review:query-db                           # Show available queries
/review:query-db stats --by-source         # Stats by source
/review:query-db stats --by-reviewer       # Stats by reviewer
/review:query-db patterns --min 2          # Find duplicate patterns
/review:query-db dismissed --owner X --repo Y
```

## License

MIT
