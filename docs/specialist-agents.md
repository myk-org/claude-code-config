# Specialist Agents

Specialist agents are the execution layer in `claude-code-config`. The orchestrator decides who should handle a task, but the specialist is the part that actually edits files, runs commands, fetches documentation, or talks to external systems.

If you only remember two files, make them `rules/10-agent-routing.md` and `agents/00-base-rules.md`. The first decides which agent should receive a task. The second defines the shared behavior every bundled specialist follows.

```5:36:rules/10-agent-routing.md
| Domain/Tool                                                                      | Agent                              |
|----------------------------------------------------------------------------------|------------------------------------|
| **Languages (by file type)**                                                     |                                    |
| Python (.py)                                                                     | `python-expert`                    |
| Go (.go)                                                                         | `go-expert`                        |
| Frontend (JS/TS/React/Vue/Angular)                                                | `frontend-expert`                  |
| Java (.java)                                                                     | `java-expert`                      |
| Shell scripts (.sh)                                                              | `bash-expert`                      |
| Markdown (.md)                                                                   | `technical-documentation-writer`   |
| **Infrastructure**                                                               |                                    |
| Docker                                                                           | `docker-expert`                    |
| Kubernetes/OpenShift                                                             | `kubernetes-expert`                |
| Jenkins/CI/Groovy                                                                | `jenkins-expert`                   |
| **Development**                                                                  |                                    |
| Git operations (local)                                                           | `git-expert`                       |
| GitHub (PRs, issues, releases, workflows)                                        | `github-expert`                    |
| Tests                                                                            | `test-automator`                   |
| Debugging                                                                        | `debugger`                         |
| API docs                                                                         | `api-documenter`                   |
| Claude Code docs (features, hooks, settings, commands, MCP, IDE, Agent SDK, API) | `claude-code-guide` (built-in)     |
| External library/framework docs (React, FastAPI, Django, etc.)                   | `docs-fetcher`                     |

### Built-in vs Custom Agents

**Built-in agents** are provided by Claude Code itself and do NOT require definition files in `agents/`:

- `claude-code-guide` - Has current Claude Code documentation built into Claude Code
- `general-purpose` - Default fallback agent when no specialist matches

**Custom agents** are defined in this repository's `agents/` directory and require definition files:

- All other agents in the routing table above (e.g., `python-expert`, `docs-fetcher`, `git-expert`)
```

Routing is based on intent, not just the tool you think you need. A pull request goes to `github-expert`, not `git-expert`. External React or FastAPI docs go to `docs-fetcher`, not the built-in `claude-code-guide`. Markdown work usually goes to `technical-documentation-writer`, but API-focused documentation belongs with `api-documenter`.

> **Note:** This page focuses on the bundled custom agents defined under `agents/`. The routing table also mentions built-in Claude Code agents such as `claude-code-guide` and `general-purpose`, but those are not shipped from this repository.

## Bundled Agents At A Glance

### Code And Documentation

| Agent | Best for | Notable boundary or instruction |
| --- | --- | --- |
| `python-expert` | Python code, async work, typing, pytest-based changes | Must use `uv` and `uvx`; never raw `python`, `python3`, `pip`, or `pip3`. |
| `go-expert` | Go code, concurrency, modules, and tests | Favors idiomatic Go, safe concurrency, and table-driven testing. Includes the `test-driven-development` skill. |
| `java-expert` | Java, Spring, Maven, Gradle, JUnit | Targets modern Java and secure, tested application code. Includes the `test-driven-development` skill. |
| `frontend-expert` | JavaScript, TypeScript, React, Vue, Angular, CSS | Covers UI implementation and frontend tooling. Uses the `frontend-design` skill for UI work. |
| `technical-documentation-writer` | User-facing docs, guides, reference pages, Markdown content | Optimized for reader-first structure, actionable steps, and realistic examples. |
| `api-documenter` | OpenAPI and Swagger specs, SDK docs, auth/error docs | Expects real request and response examples, version-aware docs, and developer experience details. |
| `docs-fetcher` | External library and framework documentation | For third-party docs only. Prefers `llms-full.txt`, then `llms.txt`, then HTML parsing. |

