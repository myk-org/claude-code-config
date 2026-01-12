# Claude Code Configuration Repository

> **Context:** This is the configuration repository for Claude Code's orchestrator pattern.
>
> When working on this repo, you're **modifying the configuration** that controls how Claude Code operates across all projects.

---

## Purpose

This repository implements an **orchestrator pattern** for Claude Code where:

1. **Main Claude = Orchestrator** - Manages workflow, delegates tasks
2. **Specialist Agents** - Domain experts that execute work
3. **Rule Enforcement** - Hooks ensure proper delegation
4. **Auto-loading Rules** - Rules from `rules/` directory are automatically injected

The goal is to preserve context, improve code quality, and enable parallel execution by routing tasks to specialized agents.

---

## Repository Structure

```
claude-code-config/
├── agents/                    # Specialist agent definitions + shared rules
│   ├── 00-base-rules.md       # Shared rules for ALL agents
│   ├── api-documenter.md      # OpenAPI/Swagger specs
│   ├── bash-expert.md         # Shell scripting
│   ├── code-reviewer.md       # Code quality/security review
│   ├── codebase-refactor-analyst.md  # Refactoring analysis
│   ├── debugger.md            # Error analysis
│   ├── docker-expert.md       # Container orchestration
│   ├── docs-fetcher.md        # External docs (prioritizes llms.txt)
│   ├── frontend-expert.md     # JS/TS/React/Vue/Angular
│   ├── general-purpose.md     # Fallback agent
│   ├── git-expert.md          # Git operations
│   ├── github-expert.md       # GitHub platform operations
│   ├── go-expert.md           # Go development
│   ├── java-expert.md         # Java/Spring development
│   ├── jenkins-expert.md      # CI/CD pipelines
│   ├── kubernetes-expert.md   # K8s/OpenShift/Helm
│   ├── python-expert.md       # Python development
│   ├── technical-documentation-writer.md  # Documentation
│   ├── test-automator.md      # Test suites, CI pipelines
│   └── test-runner.md         # Test execution
│
├── commands/                  # Custom slash commands
│   ├── code-review.md         # Local code review
│   ├── github-coderabbitai-review-handler.md  # AI review processor
│   ├── github-pr-review.md    # PR review with inline comments
│   ├── github-release.md      # GitHub release automation
│   ├── github-review-handler.md  # Human review processor
│   └── scripts/               # Helper scripts for commands
│       ├── general/
│       │   └── get-pr-info.sh
│       ├── github-coderabbitai-review-handler/
│       │   └── get-coderabbit-comments.sh
│       ├── github-pr-review/
│       │   ├── get-claude-md.sh
│       │   ├── get-pr-diff.sh
│       │   └── post-pr-inline-comment.sh
│       ├── github-release/
│       │   ├── create-github-release.sh
│       │   └── get-release-info.sh
│       └── github-review-handler/
│           └── get-human-reviews.sh
│
├── rules/                     # Orchestrator rules (AUTO-LOADED)
│   ├── 00-orchestrator-core.md      # Core delegation rules
│   ├── 05-issue-first-workflow.md   # Issue-first workflow for requests
│   ├── 10-agent-routing.md          # Agent selection logic
│   ├── 15-mcp-server-access.md      # MCP server access via mcp-cli
│   ├── 20-code-review-loop.md       # Mandatory review workflow
│   ├── 30-slash-commands.md         # Slash command execution
│   ├── 40-critical-rules.md         # Parallel execution, temp files
│   └── 50-agent-bug-reporting.md    # Bug reporting for agent issues
│
├── scripts/                   # Hook scripts (Python/Bash)
│   ├── git-protection.py      # Protects main branch, merged branches
│   ├── inject-claude.sh       # Injects Claude config
│   ├── my-notifier.sh         # Custom notifications
│   ├── post-compact-restore.py   # Restores state after compaction
│   ├── pre-compact-snapshot.py   # Saves state before compaction
│   ├── reply-to-pr-review.sh  # Reply to PR reviews
│   ├── rule-enforcer.py       # Blocks orchestrator from using Edit/Write/Bash
│   └── rule-injector.py       # Auto-loads rules from rules/
│
├── tests/                     # Unit tests for Python scripts
│   ├── test_git_protection.py
│   ├── test_post_compact_restore.py
│   ├── test_pre_compact_snapshot.py
│   └── test_rule_enforcer.py
│
├── settings.json              # Hooks, tool permissions, status line
├── statusline.sh              # Custom status bar script
├── tox.toml                   # Test configuration
├── pyproject.toml             # Python project config (ruff, mypy)
├── .pre-commit-config.yaml    # Pre-commit hooks
├── .flake8                    # Flake8 configuration
├── README.md                  # Installation and usage guide
└── CLAUDE.md                  # This file - project context (NOT tracked)
```

