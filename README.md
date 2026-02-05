# Claude Code Config

Pre-configured Claude Code setup with specialized agents and workflow automation.

## Requirements

- **Claude Code v2.1.19 or higher** - This configuration uses v2.1.19 features (see below)
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager (used for running hook scripts)

### Claude Code v2.1.19 Features Used

This configuration leverages these features:

- **Agent-scoped hooks** - Hooks defined in agent frontmatter (e.g., `PreToolUse` in git-expert) (v2.1.0)
- **`allowed-tools`** - Tool restrictions in agent frontmatter (e.g., code-reviewer is read-only) (v2.1.0)
- **`additionalContext` in PreToolUse** - Provides guidance when blocking commands (v2.1.9)
- **Task management system** - Built-in task tracking with `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet` for complex workflows (v2.1.16)
- **Slash command argument syntax** - Bracket syntax `$ARGUMENTS[0]` and shorthand `$0`, `$1` for positional arguments (v2.1.19)

> Note: `context: fork` was evaluated but not used due to compatibility issues with multi-phase workflows.

## Quick Start (Plugins)

The easiest way to use this repository's features is via plugins:

### 1. Add the marketplace

```bash
/plugin marketplace add myk-org/claude-code-config
```

### 2. Install plugins

```bash
# GitHub operations (PR reviews, releases, review handling)
/plugin install myk-github@myk-org

# Local code review and database queries
/plugin install myk-review@myk-org

# Qodo AI code review integration
/plugin install myk-qodo@myk-org
```

### 3. Install CLI (for github and review plugins)

```bash
uv tool install myk-claude-tools
```

Or from this repository:

```bash
uv tool install git+https://github.com/myk-org/claude-code-config
```

### Available Plugin Commands

| Plugin | Command | Description |
|--------|---------|-------------|
| myk-github | `/myk-github:pr-review` | Review PR and post inline comments |
| myk-github | `/myk-github:release` | Create release with changelog |
| myk-github | `/myk-github:review-handler` | Process all review sources |
| myk-review | `/myk-review:local` | Review uncommitted changes |
| myk-review | `/myk-review:query-db` | Query review database |
| myk-qodo | `/myk-qodo:review` | AI-powered code review |
| myk-qodo | `/myk-qodo:describe` | Generate PR descriptions |
| myk-qodo | `/myk-qodo:improve` | Get improvement suggestions |
| myk-qodo | `/myk-qodo:ask` | Ask questions about code |