### Infrastructure And Automation

| Agent | Best for | Notable boundary or instruction |
| --- | --- | --- |
| `bash-expert` | Bash, Zsh, POSIX shell, automation scripts, Unix/Linux admin tasks | Pushes defensive shell practices such as `set -euo pipefail`, careful quoting, and ShellCheck-friendly scripts. |
| `docker-expert` | Dockerfiles, Compose, Podman, image optimization, container security | Favors multi-stage builds, pinned base images, non-root users, and secure secret handling. |
| `kubernetes-expert` | Kubernetes, OpenShift, Helm, GitOps, service-mesh tasks | Leans declarative, with strong defaults for RBAC, probes, security contexts, and resource limits. |
| `jenkins-expert` | Jenkinsfiles, Groovy, Jenkins automation, build scripts | Treats credentials handling, timeouts, post actions, and reusable shared libraries as first-class concerns. |

### Diagnosis, Testing, And Repository Workflow

| Agent | Best for | Notable boundary or instruction |
| --- | --- | --- |
| `debugger` | Root-cause analysis for errors, failing tests, and unexpected behavior | Diagnoses only. It recommends changes but does not edit files. Includes the `systematic-debugging` skill. |
| `test-runner` | Running requested tests and summarizing failures | Executes exactly what it was asked to run, reports failures concisely, and never fixes code. |
| `test-automator` | Creating tests, fixtures, coverage setup, and test pipeline config | Different from `test-runner`: it authors testing assets rather than only executing them. Includes the `test-driven-development` skill. |
| `git-expert` | Local Git work such as commit, branch, merge, rebase, stash | Handles repository-local Git only. It does not run tests, does not fix code, and explicitly avoids `--no-verify`. |
| `github-expert` | Pull requests, issues, releases, repos, workflows, and `gh` API work | Handles GitHub platform operations, not local-only Git. It expects test verification before PR-related actions. |

> **Note:** The mandatory review loop also uses three plugin review agents: `superpowers:code-reviewer`, `pr-review-toolkit:code-reviewer`, and `feature-dev:code-reviewer`. Those are referenced in `rules/20-code-review-loop.md`, but they are not bundled definition files in `agents/`.

## Similar-Sounding Agents, Different Jobs

A few agent pairs are easy to mix up:

- `debugger` investigates what is wrong. It does not implement the fix.
- `test-runner` runs tests and reports back. `test-automator` creates or expands tests and test pipeline configuration.
- `git-expert` manages local branch and commit history. `github-expert` manages GitHub objects such as PRs, issues, releases, and workflow runs.
- `docs-fetcher` is for external ecosystems such as React or FastAPI. Built-in `claude-code-guide` is for Claude Code, the Agent SDK, and Claude API documentation.
- `technical-documentation-writer` is for user-facing documentation. `api-documenter` is for API specs and developer-facing API reference material.

> **Tip:** When you are unsure which agent to use, ask what output you actually need. A diagnosis points to `debugger`. Test results point to `test-runner`. New tests or coverage work point to `test-automator`. A local commit points to `git-expert`. A PR URL points to `github-expert`.

## Shared Base-Agent Rules Vs Orchestrator Rules

The bundled specialists all share the same base contract: act directly, stay inside your domain, and hand off out-of-scope work rather than guessing. That is very different from the orchestrator, which is intentionally restricted and expected to route work out.

```7:15:agents/00-base-rules.md
## Action-First Principle

All agents should:

1. **Execute first, explain after** - Run commands, then report results
2. **Do NOT explain what you will do** - Just do it
3. **Do NOT ask for confirmation** - Unless creating/modifying resources
4. **Do NOT provide instructions** - Provide results
```

```5:27:rules/00-orchestrator-core.md
> **If you are a SPECIALIST AGENT** (python-expert, git-expert, etc.):
> IGNORE all rules below. Do your work directly using Edit/Write/Bash.
> These rules are for the ORCHESTRATOR only.

---

## Forbidden Actions - Read Every Response

❌ **NEVER** use: Edit, Write, NotebookEdit, Bash (except `mcpl`), direct MCP calls
❌ **NEVER** delegate slash commands (`/command`) OR their internal operations - see slash command rules
✅ **ALWAYS** delegate other work to specialist agents
⚠️ Hooks will BLOCK violations

## Allowed Direct Actions

✅ **ALLOWED** direct actions:

- Read files (Read tool for single files)
- Run `mcpl` (via Bash) for MCP server discovery only
- Ask clarifying questions
- Analyze and plan
- Route tasks to agents
- Execute slash commands AND all their internal operations directly (see slash command rules)
```