---

## Key Concepts

### 1. Auto-Loading Rules

**Rules in `rules/` are automatically injected into every conversation.**

- Files are loaded in alphabetical order (hence `00-`, `10-`, etc.)
- Orchestrator receives these rules on every prompt via `rule-injector.py` hook
- Edit rules in `rules/` to change orchestrator behavior globally

### 2. Orchestrator vs Specialist

**Orchestrator (Main Claude):**
- CANNOT use: Edit, Write, NotebookEdit, Bash (except allowed commands)
- CAN: Read, route to agents, execute slash commands directly

**Specialist Agents:**
- IGNORE orchestrator rules
- Use Edit/Write/Bash freely within their domain
- Work in isolated context (discarded after task)

### 3. Enforcement Hooks

**`rule-enforcer.py` blocks violations:**
- Triggers on `PreToolUse` for Edit/Write/Bash
- Checks if caller is orchestrator or agent
- Rejects orchestrator violations with error message

### 4. Slash Commands

**Special execution rules:**
- Slash commands execute DIRECTLY in orchestrator (not delegated)
- ALL internal operations run in orchestrator context
- Slash command prompt overrides general CLAUDE.md rules
- Example: `/github-pr-review` runs scripts, posts comments directly

### 5. MCP Server Access

**MCP servers are accessed via [`mcp-cli`](https://github.com/philschmid/mcp-cli).**

- Orchestrator uses `mcp-cli` for discovery (list servers, explore tools)
- Agents execute MCP tools directly via `mcp-cli`
- See `rules/15-mcp-server-access.md` for full command reference

---

## Key Agents

### Language Specialists
- **python-expert** - Python development, async, testing
- **go-expert** - Go development, goroutines, modules
- **java-expert** - Java/Spring Boot development
- **frontend-expert** - JS/TS/React/Vue/Angular

### Infrastructure
- **docker-expert** - Dockerfiles, container orchestration
- **kubernetes-expert** - K8s/OpenShift, Helm, GitOps
- **jenkins-expert** - CI/CD pipelines, Jenkinsfiles
- **bash-expert** - Shell scripting automation

### Development Workflow
- **git-expert** - Git operations, branching strategies
- **code-reviewer** - Code quality, security review (MANDATORY after changes)
- **test-automator** - Test suite creation, CI pipelines
- **test-runner** - Test execution and reporting
- **debugger** - Error analysis and debugging

### Documentation
- **docs-fetcher** - Fetches external library/framework docs (prioritizes llms.txt)
- **technical-documentation-writer** - User-focused documentation
- **api-documenter** - OpenAPI/Swagger specifications

### Analysis
- **codebase-refactor-analyst** - Refactoring analysis and planning

### Fallback
- **general-purpose** - Handles tasks without specific specialist

---

## Development Guidelines

### Adding a New Agent

1. **Create agent file** in `agents/`:
   ```bash
   touch agents/my-new-expert.md
   ```

2. **Define agent structure**:
   ```markdown
   ---
   name: my-new-expert
   description: Brief description of when to use this agent
   ---

   You are a specialist in [domain]...

   ## Core Expertise
   - Expertise area 1
   - Expertise area 2

   ## Approach
   1. Step one
   2. Step two
   ```

3. **Add routing rule** in `rules/10-agent-routing.md`:
   ```markdown
   | My Domain | my-new-expert |
   ```

4. **Whitelist in .gitignore** (REQUIRED):
   - Open `.gitignore`
   - Find the `# agents/` section
   - Add `!agents/my-new-expert.md` in alphabetical order
   - Required because `agents/` is gitignored by default with specific files whitelisted

5. **Add scripts to settings.json** (REQUIRED if agent uses scripts):
   - If your agent needs helper scripts, create them in `commands/scripts/<agent-name>/`
   - Open `settings.json`
   - Add the script to `allowedTools` array:
     - For bash scripts: `"Bash(~/.claude/commands/scripts/<agent-name>/<script>.sh*)"`
     - For Python scripts: `"Bash(uv run ~/.claude/commands/scripts/<agent-name>/<script>.py*)"`
   - Add the script to `permissions.allow` array (same format with `:*` suffix)
   - This allows the scripts to run without permission prompts

6. **Test the agent** - Ask Claude to delegate a task to it

7. **Update bug reporting rule** (REQUIRED):
   - Open `rules/50-agent-bug-reporting.md`
   - Add the new agent to the "Scope - Agents Covered" list
   - This ensures bugs in the new agent are tracked via GitHub issues

### Removing an Agent

1. **Delete the agent file** from `agents/`:
   ```bash
   rm agents/my-old-expert.md
   ```

2. **Remove whitelist entry** from `.gitignore`:
   - Open `.gitignore`
   - Find the `# agents/` section
   - Remove the `!agents/my-old-expert.md` line

3. **Remove routing rule** from `rules/10-agent-routing.md`:
   - Delete the row mapping tasks to this agent

4. **Update bug reporting rule**:
   - Open `rules/50-agent-bug-reporting.md`
   - Remove the agent from the "Scope - Agents Covered" list

5. **Clean up scripts** (if applicable):
   - Delete any scripts from `commands/scripts/<agent-name>/`
   - Remove entries from `settings.json` → `allowedTools` and `permissions.allow`

### Modifying Orchestrator Rules

1. **Edit files in `rules/`** directory
2. **Rules are auto-loaded** on next prompt (via `rule-injector.py`)
3. **Test changes** in a new conversation

### Adding a Slash Command

1. **Create command file** in `commands/`:
   ```bash
   touch commands/my-command.md
   ```

2. **Define command structure**:
   ```markdown
   ---
   name: my-command
   description: What this command does
   ---

   # My Command Implementation

   [Your command logic here]
   ```

3. **Whitelist in .gitignore** (REQUIRED):
   - Open `.gitignore`
   - Find the `# commands/` section
   - Add `!commands/my-command.md` in alphabetical order
   - Also whitelist any scripts: `!commands/scripts/my-command/*.sh`
   - Required because `commands/` is gitignored by default with specific files whitelisted

4. **Add scripts to settings.json** (REQUIRED if command uses scripts):
   - Open `settings.json`
   - Add the script to `allowedTools` array:
     - For bash scripts: `"Bash(~/.claude/commands/scripts/<command>/<script>.sh*)"`
     - For Python scripts: `"Bash(uv run ~/.claude/commands/scripts/<command>/<script>.py*)"`
   - Add the script to `permissions.allow` array (same format with `:*` suffix)
   - This allows the scripts to run without permission prompts

5. **Command is available** as `/my-command` after creation

### Testing Changes

**Test orchestrator rules:**
```bash
# Edit rules/
# Start new Claude conversation
# Verify orchestrator behavior matches rules
```

**Test agent:**
```bash
# Edit agents/my-expert.md
# Ask Claude to delegate task to my-expert
# Verify agent receives correct instructions
```

**Test hooks:**
```bash
# Edit scripts/rule-enforcer.py
# Try violating rule (e.g., orchestrator using Write)
# Verify hook blocks the action
```

### Running Tests

**Run all tests via tox:**
```bash
uvx --with tox-uv tox
```

**Run tests for specific Python version:**
```bash
uvx --with tox-uv tox -e py313
```

**Run pre-commit checks:**
```bash
pre-commit run --all-files
```

**Test files:**
- `tests/test_git_protection.py` - Git protection hook (106 tests)
- `tests/test_pre_compact_snapshot.py` - Compaction snapshot (70 tests)
- `tests/test_rule_enforcer.py` - Rule enforcement (87 tests)
- `tests/test_post_compact_restore.py` - State restoration (31 tests)

### Script Permission Checklist

When adding ANY new script that will be run during a command/skill/agent:

1. ✅ Create the script in the appropriate `commands/scripts/<name>/` directory
2. ✅ Whitelist in `.gitignore` (with `!` prefix)
3. ✅ Add to `settings.json` → `allowedTools` array
4. ✅ Add to `settings.json` → `permissions.allow` array
5. ✅ Test that the script runs without permission prompts

**Example for bash script:**
```json
// In settings.json:
"allowedTools": [
  "Bash(~/.claude/commands/scripts/my-command/my-script.sh*)"
],
"permissions": {
  "allow": [
    "Bash(~/.claude/commands/scripts/my-command/my-script.sh*):*"
  ]
}
```

**Example for Python script:**
```json
// In settings.json:
"allowedTools": [
  "Bash(uv run ~/.claude/commands/scripts/my-command/my-script.py*)"
],
"permissions": {
  "allow": [
    "Bash(uv run ~/.claude/commands/scripts/my-command/my-script.py*):*"
  ]
}
```

---

## Important Notes

### .gitignore Whitelist Pattern

**Critical directories follow a gitignore-by-default pattern with explicit whitelisting:**

The following directories are completely gitignored, with only specific files tracked:
- `agents/` - Each agent must be explicitly whitelisted
- `commands/` - Each command and its scripts must be explicitly whitelisted
- `rules/` - Each rule must be explicitly whitelisted
- `scripts/` - Each script must be explicitly whitelisted

**When adding ANY new file to these directories, you MUST:**
1. Open `.gitignore`
2. Find the corresponding section (e.g., `# agents/`)
3. Add `!path/to/your-file.ext` in alphabetical order
4. Commit both the new file AND the updated `.gitignore`

**Why:** These directories may contain personal/local configurations. Only shared, repository-worthy files are whitelisted.

### Rules Directory Auto-Loading

**Files in `rules/` are automatically injected into every prompt.**

- The `rule-injector.py` hook runs on `UserPromptSubmit`
- Rules are concatenated in alphabetical order
- Numbering (00-, 10-, etc.) controls load order
- Changes to `rules/` take effect immediately on next prompt

### Hooks and Security

**Hooks enforce orchestrator pattern:**

- **PreToolUse** - `rule-enforcer.py` blocks Edit/Write/Bash by orchestrator
- **UserPromptSubmit** - `rule-injector.py` loads rules from `rules/`
- **PreCompact** - `pre-compact-snapshot.py` saves state
- **SessionStart** - `post-compact-restore.py` restores after compact
- **Notification** - `my-notifier.sh` custom notifications

### settings.json - Tool Allowlist

**Only specific Bash commands are allowed for orchestrator:**

```json
"allowedTools": [
  "Edit(/tmp/claude/**)",           // Only /tmp/claude/
  "Write(/tmp/claude/**)",          // Only /tmp/claude/
  "Bash(mkdir -p /tmp/claude*)",    // Create temp dir
  "Bash(claude *)",                 // Agent delegation
  "Bash(mcp-cli*)",                 // MCP server discovery
  "Bash(sed -n *)",                 // Read-only sed
  "Bash(grep *)",                   // Search
  "Grep",                           // Grep tool
  // Slash command scripts...
]
```

This enforces that orchestrator delegates work instead of doing it directly.

---

## Common Tasks

### Update Agent Behavior
```bash
# Edit the agent file
vim ~/.claude/agents/python-expert.md

# Changes take effect immediately on next delegation
```

### Add New Rule Category
```bash
# Create new rule file with numbering
touch ~/.claude/rules/50-my-new-rules.md

# File auto-loads on next prompt (alphabetical order)
```

### Debug Hook Failures
```bash
# Check hook script output
# Hooks print to stderr, visible in Claude Code console

# Test hook manually
uv run ~/.claude/scripts/rule-enforcer.py
```

### View Loaded Rules
```bash
# Rules are injected on every prompt
# Check conversation context to see loaded rules
```

---

## Architecture Principles

### 1. Separation of Concerns
- **Orchestrator** = Traffic controller
- **Agents** = Execution specialists
- **Hooks** = Enforcement layer

### 2. Context Preservation
- Specialist context discarded after task
- Main conversation stays focused
- Parallel execution possible

### 3. Quality Assurance
- Mandatory code review loop
- Test automation after changes
- Iterate until approved

### 4. Flexibility
- Easy to add/modify agents
- Rules auto-load from directory
- Hooks customize behavior

### 5. Script-First for Deterministic Operations

**When an operation is deterministic and mechanical, use a shell script instead of AI-generated commands.**

| Operation Type | Approach |
|----------------|----------|
| Deterministic (find files, calculate hashes) | ✅ Use scripts |
| Semantic (understand code, map relationships) | ✅ Use AI agents |

**Benefits of scripts:**
- **Consistent behavior** - Same logic every time
- **No permission prompts** - Pre-approved in `allowedTools`
- **Faster execution** - No AI deliberation
- **Reduced context** - AI focuses on semantic tasks
- **Easier debugging** - Test scripts independently

**Example - General workflow:**
```
Phase 1: setup-environment.sh      → Deterministic (script)
Phase 2: find-source-files.sh      → Deterministic (script)
Phase 3: calculate-checksums.sh    → Deterministic (script)
Phase 4: language-expert           → Semantic (AI agent)
Phase 5: general-purpose           → Semantic (AI agent)
```

**Script location:** `commands/scripts/<command-name>/`

**When to create a script:**
1. File operations (find, list, filter)
2. Hash/checksum calculations
3. JSON parsing/generation
4. Directory setup
5. Argument parsing
6. Any operation with fixed, repeatable logic

---

## Troubleshooting

### Orchestrator Still Using Edit/Write
- Check `rule-enforcer.py` is running (PreToolUse hook)
- Verify `settings.json` has correct hook configuration
- Check for errors in hook script output

### Rules Not Loading
- Verify files are in `rules/` directory
- Check `rule-injector.py` hook is configured (UserPromptSubmit)
- Ensure files are readable (chmod +r)

### Agent Not Being Called
- Check routing table in `rules/10-agent-routing.md`
- Verify agent file exists in `agents/`
- Test with explicit delegation request

### Slash Command Not Working
- Verify file exists in `commands/`
- Check file has correct frontmatter (name, description)
- Restart Claude Code if recently added

---

## References

- **README.md** - Installation and setup instructions
- **rules/** - Full orchestrator rule definitions
- **agents/** - Individual agent implementations
- **commands/** - Slash command implementations
