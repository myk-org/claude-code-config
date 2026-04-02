# Claude Code Plugins

This directory contains Claude Code plugins that can be installed via the plugin marketplace.

## Available Plugins

| Plugin | Description | Commands |
|--------|-------------|----------|
| **[myk-github](./myk-github/README.md)** | GitHub operations | `/myk-github:coderabbit-rate-limit`, `/myk-github:pr-review`, `/myk-github:refine-review`, `/myk-github:release`, `/myk-github:review-handler` |
| **[myk-review](./myk-review/README.md)** | Local review operations | `/myk-review:local`, `/myk-review:query-db` |
| **[myk-acpx](./myk-acpx/README.md)** | Run prompts to any ACP-compatible coding agent via acpx | `/myk-acpx:prompt` |

## Installation

### From Marketplace

```bash
# Add this repository as a marketplace
/plugin marketplace add myk-org/claude-code-config

# Install plugins
/plugin install myk-github@myk-org    # GitHub operations
/plugin install myk-review@myk-org    # Local review operations
/plugin install myk-acpx@myk-org      # Multi-agent ACP (via acpx)
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

### Command Frontmatter Rules

**CRITICAL: Command `.md` files must NEVER include a `name` field in the YAML frontmatter.**

The command name is derived from the filename automatically. Adding a `name:` field breaks command registration and the command will not appear in plugin listings.

**Correct frontmatter:**

```yaml
---
description: What this command does
argument-hint: [ARGS]
allowed-tools: Bash(tool:*), AskUserQuestion
---
```

**Wrong frontmatter (DO NOT USE):**

```yaml
---
name: my-command        # ← NEVER add this field
description: What this command does
argument-hint: [ARGS]
allowed-tools: Bash(tool:*), AskUserQuestion
---
```

### Bug Reporting Policy

**Bug Reporting Policy:** Every command MUST include a bug reporting blockquote after the `#` heading.
See `CLAUDE.md` "Bug Reporting Policy for Plugins" for the template.

### Adding a Plugin to This Repository

1. Create plugin directory under `plugins/`
2. Add plugin manifest (`.claude-plugin/plugin.json`)
3. Add skills in `skills/` directory
4. Update `.claude-plugin/marketplace.json` at repo root
5. Whitelist files in `.gitignore`
