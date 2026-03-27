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

It also contains the **`myk-claude-tools`** CLI package (in `myk_claude_tools/`),
which provides CLI commands for reviews, PR operations, releases, and database queries used by the plugins.

The goal is to preserve context, improve code quality, and enable parallel execution by routing tasks to specialized agents.

---

## Repository Structure

```text
claude-code-config/
├── agents/                    # Specialist agent definitions + shared rules
│   ├── 00-base-rules.md       # Shared rules for ALL agents
│   ├── api-documenter.md      # OpenAPI/Swagger specs
│   ├── bash-expert.md         # Shell scripting
│   ├── debugger.md            # Error analysis
│   ├── docker-expert.md       # Container orchestration
│   ├── docs-fetcher.md        # External docs (prioritizes llms.txt)
│   ├── frontend-expert.md     # JS/TS/React/Vue/Angular
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
├── plugins/                   # Claude Code plugins (slash commands)
│   ├── myk-github/            # GitHub operations plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── commands/          # /myk-github:coderabbit-rate-limit, /myk-github:pr-review, /myk-github:refine-review, /myk-github:release, /myk-github:review-handler
│   │   └── README.md
│   ├── myk-review/            # Local review operations plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── commands/          # /myk-review:local, /myk-review:query-db
│   │   └── README.md
│   ├── myk-acpx/              # Multi-agent ACP plugin (via acpx)
│   │   ├── .claude-plugin/plugin.json
│   │   ├── commands/          # /myk-acpx:prompt
│   │   └── README.md
│   └── README.md              # Plugin development guide
│
├── rules/                     # Orchestrator rules (AUTO-LOADED)
│   ├── 00-orchestrator-core.md      # Core delegation rules
│   ├── 05-issue-first-workflow.md   # Issue-first workflow for requests
│   ├── 10-agent-routing.md          # Agent selection logic
│   ├── 15-mcp-launchpad.md          # MCP Launchpad CLI for MCP servers
│   ├── 20-code-review-loop.md       # Mandatory review workflow
│   ├── 25-task-system.md            # Task system usage guidelines
│   ├── 30-slash-commands.md         # Slash command execution
│   ├── 40-critical-rules.md         # Parallel execution, temp files
│   └── 50-agent-bug-reporting.md    # Bug reporting for agent issues
│
├── scripts/                   # Hook scripts (Python/Bash)
│   ├── git-protection.py      # Protects main branch, merged branches
│   ├── my-notifier.sh         # Custom notifications
│   ├── rule-enforcer.py       # Blocks orchestrator from using Edit/Write/Bash
│   ├── rule-injector.py       # Auto-loads rules from rules/
│   └── session-start-check.sh # SessionStart hook for tool validation
│
├── myk_claude_tools/           # CLI package used by plugins
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point
│   ├── coderabbit/              # CodeRabbit rate limit handling
│   │   ├── commands.py
│   │   └── rate_limit.py
│   ├── db/                     # Database operations
│   │   ├── commands.py
│   │   └── query.py
│   ├── pr/                     # PR operations
│   │   ├── claude_md.py
│   │   ├── commands.py
│   │   ├── common.py
│   │   ├── diff.py
│   │   └── post_comment.py
│   ├── release/                # Release management
│   │   ├── bump_version.py
│   │   ├── commands.py
│   │   ├── create.py
│   │   ├── detect_versions.py
│   │   └── info.py
│   └── reviews/                # Review fetching and parsing
│       ├── coderabbit_parser.py
│       ├── commands.py
│       ├── fetch.py
│       ├── pending_fetch.py
│       ├── pending_update.py
│       ├── post.py
│       └── store.py
│
├── tests/                     # Unit tests for Python scripts
│   ├── test_git_protection.py
│   └── test_rule_enforcer.py
│
├── settings.json              # Hooks, tool permissions, status line
├── statusline.sh              # Custom status bar script
├── tox.toml                   # Test configuration
├── pyproject.toml             # Python project config (ruff, mypy)
├── .pre-commit-config.yaml    # Pre-commit hooks
├── .flake8                    # Flake8 configuration
├── README.md                  # Installation and setup guide
├── AI_REVIEW.md               # This file - AI review tool context
└── LICENSE                    # MIT License
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

### 4. Slash Commands (Plugins)

**Slash commands are provided by plugins in the `plugins/` directory.**

- Commands follow the format `/plugin-name:command` (e.g., `/myk-github:pr-review`)
- Slash commands execute DIRECTLY in orchestrator (not delegated)
- ALL internal operations run in orchestrator context
- Slash command prompt overrides general CLAUDE.md rules
- Example: `/myk-github:pr-review` runs scripts, posts comments directly

### 5. MCP Server Access

**MCP servers are accessed via [`mcp-launchpad`](https://github.com/kenneth-liao/mcp-launchpad) (`mcpl`).**

- Orchestrator uses `mcpl` for discovery (list servers, explore tools)
- Agents execute MCP tools directly via `mcpl`
- See `rules/15-mcp-launchpad.md` for full command reference

### 6. Task System

**Claude Code provides task tracking tools for complex workflows.**

**Tasks persist locally to disk** at `~/.claude/tasks/<session-uuid>/` (a Claude session UUID folder) and can be resumed across sessions on the same machine/profile.

**Available tools:**

- `TaskCreate` - Create new tasks with subject, description, activeForm
- `TaskUpdate` - Update task status, add dependencies (blockedBy/blocks)
- `TaskList` - View all tasks and their status
- `TaskGet` - Get full details of a specific task

**When to use tasks:**

- Complex work that might be interrupted mid-session
- Multi-step workflows where progress tracking helps
- Work you might need to resume in a new session
- Operations where seeing status helps the user
- Slash commands with dependent phases

**Key question:** "Is this work I'd want to track and potentially resume?"

**When NOT to use:**

- Simple operations that complete quickly
- Agent work (agents are ephemeral)
- Trivial fixes or single-action operations

**Task naming:**

- `subject`: Imperative form ("Run tests", "Post comments")
- `activeForm`: Present continuous ("Running tests", "Posting comments")

**Reference:** See `rules/25-task-system.md` for full guidelines.

### 7. Review Database

The review database provides query access to the reviews SQLite database at `.claude/data/reviews.db`.

**Key features:**

- **Auto-skip**: Previously dismissed comments are automatically skipped when fetching new reviews
- **Analytics**: Query addressed rates, duplicate patterns, reviewer stats

**Command:** `/myk-review:query-db` - Query the database for review analytics (from the `myk-review` plugin)

### 8. Plugin Marketplace

This repository also serves as a Claude Code plugin marketplace. Users can install plugins from this repo.

**Installation:**

```text
/plugin marketplace add myk-org/claude-code-config
```

**Available Plugins:**

| Plugin | Description | Commands |
|--------|-------------|----------|
| `myk-github` | GitHub operations | `/myk-github:coderabbit-rate-limit`, `/myk-github:pr-review`, `/myk-github:refine-review`, `/myk-github:release`, `/myk-github:review-handler` |
| `myk-review` | Local review operations | `/myk-review:local`, `/myk-review:query-db` |
| `myk-acpx` | Multi-agent ACP | `/myk-acpx:prompt` |

**Plugin Location:** `plugins/` directory

**Marketplace Manifest:** `.claude-plugin/marketplace.json`

---

## Key Agents

### Language Specialists

- **python-expert** - Python development, async, testing
- **go-expert** - Go development, goroutines, modules
- **frontend-expert** - JS/TS/React/Vue/Angular
- **java-expert** - Java/Spring Boot development

### Infrastructure

- **docker-expert** - Dockerfiles, container orchestration
- **kubernetes-expert** - K8s/OpenShift, Helm, GitOps
- **jenkins-expert** - CI/CD pipelines, Jenkinsfiles
- **bash-expert** - Shell scripting automation

### Development Workflow

- **git-expert** - Git operations, branching strategies
- **test-automator** - Test suite creation, CI pipelines
- **test-runner** - Test execution and reporting
- **debugger** - Root cause analysis (diagnosis only, delegates fixes to specialists)

### Code Review (Plugin Agents)

- **superpowers:code-reviewer** - General code quality and maintainability
- **pr-review-toolkit:code-reviewer** - Project guidelines and style adherence
- **feature-dev:code-reviewer** - Bugs, logic errors, and security vulnerabilities

### Documentation

- **docs-fetcher** - Fetches external library/framework docs (prioritizes llms.txt)
- **technical-documentation-writer** - User-focused documentation
- **api-documenter** - OpenAPI/Swagger specifications

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

5. **Test the agent** - Ask Claude to delegate a task to it

6. **Update bug reporting rule** (REQUIRED):

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

### Modifying Orchestrator Rules

1. **Edit files in `rules/`** directory
2. **Rules are auto-loaded** on next prompt (via `rule-injector.py`)
3. **Test changes** in a new conversation

### Adding a Slash Command (Plugin)

**Slash commands are now defined as plugins.** See `plugins/README.md` for the complete guide.

**Quick overview:**

1. Create plugin directory under `plugins/`
2. Add plugin manifest (`.claude-plugin/plugin.json`)
3. Add commands in `commands/` directory within the plugin
4. Update `.claude-plugin/marketplace.json` at repo root
5. Whitelist files in `.gitignore`

**Plugin structure:**

```text
plugins/
└── my-plugin/
    ├── .claude-plugin/
    │   └── plugin.json       # Plugin manifest
    ├── commands/             # Slash command definitions
    │   └── my-command.md
    ├── skills/               # Skill implementations (optional)
    │   └── my-skill/
    │       └── SKILL.md
    └── README.md             # Plugin documentation
