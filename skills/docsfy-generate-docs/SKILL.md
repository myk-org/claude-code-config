---
name: docsfy-generate-docs
description: Use when the user asks to generate documentation with docsfy, create docs for a repository using docsfy, or mentions docsfy documentation generation for any project
---

# Generate Documentation with docsfy

## Overview

Generate AI-powered documentation for a Git repository using the docsfy CLI.
The CLI connects to a docsfy server that clones the repo, plans documentation structure, and generates pages using AI.

## Prerequisites (MANDATORY - check before anything else)

### 1. docsfy CLI installed

```bash
docsfy --help
```

If not found: `uv tool install docsfy`

### 2. Server is alive

```bash
docsfy health
```

If health check fails, inform the user that the docsfy server is not reachable and stop. The user may need to:

- Start the server: `docsfy-server`
- Check their config: `docsfy config show`
- Set up a profile: `docsfy config init`

## Workflow

### Phase 1: Collect Parameters

**Always ask the user — NEVER assume or hardcode provider/model:**

| Parameter | Required | How to get |
|-----------|----------|------------|
| Repository URL | Yes | Ask user or infer from current repo's git remote |
| AI Provider | Yes | Ask user (options: `claude`, `gemini`, `cursor`) |
| AI Model | Yes | Ask user — provider-specific model name |
| Branch | No | Default: `main` |
| Output directory | No | Default: `docs/` |
| Force regeneration | No | Default: no |

Use `AskUserQuestion` to collect provider, model, and any missing parameters.

### GitHub Pages Setup (GitHub repos only)

If the repository URL does not contain `github.com`, skip the GitHub Pages setup entirely and treat GitHub Pages as not configured.

If the repository is hosted on GitHub, check if GitHub Pages is configured to serve from `docs/` on the target branch:

```bash
gh api repos/<owner>/<repo>/pages --jq '.source' 2>/dev/null
```

- If **not configured** or returns error: ask the user if they want to enable GitHub Pages to serve the generated docs.
  - **Yes** → Configure GitHub Pages to serve from `docs/` on the target branch:

    ```bash
    gh api repos/<owner>/<repo>/pages -X POST -f "source[branch]=<branch>" -f "source[path]=/docs"
    ```

  - **No** → Skip and continue with generation.
- If **already configured** with `docs/` path: no action needed, continue.
- If **configured with a different path**: inform the user and ask how to proceed.

**Track whether GitHub Pages is confirmed to serve from `docs/` on the target branch**
(either pre-existing or newly set up) — this is needed for Phase 5.
If Pages is configured but serves from a different path and the user chose not to change it,
treat it as not configured for Phase 5 purposes.

### Phase 2: Generate Documentation

```bash
docsfy generate <repo_url> --branch <branch> --provider <provider> --model <model> --watch [--force]
```

- Always use `--watch` for real-time WebSocket progress
- Add `--force` only if user requested force regeneration

Monitor output until generation completes with status `ready`, `error`, or `aborted`.

If generation fails, show the error and ask the user how to proceed.

### Phase 3: Create Branch

After generation completes (status: `ready`), create a local branch to isolate docs changes.

**Extract `<project_name>`** from the repo URL: strip any trailing `/` and `.git` suffix, then take the last path segment (e.g., `docsfy` from `https://github.com/myk-org/docsfy.git`).

Before switching branches, check for uncommitted changes:

```bash
git status --porcelain
```

If the working tree is dirty, inform the user and ask whether to stash changes, abort, or continue.

Create the branch:

```bash
git fetch origin <branch>
git checkout -B docs/docsfy-<project_name> origin/<branch>
```

- `<branch>` is the branch parameter from Phase 1.
- Uses `-B` (capital B) to create or reset the branch if it already exists from a previous run.

This ensures docs changes are on a separate branch, not directly on the current working branch.

### Phase 4: Download and Flatten Generated Docs

```bash
docsfy download <project_name> --branch <branch> --provider <provider> --model <model> --output <output_dir>
```

`<project_name>` is the same value extracted in Phase 3.

The download creates a nested subdirectory: `<output_dir>/<project>-<branch>-<provider>-<model>/`. Verify it exists, then flatten so all files are directly under `<output_dir>/`:

```bash
ls <output_dir>/<project>-<branch>-<provider>-<model>/
mv <output_dir>/<project>-<branch>-<provider>-<model>/* <output_dir>/
mv <output_dir>/<project>-<branch>-<provider>-<model>/.* <output_dir>/ 2>/dev/null
rm -rf <output_dir>/<project>-<branch>-<provider>-<model>
```

If the nested subdirectory does not exist after download, the project name or parameters may not match what was used during generation — surface the error to the user.

### Phase 5: GitHub Pages Post-Setup (conditional)

**This phase runs ONLY if GitHub Pages is confirmed to serve from `docs/` on the target branch** (determined in Phase 1).

#### 5a. Display Docs Site Link

Show the user the live documentation URL:

```text
Your documentation site: https://<owner>.github.io/<repo>/
```

Extract `<owner>` and `<repo>` from the repository URL.

#### 5b. Offer README Simplification

Ask the user if they want to simplify the project README to keep it minimal and point to the new docs site:

> GitHub Pages is serving your docs. Would you like to simplify the project README to point to the docs site?

- **Yes** → Read the current `README.md` in the repository root. Create a simplified version that keeps ONLY:
  - Project title + one-line description
  - Link to the docs site prominently (`https://<owner>.github.io/<repo>/`)
  - Quick start (e.g., docker run or install command, 5 lines max)
  - CLI install + 3-line usage example
  - "See the [full documentation](https://<owner>.github.io/<repo>/) for everything else"
  - License section

  Remove all other detailed content (API docs, configuration guides, detailed usage, etc.).

  If no `README.md` exists, skip this step.
- **No** → Skip and continue to summary.

### Phase 6: Summary

Display:

- Project name and repository URL
- Branch, provider, model used
- Output directory where docs were extracted
- Docs site URL (if GitHub Pages is configured)
- Whether README was simplified (if applicable)

## Quick Reference

| Command | Purpose |
|---------|---------|
| `docsfy generate <url> --watch` | Generate docs with live progress |
| `docsfy status <name>` | Check generation status |
| `docsfy download <name> -o <dir>` | Download docs to directory |
| `docsfy list` | List all projects |
| `docsfy abort <name>` | Abort active generation |
| `docsfy health` | Check server connectivity |
| `docsfy config show` | Show server profiles |
| `docsfy config init` | Set up a new server profile |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Hardcoding provider/model | Always ask the user |
| Skipping health check | Server must be reachable before generating |
| Using local files instead of repo URL | docsfy works with Git repository URLs |
| Forgetting `--watch` flag | Always use `--watch` for real-time progress |
| Downloading before ready | Check status is `ready` before downloading |
| Leaving nested download folder | Flatten after download — move files to output root |
| Downloading before creating branch | Always create a docs branch before downloading |
| Showing docs link without Pages serving docs/ | Only show docs URL if GitHub Pages serves from `docs/` on target branch |