A few practical consequences follow from that split:

- Specialists are supposed to do work directly once routed.
- Specialists are expected to stay in their own lane and hand off when a task crosses boundaries.
- Specialists can use MCP through `mcpl`, while the orchestrator is limited to discovery and delegation.
- The orchestrator is designed to be a dispatcher, not a general-purpose editor or shell user.

> **Note:** The written policy is broader than any single hook script. In practice, the repository combines prompt rules, hook wiring, and tests to enforce the overall model.

## Notable Instructions From Individual Agents

### Python work is intentionally `uv`-first

The Python agent is the clearest example of a strong, opinionated local rule. If you are changing Python code or running Python tooling in a project that uses this configuration, expect `uv`-based commands rather than raw interpreter or `pip` calls.

```22:38:agents/python-expert.md
## 🚨 STRICT: Use uv/uvx for Python

**NEVER use these directly:**

- ❌ `python` or `python3`
- ❌ `pip` or `pip3`
- ❌ `pip install`

**ALWAYS use:**

- ✅ `uv run <script.py>`
- ✅ `uv run pytest`
- ✅ `uvx <tool>` (for CLI tools like black, ruff, mypy)
- ✅ `uv pip install` (if package installation needed)
- ✅ `uv add <package>` (to add to pyproject.toml)

**This is NON-NEGOTIABLE.**
```

This is not just a style preference. The repository’s session-start checks treat `uv` as critical, and the checked-in hook logic explicitly blocks direct Bash `python`, `python3`, `pip`, `pip3`, and raw `pre-commit` usage.

### External docs go through `docs-fetcher`

`docs-fetcher` is not a generic web-search helper. It is a specialist for current third-party documentation, and its workflow is intentionally optimized for LLM-friendly doc sources before falling back to regular web pages.

```23:59:agents/docs-fetcher.md
1. **Discover** - Use WebSearch to find official documentation URL
2. **llms-full.txt First** - Try `{base_url}/llms-full.txt` for complete docs, then `{base_url}/llms.txt` for index, then HTML
3. **Parse Smart** - Extract only relevant sections based on query
4. **Context Rich** - Include examples and key points
5. **Source Cited** - Always provide source URL and type

## Workflow

```text
Request: {library} + {topic}
    ↓
WebSearch → Find official docs URL
    ↓
Try: {base_url}/llms-full.txt
    ↓
Exists? ──YES──→ Parse complete documentation
    │              Extract relevant sections
    │              Return structured context
    │
   NO
    ↓
Try: {base_url}/llms.txt
    ↓
Exists? ──YES──→ Parse llms.txt index
    │              Find relevant links
    │              WebFetch linked pages
    │              Return structured context
    │
   NO
    ↓
WebFetch main docs page
    ↓
Parse HTML/markdown content
    ↓
Extract relevant sections
    ↓
Return structured context
```
```

That makes `docs-fetcher` a good fit for React, FastAPI, Django, and other external ecosystems, but not for Claude Code documentation. The routing table explicitly reserves Claude Code, Agent SDK, and Claude API docs for the built-in `claude-code-guide`.

### Debugging, test running, and test authoring are deliberately separate

This repository draws a clean line between three kinds of “testing” work:

- `debugger` explains why something failed and points to the likely fix location.
- `test-runner` runs the specified tests and returns focused failure analysis.
- `test-automator` creates or improves the tests, fixtures, and test pipeline setup.

That separation matters because it keeps “figure out what’s broken,” “run the suite,” and “write the tests” from turning into one blurry responsibility.

### Local Git and GitHub platform work are also separate

`git-expert` and `github-expert` are intentionally split. Local repository operations stay with `git-expert`. Anything that creates or changes GitHub resources goes to `github-expert` through `gh`.

