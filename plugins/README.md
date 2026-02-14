# Claude Code Plugins

This directory contains Claude Code plugins that can be installed via the plugin marketplace.

## Available Plugins

| Plugin | Description | Commands |
|--------|-------------|----------|
| **[myk-github](./myk-github/README.md)** | GitHub operations | `/myk-github:pr-review`, `/myk-github:release`, `/myk-github:review-handler` |
| **[myk-review](./myk-review/README.md)** | Local review operations | `/myk-review:local`, `/myk-review:query-db` |
| **[myk-qodo](./myk-qodo/README.md)** | Qodo AI code review | `/myk-qodo:review`, `/myk-qodo:describe`, `/myk-qodo:improve`, `/myk-qodo:ask` |
| **[myk-cursor](./myk-cursor/README.md)** | Cursor agent CLI integration | `/myk-cursor:prompt` |

## Installation

### From Marketplace

```bash
# Add this repository as a marketplace
/plugin marketplace add myk-org/claude-code-config

# Install plugins
/plugin install myk-github@myk-org    # GitHub operations
/plugin install myk-review@myk-org    # Local review operations
/plugin install myk-qodo@myk-org      # Qodo AI code review
/plugin install myk-cursor@myk-org    # Cursor agent CLI
```

### Prerequisites for github/review plugins

These plugins require the `myk-claude-tools` CLI:

```bash
uv tool install myk-claude-tools
```

### Local Development

To test plugins during development:

```bash
# Clone the repository
git clone https://github.com/myk-org/claude-code-config.git
cd claude-code-config

# Start Claude with a plugin loaded (example: myk-github)
claude --plugin-dir ./plugins/myk-github

# Test the plugin commands
/myk-github:pr-review
/myk-review:local
/myk-qodo:review
```

## Creating New Plugins

See the [Claude Code Plugins Guide](https://docs.anthropic.com/en/docs/claude-code/plugins) for documentation on creating plugins.

### Plugin Structure

```text
plugins/
└── my-plugin/
    ├── .claude-plugin/
    │   └── plugin.json       # Plugin manifest
    ├── commands/             # Slash command definitions
    │   └── my-command.md
    ├── skills/               # Skill implementations
    │   └── my-skill/
    │       └── SKILL.md
    └── README.md             # Plugin documentation
```

### Adding a Plugin to This Repository

1. Create plugin directory under `plugins/`
2. Add plugin manifest (`.claude-plugin/plugin.json`)
3. Add skills in `skills/` directory
4. Update `.claude-plugin/marketplace.json` at repo root
5. Whitelist files in `.gitignore`
