# GitHub Plugin for Claude Code

GitHub operations including PR reviews, releases, and review handling.

## Prerequisites

Install `myk-claude-tools`:

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
/plugin install github@myk-org
```

## Available Commands

### /github:pr-review

Review a GitHub PR and post inline comments on selected findings.

```bash
/github:pr-review                    # Review PR from current branch
/github:pr-review 123                # Review PR #123
/github:pr-review https://github.com/owner/repo/pull/123
```

### /github:release

Create a GitHub release with automatic changelog generation.

```bash
/github:release              # Normal release
/github:release --dry-run    # Preview without creating
/github:release --prerelease # Create prerelease
/github:release --draft      # Create draft release
```

### /github:review-handler

Process ALL review sources (human, Qodo, CodeRabbit) from current PR.

```bash
/github:review-handler
```

## License

MIT
