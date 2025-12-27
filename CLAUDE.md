# Claude Code Configuration Repository

This repository contains a pre-configured Claude Code setup with an orchestrator pattern, specialized agents, and workflow automation.

## Project Purpose

This is a **configuration repository** for Claude Code that implements:
- Orchestrator pattern (main conversation delegates to specialist agents)
- Tool permission controls and hooks
- Custom slash commands
- MCP server integrations

## Repository Structure

```
claude-code-config/
├── agents/          - Specialist agent definitions (python-expert, git-expert, etc.)
├── commands/        - Custom slash commands (like /commit, /review-pr)
├── rules/           - Orchestrator rules (auto-loaded by Claude Code)
├── scripts/         - Helper scripts for hooks and automation
├── servers/         - MCP server configurations
├── settings.json    - Hooks and tool permissions configuration
├── .claude/         - Runtime state and cache (gitignored)
└── README.md        - Installation and usage documentation
```

### Key Directories

**`agents/`** - Agent definition files in Markdown format
- Each agent has a specialized role (language expert, infrastructure, etc.)
- Follow existing naming: `{domain}-{role}.md` (e.g., `python-expert.md`)
- Structure: Role description, expertise areas, approach, examples

**`commands/`** - Custom slash command definitions
- Each command is a Markdown file with prompts and workflows
- Can invoke agents internally as specified in their prompts

**`rules/`** - Orchestrator rules (auto-loaded by Claude Code)
- Contains modular orchestrator rules that auto-load into conversations
- Files are numbered (00-, 10-, etc.) for load order control
- Each file focuses on one concern (routing, code review, slash commands, etc.)
- These rules control main conversation behavior (delegation, forbidden tools, etc.)

**`scripts/`** - Python/Shell scripts for automation
- Used by hooks in `settings.json`
- Tool permission validation
- Workflow automation

**`servers/`** - MCP server configurations
- Integration with external tools and APIs
- GitHub metrics, webhook logs, OpenShift, etc.

**`settings.json`** - Central configuration file
- Tool hooks (before/after tool execution)
- Permission controls
- Agent routing rules

## Development Guidelines

### Adding New Agents

1. Create file in `agents/` following this structure:
   ```markdown
   # Agent Name

   Role description (1-2 sentences)

   ## Core Expertise
   - Bullet list of skills

   ## Approach
   How this agent works

   ## Examples (optional)
   ```

2. Add routing rule to orchestrator in `rules/10-agent-routing.md`

3. Test with real Claude Code conversations

### Modifying Configuration

- **settings.json**: Test hook changes carefully - they run on every tool call
- **commands/**: Keep slash command prompts focused and self-contained
- **scripts/**: Ensure scripts have proper error handling and exit codes

### Testing Changes

1. Install this config to ~/.claude (see README.md)
2. Run Claude Code in a test project
3. Verify agents are invoked correctly
4. Check hooks execute without errors

## Important Notes

- **Orchestrator rules**: The main orchestrator rules (agent delegation, forbidden tools, etc.) are defined in the `rules/` directory, which auto-loads into every conversation
- **This file**: Provides project-specific context about the claude-code-config repository itself
- **Rules organization**: Keep orchestrator rules modular in `rules/`, each file addressing one concern

## Related Documentation

- [README.md](/home/myakove/git/claude-code-config/README.md) - Installation and setup
- [settings.json](/home/myakove/git/claude-code-config/settings.json) - Hooks and permissions
- Individual agent files in `agents/` for agent-specific documentation
