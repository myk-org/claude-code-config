# myk-github Plugin for Claude Code

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
/plugin install myk-github@myk-org
```

## Available Commands

### /myk-github:pr-review

Review a GitHub PR and post inline comments on selected findings.

```bash
/myk-github:pr-review                    # Review PR from current branch
/myk-github:pr-review 123                # Review PR #123
/myk-github:pr-review https://github.com/owner/repo/pull/123
```

### /myk-github:release

Create a GitHub release with automatic changelog generation.

```bash
/myk-github:release              # Normal release
/myk-github:release --dry-run    # Preview without creating
/myk-github:release --prerelease # Create prerelease
/myk-github:release --draft      # Create draft release
```

### /myk-github:review-handler

Process ALL review sources (human, Qodo, CodeRabbit) from current PR.

```bash
/myk-github:review-handler
```

## License

MIT
