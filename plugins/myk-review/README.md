# myk-review Plugin for Claude Code

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
/plugin install myk-review@myk-org
```

## Available Commands

### /myk-review:local

Review uncommitted changes or changes compared to a branch.

```bash
/myk-review:local              # Review uncommitted changes
/myk-review:local main         # Compare against main branch
/myk-review:local feature/xyz  # Compare against specific branch
```

### /myk-review:query-db

Query the reviews database for analytics and insights.

```bash
/myk-review:query-db                           # Show available queries
/myk-review:query-db stats --by-source         # Stats by source
/myk-review:query-db stats --by-reviewer       # Stats by reviewer
/myk-review:query-db patterns --min 2          # Find duplicate patterns
/myk-review:query-db dismissed --owner X --repo Y
```

## License

MIT
