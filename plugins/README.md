# Claude Code Plugins

This directory contains Claude Code plugins that can be installed via the plugin marketplace.

## Available Plugins

| Plugin | Description | Skills |
|--------|-------------|--------|
| [qodo](./qodo/) | Qodo AI code review integration | `/qodo:review`, `/qodo:describe`, `/qodo:improve`, `/qodo:ask` |

## Installation

### From Marketplace

```bash
# Add this repository as a marketplace
/plugin marketplace add myk-org/claude-code-config

# Install a plugin
/plugin install qodo@myk-org
```

### Local Development

```bash
# Test a plugin during development
claude --plugin-dir ./plugins/qodo
```

## Creating New Plugins

See the [Claude Code Plugins Guide](https://docs.anthropic.com/en/docs/claude-code/plugins) for documentation on creating plugins.

### Plugin Structure

```text
plugins/
└── my-plugin/
    ├── .claude-plugin/
    │   └── plugin.json       # Plugin manifest
    ├── skills/               # Skill definitions
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