> **For full orchestrator pattern with agents and hooks**, see [Full Installation](#installation) below.

## Installation

Clone to any location and symlink into `~/.claude`:

```bash
# Clone to ~/git/ (or your preferred location)
git clone https://github.com/myk-org/claude-code-config ~/git/claude-code-config

# Create ~/.claude if it doesn't exist
mkdir -p ~/.claude

# Symlink each component
ln -sf ~/git/claude-code-config/agents ~/.claude/agents
ln -sf ~/git/claude-code-config/rules ~/.claude/rules
ln -sf ~/git/claude-code-config/scripts ~/.claude/scripts
ln -sf ~/git/claude-code-config/skills ~/.claude/skills
ln -sf ~/git/claude-code-config/settings.json ~/.claude/settings.json
ln -sf ~/git/claude-code-config/statusline.sh ~/.claude/statusline.sh
```

**Updating:**

```bash
cd ~/git/claude-code-config && git pull
```

Your symlinks will automatically point to the updated files.

## What's Included

- **3 plugins** with 9 commands (myk-github, myk-review, myk-qodo)
- **CLI tool** (`myk-claude-tools`) for plugin operations
- **19 specialized agents** for different domains (Python, Go, Java, Docker, Kubernetes, Git, etc.)
- **1 skill** for context-aware automation
- **Orchestrator pattern** with automatic agent routing via CLAUDE.md
- **Pre-commit hooks** for rule enforcement
- **Status line** integration
- **SessionStart tool validation** - Checks for required tools (uv, gh, prek, mcpl) and prompts to install missing ones

## Agents

| Agent | Purpose |
| ----- | ------- |
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

When specialist agents work with external libraries or frameworks, they can automatically fetch the latest
documentation through the `docs-fetcher` agent. This ensures that code follows current best practices and
uses up-to-date APIs.

**Key features:**

- Prioritizes `llms.txt` files (LLM-optimized documentation)
- Falls back to official documentation sites
- Caches results for faster subsequent access
- Provides context-relevant excerpts to specialist agents

**Example workflow:**

```text
python-expert working with FastAPI
         ↓
    docs-fetcher fetches FastAPI docs
         ↓
python-expert uses current best practices
```

## Skills

Skills are similar to slash commands but auto-invoke based on task context rather than requiring explicit invocation.

| Skill           | Description                                                                        |
| --------------- | ---------------------------------------------------------------------------------- |
| `agent-browser` | Browser automation for web testing, form filling, screenshots, and data extraction |

### agent-browser Installation

See [agent-browser](https://github.com/vercel-labs/agent-browser) for installation instructions.

## MCP Server Access

This configuration uses [mcp-launchpad](https://github.com/kenneth-liao/mcp-launchpad) (`mcpl`) for on-demand MCP server access.

**Benefits over native MCP loading:**

- Tools are NOT loaded into context at session start
- No 30% context consumption from tool definitions
- Agents discover and call tools on-demand via CLI

**Installation:**

```bash
uv tool install https://github.com/kenneth-liao/mcp-launchpad.git
```

See `rules/15-mcp-launchpad.md` for detailed usage instructions and command reference.

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

```text
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
       Done
```

### Benefits

- **Reduced token usage** - Specialist context is discarded after task completion
- **Better code quality** - Domain experts produce better code
- **Faster execution** - Parallel agents vs sequential operations
- **Maintainability** - Easy to add/modify agents for new domains

## Orchestrator Pattern Details

The `CLAUDE.md` file defines an orchestrator pattern where:

1. The main Claude instance acts as a **manager/orchestrator**
2. It delegates tasks to **specialist agents** based on the domain
3. After code changes, automatic **code review** and **test** loops run

## Customization

- **Edit `CLAUDE.md`** to customize orchestrator rules and agent routing
- **Edit `.claude/settings.json`** to modify hooks and allowed tools
- **Edit agents in `.claude/agents/`** to customize agent behavior

## File Structure

```text
~/.claude/
├── agents/           # Specialist agent definitions
├── plugins/          # Plugin definitions (myk-github, myk-review, myk-qodo)
├── skills/           # Skills (auto-invoked based on context)
│   └── agent-browser/
│       └── SKILL.md
├── rules/            # Orchestrator rules (auto-loaded)
├── scripts/          # Helper scripts for hooks
│   ├── git-protection.py         # Protects main branch, merged branches
│   ├── my-notifier.sh            # Custom notifications
│   ├── reply-to-pr-review.sh     # Reply to PR reviews
│   ├── rule-enforcer.py          # Blocks orchestrator from using Edit/Write/Bash
│   ├── rule-injector.py          # Auto-loads rules from rules/
│   └── session-start-check.sh    # Validates required tools at session start
├── tests/            # Unit tests for Python scripts
├── settings.json     # Hooks and tool permissions
├── statusline.sh     # Status line script
├── tox.toml          # Test configuration
├── pyproject.toml    # Python project config (ruff, mypy)
└── .pre-commit-config.yaml  # Pre-commit hooks
```

## Development

### Running Tests

Tests are run via tox with uv:

```bash
# Run all tests
uvx --with tox-uv tox

# Run specific Python version
uvx --with tox-uv tox -e py313

# Pass pytest arguments
uvx --with tox-uv tox -- -v --tb=short
```

### Pre-commit

This project uses pre-commit hooks for code quality:

```bash
# Install pre-commit hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

## Plugins

This repository provides plugins for Claude Code with specialized workflows.

### Available Plugins

| Plugin | Description | Commands |
|--------|-------------|----------|
| **myk-github** | GitHub operations | `/myk-github:pr-review`, `/myk-github:release`, `/myk-github:review-handler` |
| **myk-review** | Local review operations | `/myk-review:local`, `/myk-review:query-db` |
| **myk-qodo** | Qodo AI code review | `/myk-qodo:review`, `/myk-qodo:describe`, `/myk-qodo:improve`, `/myk-qodo:ask` |

### Plugin Installation

```bash
# Add this repository as a marketplace
/plugin marketplace add myk-org/claude-code-config

# Install plugins
/plugin install myk-github@myk-org
/plugin install myk-review@myk-org
/plugin install myk-qodo@myk-org
```

### Prerequisites for github/review plugins

These plugins use the `myk-claude-tools` CLI:

```bash
uv tool install myk-claude-tools
```

Or install from this repository:

```bash
uv tool install git+https://github.com/myk-org/claude-code-config
```

See [plugins/README.md](./plugins/README.md) for detailed plugin documentation.

## License

MIT
