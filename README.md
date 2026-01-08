# Claude Code Config

Pre-configured Claude Code setup with specialized agents and workflow automation.

## Requirements

- **Claude Code v2.1.0 or higher** - This configuration uses v2.1.0 features (agent-scoped hooks, `allowed-tools` in frontmatter)
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager (used for running hook scripts)

### Claude Code v2.1.0 Features Used

This configuration leverages these v2.1.0 features:

- **Agent-scoped hooks** - Hooks defined in agent frontmatter (e.g., `PreToolUse` in git-expert)
- **`allowed-tools`** - Tool restrictions in agent frontmatter (e.g., code-reviewer is read-only)

> Note: `context: fork` was evaluated but not used due to compatibility issues with multi-phase workflows.

## Installation

### Option 1: Clone directly to ~/.claude

> **⚠️ If `~/.claude` already exists**, back it up first! See [backup instructions](#backup-existing-config) below.

```bash
git clone https://github.com/myk-org/claude-code-config ~/.claude
```

**See also:**
- [Backup Existing Config](#backup-existing-config) - If you have an existing ~/.claude
- [GNU Stow Integration](#integration-with-dotfiles-gnu-stow) - For dotfiles users

### Option 2: Clone as a regular git repo

Clone to any location (e.g., `~/git/`), then set up ~/.claude using one of these methods:

```bash
git clone https://github.com/myk-org/claude-code-config ~/git/claude-code-config
```

**Then choose how to use it:**
- [Symlink Approach](#symlink-approach) - Symlink components to ~/.claude
- [Copy Approach](#copy-approach) - Copy files to ~/.claude

---

#### Backup Existing Config

If you have an existing `~/.claude` directory:

```bash
# Backup existing config
mv ~/.claude ~/.claude.backup

# Clone the repo
git clone https://github.com/myk-org/claude-code-config ~/.claude

# Copy your private files back (examples - adjust to your setup)
# Private agents:
cp ~/.claude.backup/agents/my-private-agent.md ~/.claude/agents/
# MCP server configs (if you had them):
mkdir -p ~/.claude/code-execution-configs/
cp -r ~/.claude.backup/code-execution-configs/* ~/.claude/code-execution-configs/
# Any other private files you have...

# Remove backup after verifying everything works
rm -rf ~/.claude.backup
```

#### Symlink Approach

Clone to a different location and symlink into your existing `~/.claude`:

```bash
# Clone to ~/git/ (or your preferred location)
git clone https://github.com/myk-org/claude-code-config ~/git/claude-code-config

# Create ~/.claude if it doesn't exist
mkdir -p ~/.claude

# Symlink each component
ln -sf ~/git/claude-code-config/agents ~/.claude/agents
ln -sf ~/git/claude-code-config/commands ~/.claude/commands
ln -sf ~/git/claude-code-config/rules ~/.claude/rules
ln -sf ~/git/claude-code-config/scripts ~/.claude/scripts
ln -sf ~/git/claude-code-config/servers ~/.claude/servers
ln -sf ~/git/claude-code-config/settings.json ~/.claude/settings.json
ln -sf ~/git/claude-code-config/statusline.sh ~/.claude/statusline.sh
```

**Note:** To use the code execution server with MCP server configs, create your own `~/.claude/code-execution-configs/` directory for your private config files (not part of this repo).

#### Copy Approach

Clone to a different location and copy files to your existing `~/.claude`:

```bash
# Clone to a temp location
git clone https://github.com/myk-org/claude-code-config /tmp/claude-code-config

# Copy to ~/.claude (won't overwrite existing files)
cp -rn /tmp/claude-code-config/* ~/.claude/

# Or force overwrite (careful with private configs!)
# cp -r /tmp/claude-code-config/* ~/.claude/

# Clean up
rm -rf /tmp/claude-code-config
```

**Updating with this approach:**
```bash
git clone https://github.com/myk-org/claude-code-config /tmp/claude-code-config
cp -r /tmp/claude-code-config/agents ~/.claude/
cp -r /tmp/claude-code-config/commands ~/.claude/
cp -r /tmp/claude-code-config/rules ~/.claude/
cp -r /tmp/claude-code-config/scripts ~/.claude/
# ... selectively copy what you need
rm -rf /tmp/claude-code-config
```

## Integration with Dotfiles (GNU Stow)

If you manage your dotfiles with GNU Stow, use this **clone + overlay** approach.

### How It Works

```
Step 1: git clone this repo directly to ~/.claude (base config)
Step 2: stow your dotfiles (private .claude files overlay on top)
```

### Directory Structure

**This repo (cloned directly to ~/.claude):**
```
~/.claude/                    ← git clone destination
├── agents/                   # Public agents (from this repo)
├── commands/                 # Commands
├── scripts/                  # Public scripts
├── servers/                  # Server configs
├── settings.json             # Base settings
└── statusline.sh
```

**Your dotfiles (private overlay via stow):**
```
dotfiles/
├── .zshrc
├── .config/
└── .claude/                  # Only YOUR private additions
    ├── agents/               # Private agents
    │   ├── my-private-agent.md
    │   └── company-specific-agent.md
    ├── scripts/              # Private scripts
    │   └── my-helper.sh
    ├── commands/             # Private commands
    │   └── my-workflow.md
    └── code-execution-configs/  # Your MCP server configs
        ├── my-server.json
        └── company-internal-service.json
```

### Setup

> **Note:** If `~/.claude` already exists, see [Option 1](#option-1-clone-directly-to-claude) for backup instructions before cloning.

```bash
# 1. Clone this repo to ~/.claude
git clone https://github.com/myk-org/claude-code-config ~/.claude

# 2. Stow your dotfiles (overlays private files)
cd ~/dotfiles && stow -t ~ .
```

### Updating

```bash
# Update base config:
cd ~/.claude && git pull

# Your private files from dotfiles remain untouched
```

## What's Included

- **19 specialized agents** for different domains (Python, Go, Java, Docker, Kubernetes, Git, etc.)
- **4 slash commands** including PR review workflows
- **Orchestrator pattern** with automatic agent routing via CLAUDE.md
- **Pre-commit hooks** for rule enforcement
- **MCP server integrations** (code execution)
- **Status line** integration

## Agents

| Agent | Purpose |
|-------|---------|
| `python-expert` | Python development, testing, async patterns |
| `go-expert` | Go development, goroutines, modules |
| `java-expert` | Java/Spring Boot development |
| `frontend-expert` | JS/TS/React/Vue/Angular |
| `bash-expert` | Shell scripting and automation |
| `docker-expert` | Dockerfile, container orchestration |
| `kubernetes-expert` | K8s/OpenShift, Helm, GitOps |
| `jenkins-expert` | CI/CD pipelines, Jenkinsfiles |
| `git-expert` | Git operations, branching strategies |
| `github-expert` | GitHub platform operations (PRs, issues, releases) |
| `test-automator` | Test suites, CI pipelines |
| `test-runner` | Test execution and reporting |
| `debugger` | Error analysis, debugging |
| `code-reviewer` | Code quality, security review |
| `codebase-refactor-analyst` | Refactoring analysis and planning |
| `technical-documentation-writer` | Documentation |
| `api-documenter` | OpenAPI/Swagger specs |
| `docs-fetcher` | Fetches external library/framework documentation, prioritizes llms.txt |
| `general-purpose` | Fallback for unspecified tasks |

### Automatic Documentation Fetching

When specialist agents work with external libraries or frameworks, they can automatically fetch the latest documentation through the `docs-fetcher` agent. This ensures that code follows current best practices and uses up-to-date APIs.

**Key features:**
- Prioritizes `llms.txt` files (LLM-optimized documentation)
- Falls back to official documentation sites
- Caches results for faster subsequent access
- Provides context-relevant excerpts to specialist agents

**Example workflow:**
```
python-expert working with FastAPI
         ↓
    docs-fetcher fetches FastAPI docs
         ↓
python-expert uses current best practices
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/github-pr-review` | Review a GitHub PR and post inline comments. Posts as single review with summary. |
| `/github-review-handler` | Process human reviewer comments from a PR. |
| `/github-coderabbitai-review-handler` | Process CodeRabbit AI review comments. |
| `/code-review` | Run code review on local changes. |

### `/github-pr-review` Features

- Auto-detect PR from current branch or accept PR number/URL
- Reads project CLAUDE.md for review rules
- Deep code review (security, bugs, error handling, performance)
- User selection - choose which findings to post
- Single review thread with summary table
- Inline comments with severity badges, suggestions, AI prompts

## MCP Servers

The `.claude/servers/` directory contains MCP (Model Context Protocol) server implementations.

### Available MCP Servers

1. **Code Execution Server** - UTCP-based code execution layer for tool chaining

### Code Execution Server

Located at `.claude/servers/code-execution/`, this server wraps MCP connections through a **code execution layer** using UTCP.

**Why not connect MCP servers directly?**

| Approach | API Calls | Flexibility | Performance |
|----------|-----------|-------------|-------------|
| **Direct MCP** | 1 call per tool | Single tool per request | Many round-trips |
| **Code Execution** | 1 call for entire workflow | Chain tools with TypeScript | Single round-trip |

**Key advantages:**

1. **Tool Chaining in One Call**
   ```typescript
   // Direct MCP: 3 separate API calls
   // Code Execution: 1 call with this code:
   const repos = await github.listRepos();
   const metrics = await Promise.all(
     repos.map(r => github.getMetrics(r.id))
   );
   return summarize(metrics);
   ```

2. **Custom Logic Between Tools**
   - Conditional branching based on results
   - Loops and iterations
   - Data transformation and filtering
   - Error handling and retries

3. **Reduced Token Usage**
   - One tool call instead of many
   - Results aggregated before returning
   - No intermediate results in conversation

4. **Better Performance**
   - Single round-trip to API
   - Parallel execution with Promise.all
   - No waiting for Claude to process each step

**Setup:**
```bash
cd ~/.claude/servers/code-execution
npm install
```

### Adding Server Configs

1. Create your private configs directory and config file:

```bash
# Create your private configs directory (not part of this repo)
mkdir -p ~/.claude/code-execution-configs/

# Create a config file for your MCP server
cat > ~/.claude/code-execution-configs/my-service.json << 'EOF'
{
  "manual_call_templates": [
    {
      "name": "my-service",
      "call_template_type": "mcp",
      "config": {
        "mcpServers": {
          "my-server": {
            "transport": "http",
            "url": "http://localhost:8080/mcp"
          }
        }
      }
    }
  ],
  "tool_repository": {
    "tool_repository_type": "in_memory"
  },
  "tool_search_strategy": {
    "tool_search_strategy_type": "tag_and_description_word_match"
  }
}
EOF
```

2. Add the MCP server to Claude by editing `~/.claude.json`:

```json
{
  "mcpServers": {
    "my-service": {
      "command": "npx",
      "args": ["@utcp/code-mode-mcp"],
      "env": {
        "UTCP_CONFIG_FILE": "~/.claude/code-execution-configs/my-service.json"
      }
    }
  }
}
```

3. Restart Claude Code for the changes to take effect.

**Note:** The `code-execution-configs/` directory is for your private MCP server configurations and is NOT part of this repository. Create it yourself in `~/.claude/` and add your own config files there.

### Creating an Agent for Your MCP Server

After adding an MCP server, you'll want a specialized agent to manage it. Ask Claude to create one:

**Example prompt:**
```
Create an agent for my new MCP server called "my-service" that handles [describe what your server does].
The agent should be saved to ~/.claude/agents/my-service-manager.md
```

**Agent file structure:**
```markdown
---
name: my-service-manager
description: Use this agent for [your MCP server purpose]
---

You are a specialist agent for managing the my-service MCP server...

## Available Tools
- mcp__my-service__tool_name
- ...
```

The agent will be automatically available in Claude Code after creation.

## Why Agent-Based Workflow?

This configuration implements an **orchestrator pattern** where Claude acts as a manager delegating to specialist agents. Here's why:

### Context Preservation
- **Main conversation stays lean** - The orchestrator only tracks high-level progress
- **Specialists work in isolation** - Each agent handles its task without bloating the main context
- **Parallel execution** - Multiple agents can work simultaneously on independent tasks

### Expertise Separation
- **Domain knowledge** - Each agent has specialized instructions for its domain (Python best practices, Git workflows, Docker patterns)
- **Tool restrictions** - Agents only use tools relevant to their specialty
- **Consistent patterns** - Same agent = same coding style and conventions

### Quality Assurance
- **Mandatory code review** - Every code change goes through `code-reviewer`
- **Automated testing** - `test-automator` runs after changes
- **Review loop** - Changes iterate until approved

### Workflow Example

```
User: "Add a new feature to handle user auth"
         │
         ▼
   ┌─────────────────┐
   │  ORCHESTRATOR   │  (main Claude - manages, doesn't code)
   └────────┬────────┘
            │
   ┌────────┼────────────────┐
   │        │                │
   ▼        ▼                ▼
┌──────┐ ┌──────┐      ┌──────────┐
│python│ │ git  │      │test-auto │
│expert│ │expert│      │  mator   │
└──────┘ └──────┘      └──────────┘
   │        │                │
   └────────┴────────────────┘
            │
            ▼
    ┌──────────────┐
    │code-reviewer │
    └──────────────┘
            │
            ▼
       ✅ Done
```

### Benefits
- **Reduced token usage** - Specialist context is discarded after task completion
- **Better code quality** - Domain experts produce better code
- **Faster execution** - Parallel agents vs sequential operations
- **Maintainability** - Easy to add/modify agents for new domains

## How It Works

The `CLAUDE.md` file defines an orchestrator pattern where:

1. The main Claude instance acts as a **manager/orchestrator**
2. It delegates tasks to **specialist agents** based on the domain
3. After code changes, automatic **code review** and **test** loops run

## Customization

- **Edit `CLAUDE.md`** to customize orchestrator rules and agent routing
- **Edit `.claude/settings.json`** to modify hooks and allowed tools
- **Edit agents in `.claude/agents/`** to customize agent behavior

## File Structure

```
~/.claude/
├── agents/           # Specialist agent definitions
├── scripts/          # Helper scripts for hooks
├── settings.json     # Hooks and tool permissions
└── statusline.sh     # Status line script
```

## License

MIT
