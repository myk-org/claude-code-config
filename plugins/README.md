# Claude Code Plugins

This directory contains Claude Code plugins that can be installed via the plugin marketplace.

## Available Plugins

- **[qodo](./qodo/README.md)** - Qodo AI code review integration

## Installation

### From Marketplace

```bash
# Add this repository as a marketplace
/plugin marketplace add myk-org/claude-code-config

# Install a plugin
/plugin install qodo@myk-org
```

### Local Development

To test plugins during development:

```bash
# Clone the repository
git clone https://github.com/myk-org/claude-code-config.git
cd claude-code-config

# Start Claude with the plugin loaded
claude --plugin-dir ./plugins/qodo

# Test the plugin commands
/qodo:review
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
