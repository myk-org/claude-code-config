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
ln -sf ~/git/claude-code-config/skills ~/.claude/skills
ln -sf ~/git/claude-code-config/settings.json ~/.claude/settings.json
ln -sf ~/git/claude-code-config/statusline.sh ~/.claude/statusline.sh
```

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
cp -r /tmp/claude-code-config/skills ~/.claude/
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
├── skills/                   # Skills
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
    └── commands/             # Private commands
        └── my-workflow.md
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
- **1 skill** for context-aware automation
- **Orchestrator pattern** with automatic agent routing via CLAUDE.md
- **Pre-commit hooks** for rule enforcement
- **Status line** integration
- **SessionStart tool validation** - Checks for required tools (uv, gh, prek, mcpl) and prompts to install missing ones

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

## Skills

Skills are similar to slash commands but auto-invoke based on task context rather than requiring explicit invocation.

| Skill | Description |
|-------|-------------|
| `agent-browser` | Browser automation for web testing, form filling, screenshots, and data extraction |

### agent-browser Installation

See [agent-browser](https://github.com/vercel-labs/agent-browser) for installation instructions.

### `/github-pr-review` Features

- Auto-detect PR from current branch or accept PR number/URL
- Reads project CLAUDE.md for review rules
- Deep code review (security, bugs, error handling, performance)
- User selection - choose which findings to post
- Single review thread with summary table
- Inline comments with severity badges, suggestions, AI prompts

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
├── commands/         # Slash commands
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

## License

MIT