```

**Commands use the format:** `/plugin-name:command` (e.g., `/myk-github:pr-review`)

**Prerequisites:** Some plugins require the `myk-claude-tools` CLI:

```bash
uv tool install myk-claude-tools
```

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

---

## Important Notes

### .gitignore Whitelist Pattern

**Critical directories follow a gitignore-by-default pattern with explicit whitelisting:**

The following directories are completely gitignored, with only specific files tracked:

- `agents/` - Each agent must be explicitly whitelisted
- `plugins/` - Each plugin must be explicitly whitelisted
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
- **SessionStart** - `session-start-check.sh` validates tool configuration
- **Notification** - `my-notifier.sh` custom notifications

### settings.json - Tool Allowlist

**Only specific Bash commands are allowed for orchestrator:**

```json
"allowedTools": [
  "Edit(/tmp/claude/**)",           // Only /tmp/claude/
  "Write(/tmp/claude/**)",          // Only /tmp/claude/
  "Bash(mkdir -p /tmp/claude*)",    // Create temp dir
  "Bash(claude:*)",                 // Agent delegation
  "Bash(mcpl:*)",                   // MCP server discovery
  "Bash(myk-claude-tools:*)",       // Plugin CLI tools
  "Bash(sed -n:*)",                 // Read-only sed
  "Bash(grep:*)",                   // Search
  "Grep"                            // Grep tool
]
```

This enforces that orchestrator delegates work instead of doing it directly.

### CLAUDE.md and AI_REVIEW.md Sync

**`AI_REVIEW.md` is the canonical project-context file for AI review tools.**

`CLAUDE.md` is a local-only file (gitignored) that contains Claude Code instructions.
It must be kept in sync with `AI_REVIEW.md` — update both when modifying shared project context or guidelines.

## Handling Review Feedback

When fixing reviewer comments (human, CodeRabbit):

- If the reviewer provides a specific code suggestion or diff, implement it exactly — not your own interpretation
- Do NOT simplify, minimize, or "half-fix" the suggestion
- After fixing, verify your code matches what the reviewer asked for, not just "addresses the concern"
- **NO SKIP WITHOUT USER APPROVAL:** If you disagree with a suggestion, ASK THE USER before skipping, partially fixing, or applying a minimum-viable fix
- **Read the ENTIRE review thread before acting.** Review threads contain a top-level comment plus replies.
  Comments often contain multiple parts: a main issue description, code suggestions, AND additional references
  like "Also applies to: 663-668" or mentions of other files/lines. Replies may contain clarifications,
  additional locations, or refined suggestions. You MUST address ALL parts from the comment AND replies,
  not just the first paragraph.
- **Multi-location fixes are MANDATORY.** When a comment says "Also applies to: X-Y" or references other lines/files,
  apply the same logical fix, adapted as needed to each location. These are not optional — they are part of the
  comment's requirements.
- **Post-fix verification checklist.** After fixing a comment, re-read the ORIGINAL review thread in full and verify:
  1. Every code suggestion or diff was implemented
  2. Every referenced file and line range was addressed
  3. Every "Also applies to" location was fixed
  4. No secondary instructions or reply clarifications were skipped
  If any part was missed, fix it before moving to the next comment.

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

- **Mandatory code review** - Every code change goes through 3 parallel review agents
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

```text
Phase 1: setup-environment.sh      → Deterministic (script)
Phase 2: find-source-files.sh      → Deterministic (script)
Phase 3: calculate-checksums.sh    → Deterministic (script)
Phase 4: language-expert           → Semantic (AI agent)
Phase 5: general-purpose           → Semantic (AI agent)
```

**Script execution:** Plugins can use the `myk-claude-tools` CLI for deterministic operations.

**When to use scripts/CLI tools:**

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

- Verify plugin exists in `plugins/` directory
- Check plugin manifest (`.claude-plugin/plugin.json`) is valid
- Check command file has correct frontmatter (name, description)
- Ensure plugin is installed: `/plugin install <plugin-name>@myk-org`
- Restart Claude Code if recently added
- **NEVER add a `name` field to command frontmatter** — adding `name` causes
  the plugin to stop appearing in the plugins list. Commands only need
  `description`, `argument-hint`, and `allowed-tools` in their frontmatter.

---

## References

- **README.md** - Installation and setup instructions
- **rules/** - Full orchestrator rule definitions
- **agents/** - Individual agent implementations
- **plugins/** - Slash command implementations (plugin-based)
