# Claude Code Config

Pre-configured Claude Code setup with specialized agents, plugins, and workflow automation.

**[Full Documentation](https://myk-org.github.io/claude-code-config/)**

## Quick Start

```text
/plugin marketplace add myk-org/claude-code-config
/plugin install myk-github@myk-org
/plugin install myk-review@myk-org
/plugin install myk-acpx@myk-org
```

## CLI

Some plugins require the `myk-claude-tools` CLI:

```bash
uv tool install myk-claude-tools
```

```text
/myk-github:pr-review         # Review PR and post inline comments
/myk-github:release           # Create release with changelog
/myk-review:local             # Review uncommitted changes
```

See the [full documentation](https://myk-org.github.io/claude-code-config/) for agents, orchestrator pattern, installation, configuration, and more.

## License

MIT