> **Warning:** Git safeguards are not just advisory. `git-protection.py` blocks commits and pushes on protected branches such as `main` and `master`, and it also blocks work on branches that are already merged. Both `git-expert` and `github-expert` are designed to work with that protection rather than bypass it.

## How The Repository Reinforces Agent Behavior

The hook and settings layer is what turns these rules from documentation into runtime behavior. `settings.json` wires together the reminder, enforcement, protection, and environment checks that support the agent model.

```37:85:settings.json
    "PreToolUse": [
      {
        "matcher": "TodoWrite|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run ~/.claude/scripts/rule-enforcer.py"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run ~/.claude/scripts/git-protection.py"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "prompt",
            "prompt": "You are a security gate protecting against catastrophic OS destruction. Analyze: $ARGUMENTS\n\nBLOCK if the command would:\n- Delete system directories: /, /boot, /etc, /usr, /bin, /sbin, /lib, /var, /home\n- Write to disk devices: dd to /dev/sda, /dev/nvme, etc.\n- Format filesystems: mkfs on any device\n- Remove critical files: /etc/fstab, /etc/passwd, /etc/shadow, kernel/initramfs\n- Recursive delete with sudo or as root\n- Chain destructive commands after safe ones using &&, ;, |, ||\n\nASK (requires user confirmation) if:\n- Command uses sudo but is not clearly destructive\n- Deletes files outside system directories but looks risky\n\nALLOW all other commands - this gate only guards against OS destruction.\n\nIMPORTANT: Use your judgment. If a command seems potentially destructive even if not explicitly listed above, ASK the user for confirmation.\n\nRespond with JSON: {\"decision\": \"approve\" or \"block\" or \"ask\", \"reason\": \"brief explanation\"}",
            "timeout": 10000
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "uv run ~/.claude/scripts/rule-injector.py"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/session-start-check.sh",
            "timeout": 5000
          }
        ]
      }
    ]
```

A few important things happen here:

- `rule-injector.py` adds a “manager, not executor” reminder at prompt submission time.
- `rule-enforcer.py` blocks certain shell-level violations, especially direct `python`, `pip`, and `pre-commit` usage.
- `git-protection.py` protects branch safety for Git operations.
- The extra security prompt hook acts as a final guardrail against destructive shell commands.
- `session-start-check.sh` validates prerequisites such as `uv`, and conditionally checks for tools like `gh`, `prek`, and `mcpl`.

The hook behavior is also covered by unit tests. In particular, `tests/test_rule_enforcer.py` verifies the Bash restrictions and also confirms that non-Bash tools are still allowed, while `tests/test_git_protection.py` covers branch detection, merged-branch checks, protected-branch blocking, and GitHub PR merge-status handling.

## Validation In This Repository

This repository does not check in `.github/workflows/` files, and it does not include a `Jenkinsfile`. Even so, it does include checked-in validation configuration that supports the documented behavior of its scripts and rules.

`tox.toml` defines the repository’s test entry point:

```1:7:tox.toml
skipsdist = true
envlist = ["unittests"]

[env.unittests]
description = "Run pytest tests"
deps = ["uv"]
commands = [["uv", "run", "--group", "tests", "pytest", "tests"]]
```

That is paired with `.pre-commit-config.yaml`, which enables checks from `pre-commit-hooks`, `flake8`, `detect-secrets`, `ruff`, `gitleaks`, `mypy`, and `markdownlint`. In other words, the repo’s own quality story is local and script-centric rather than workflow-YAML-centric.

This distinction matters for the agent docs:

- `jenkins-expert` and `test-automator` are available because projects using this configuration may need CI or pipeline work.
- The configuration repository itself validates behavior through hook scripts, local linting and formatting checks, and unit tests under `tests/`.
- The most important “source of truth” for specialist-agent behavior is still the checked-in agent definitions and rules, not a separate CI pipeline file.

> **Tip:** If you want to understand why a task was routed a certain way, read three things in order: `rules/10-agent-routing.md`, the relevant file in `agents/`, and then `settings.json` plus the matching script in `scripts/` if the behavior looks enforced rather than advisory.
