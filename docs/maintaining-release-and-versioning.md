# Maintaining Releases and Versioning

`claude-code-config` has more than one version surface, and not all of them are automated in the same way.

At a high level, maintainers need to keep track of:

- the Python CLI package version for `myk-claude-tools`
- the runtime `__version__` inside the Python package
- each plugin's own `.claude-plugin/plugin.json`
- the root `.claude-plugin/marketplace.json`

Only the first two are automatically discovered and updated by the built-in release helpers.

> **Note:** This repository does not include a checked-in `.github/workflows` release pipeline. Release preparation and publishing are driven by `myk-claude-tools release ...` and the `/myk-github:release` command.

## Where the CLI version lives

The installable CLI package is versioned in standard Python packaging metadata, and the package also keeps a runtime `__version__` constant.

From `pyproject.toml`:

```toml
[project]
name = "myk-claude-tools"
version = "1.7.2"
description = "CLI utilities for Claude Code plugins"
```

From `myk_claude_tools/__init__.py`:

```python
"""myk-claude-tools: CLI utilities for Claude Code plugins."""

__version__ = "1.7.2"
```

The root CLI exposes a version flag through Click:

```python
@click.group()
@click.version_option()
def cli() -> None:
    """CLI utilities for Claude Code plugins."""
```

In practice, that means a release of the CLI should keep `pyproject.toml` and `myk_claude_tools/__init__.py` aligned.

## Where plugin versions live

Each plugin has its own manifest under `plugins/*/.claude-plugin/plugin.json`.

From `plugins/myk-github/.claude-plugin/plugin.json`:

```json
{
  "name": "myk-github",
  "version": "1.4.3",
  "description": "GitHub operations for Claude Code - PR reviews, releases, review handling, and CodeRabbit rate limits",
  "author": {
    "name": "myk-org"
  },
  "repository": "https://github.com/myk-org/claude-code-config",
  "license": "MIT",
  "keywords": ["github", "pr-review", "refine-review", "release", "code-review", "coderabbit", "rate-limit"]
}
```

From `plugins/myk-review/.claude-plugin/plugin.json`:

```json
{
  "name": "myk-review",
  "version": "1.4.3",
  "description": "Local code review and review database operations for Claude Code",
  "author": {
    "name": "myk-org"
  },
  "repository": "https://github.com/myk-org/claude-code-config",
  "license": "MIT",
  "keywords": ["code-review", "local", "database", "analytics"]
}
```

From `plugins/myk-acpx/.claude-plugin/plugin.json`:

```json
{
  "name": "myk-acpx",
  "version": "1.4.6",
  "description": "Multi-agent prompt execution via acpx (Agent Client Protocol)",
  "author": { "name": "myk-org" },
  "repository": "https://github.com/myk-org/claude-code-config",
  "license": "MIT",
  "keywords": ["acpx", "acp", "multi-agent", "codex", "gemini", "cursor", "copilot"]
}
```

The repository also publishes plugin metadata through the root marketplace manifest:

```json
{
  "name": "myk-org",
  "owner": {
    "name": "myk-org"
  },
  "plugins": [
    {
      "name": "myk-github",
      "source": "./plugins/myk-github",
      "description": "GitHub operations - PR reviews, releases, review handling, CodeRabbit rate limits",
      "version": "1.7.2"
    },
    {
      "name": "myk-review",
      "source": "./plugins/myk-review",
      "description": "Local code review and review database operations",
      "version": "1.7.2"
    },
    {
      "name": "myk-acpx",
      "source": "./plugins/myk-acpx",
      "description": "Multi-agent prompt execution via acpx (Agent Client Protocol)",
      "version": "1.7.2"
    }
  ]
}
```

> **Warning:** In the current repository state, the plugin manifests and the marketplace manifest do not match. The per-plugin `plugin.json` files use `1.4.3` / `1.4.6`, while `.claude-plugin/marketplace.json` uses `1.7.2` for all three plugins. The release helpers do not reconcile this automatically, so maintainers need to decide which version numbers should move for a given release and update those files deliberately.

## What `release detect-versions` can find

The release tooling scans from the current working directory, so run it from the repository root.

Supported root-level version files are defined in `myk_claude_tools/release/detect_versions.py`:

```python
_ROOT_SCANNERS: list[tuple[str, Callable[[Path], str | None], str]] = [
    ("pyproject.toml", _parse_pyproject_toml, "pyproject"),
    ("package.json", _parse_package_json, "package_json"),
    ("setup.cfg", _parse_setup_cfg, "setup_cfg"),
    ("Cargo.toml", _parse_cargo_toml, "cargo"),
    ("build.gradle", _parse_gradle, "gradle"),
    ("build.gradle.kts", _parse_gradle, "gradle"),
]
```

It also walks the tree looking for Python files named `__init__.py` or `version.py` that contain a `__version__ = "..."` assignment:

```python
def _find_python_version_files(root: Path) -> list[VersionFile]:
    """Find Python files containing __version__ assignments."""
    results: list[VersionFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for name in filenames:
            if name not in ("__init__.py", "version.py"):
                continue
            filepath = Path(dirpath) / name
            version = _parse_python_version(filepath)
            if version:
                results.append(
                    VersionFile(
                        path=filepath.relative_to(root).as_posix(),
                        current_version=version,
                        file_type="python_version",
                    )
                )
    return results
```

The scanner skips common generated and dependency directories such as `.venv`, `node_modules`, `.tox`, `dist`, `build`, and `target`.

For this repository layout, the built-in detector will typically find:

- `pyproject.toml`
- `myk_claude_tools/__init__.py`

It will not find:

- `plugins/*/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

That limitation is important: the release helper automates the CLI version files, not the plugin manifests.

The command emits JSON with a simple shape:

```python
output = {
    "version_files": [r.to_dict() for r in results],
    "count": len(results),
}
print(json.dumps(output, indent=2))
```

The plugin release workflow expects these fields:

- `version_files[].path`
- `version_files[].current_version`
- `count`

## What `release bump-version` actually does

`myk-claude-tools release bump-version` updates detected version files in place. It does not create commits, tags, or releases.

The command validates the new version string before doing any file changes:

```python
new_version = new_version.strip()
if not new_version or any(ch in new_version for ch in ("\n", "\r")):
    return BumpResult(
        status="failed",
        error="Invalid version: must be a non-empty single-line string.",
    )
if new_version.startswith("v") or new_version.startswith("V"):
    return BumpResult(
        status="failed",
        error=f"Invalid version: '{new_version}' should not start with 'v'. Use '{new_version[1:]}' instead.",
    )
```

A few details matter in day-to-day maintenance:

- writes are atomic, using a temporary file and rename
- existing file permissions are preserved when possible
- `pyproject.toml` updates are scoped to the `[project]` section only
- `setup.cfg` updates are scoped to `[metadata]` only
- dynamic `setup.cfg` versions such as `attr:` and `file:` are intentionally skipped
- if you pass `--files`, every listed path must match a detected file or the command fails before modifying anything

From `myk_claude_tools/release/commands.py`:

```python
@release.command("bump-version")
@click.argument("version")
@click.option("--files", multiple=True, help="Specific files to update (can be repeated)")
def release_bump_version(version: str, files: tuple[str, ...]) -> None:
    """Update version strings in detected version files."""
    bump_run(version, list(files) if files else None)
```

> **Warning:** `bump-version` expects the bare version number, such as `1.8.0`. `release create` expects a Git tag, such as `v1.8.0`. That `v` difference is intentional and easy to get wrong.

## What `release info` checks before a release

`myk-claude-tools release info` is the pre-flight command. It uses both `git` and `gh`, and it fails early if either dependency is missing.

The release subcommands are registered like this:

```python
@release.command("info")
@click.option("--repo", help="Repository in owner/repo format")
@click.option("--target", help="Target branch for release (overrides default branch check)")
@click.option("--tag-match", help="Glob pattern to filter tags (e.g., 'v2.10.*')")
def release_info(repo: str | None, target: str | None, tag_match: str | None) -> None:
    """Fetch release validation info and commits since last tag."""
    info_run(repo, target=target, tag_match=tag_match)
```

`release info` validates:

- that you are on the effective target branch
- that the working tree is clean
- that `git fetch origin <target>` succeeds
- that the local branch is neither ahead of nor behind `origin/<target>`

It also supports automatic version-branch behavior. If the current branch is named like `v2.10`, the tool infers both the release target and a tag filter:

```python
def _detect_version_branch(current_branch: str) -> tuple[str | None, str | None]:
    """Auto-detect version branch and infer tag match pattern."""
    match = _VERSION_BRANCH_RE.match(current_branch)
    if match:
        version_prefix = match.group(1)
        return current_branch, f"v{version_prefix}.*"
    return None, None
```

That makes it easier to manage release lines such as `v2.10` without passing `--target` and `--tag-match` every time.

If validation fails, the tool returns early with validation data and skips the more expensive tag and commit collection. If validation passes, it reports:

- repository metadata
- validation results
- the most recent tag
- recent tags
- commits since the last tag
- whether this would be the first release

## What `release create` publishes

`myk-claude-tools release create` is a thin wrapper around `gh release create`. It expects:

- a repository in `owner/repo` format
- a tag such as `v1.8.0`
- a changelog file path

From `myk_claude_tools/release/create.py`:

```python
cmd = [
    "gh",
    "release",
    "create",
    tag,
    "--repo",
    owner_repo,
    "--notes-file",
    changelog_file,
    "--title",
    title.strip() if title and title.strip() else tag,
]

if target:
    cmd.extend(["--target", target])

if prerelease:
    cmd.append("--prerelease")

if draft:
    cmd.append("--draft")
```

A few useful details:

- `owner_repo` must match `owner/repo`
- the changelog file must already exist
- `--target` is passed straight through to `gh release create`
- `--draft` and `--prerelease` are supported
- tags that do not match `vX.Y.Z` style semver are warned about, but not blocked

> **Tip:** Because this command shells out to `gh`, the actual release publishing behavior is whatever `gh release create` does with the tag and target you provide. The helper mainly adds validation and structured JSON output around that call.

## Maintainer command reference

The release flow in `plugins/myk-github/commands/release.md` uses these commands directly:

```bash
myk-claude-tools release info
myk-claude-tools release info --target <branch>
myk-claude-tools release info --target <branch> --tag-match <pattern>
myk-claude-tools release detect-versions
myk-claude-tools release bump-version <VERSION> --files <file1> --files <file2>
```

And for publishing:

```bash
myk-claude-tools release create {owner}/{repo} {tag} "$CHANGELOG_FILE" [--prerelease] [--draft] [--target {target_branch}]
```

The same command definition also recommends checking that the CLI is installed first:

```bash
myk-claude-tools --version
```

If it is missing:

```bash
uv tool install myk-claude-tools
```

## Recommended release workflow for this repository

A practical release for `claude-code-config` usually looks like this:

1. Confirm the installed CLI version with `myk-claude-tools --version`.
2. Run `myk-claude-tools release info` from the repository root.
3. Fix any validation failures before going further.
4. Run `myk-claude-tools release detect-versions` to see which files will be auto-updated.
5. Run `myk-claude-tools release bump-version <VERSION>` for the CLI version files.
6. Manually update plugin manifests and the marketplace manifest if your release should move those versions too.
7. Commit, tag, and push according to your normal git workflow.
8. Generate release notes and pass them to `myk-claude-tools release create`.
9. Verify the published GitHub release URL returned by the command.

For this repo specifically, step 6 matters because plugin version files are not part of automatic detection.

## Guided release flow with `/myk-github:release`

If you prefer a guided workflow, the `myk-github` plugin already defines one in `plugins/myk-github/commands/release.md`.

That command orchestrates these phases:

- validation with `release info`
- version discovery with `release detect-versions`
- changelog analysis
- user approval
- optional `release bump-version`
- branch creation, PR creation, and merge for the version bump
- final `release create`

It also includes a conditional `uv lock` step if a `uv.lock` file exists:

```bash
uv lock
git add uv.lock
```

This repository does not currently include `uv.lock`, but the workflow is built to handle projects that do.

> **Tip:** The slash command is the easiest way to follow the repo's intended release sequence, especially when you want the version bump to happen in a dedicated PR before the GitHub release is published.

## What the tests guarantee

The tests are a useful source of truth for what the release helpers support.

`tests/test_detect_versions.py` confirms that detection:

- reads `pyproject.toml`, `package.json`, `setup.cfg`, `Cargo.toml`, and Gradle files
- detects `__version__` in `__init__.py` and `version.py`
- skips excluded directories
- ignores malformed files
- ignores `setup.cfg` values that use `attr:` or `file:`
- only reads the correct section in multi-section files

`tests/test_bump_version.py` confirms that bumping:

- preserves unrelated file content
- only updates the intended section
- preserves indentation
- supports updating multiple files at once
- fails fast on partial `--files` mismatches
- reports skipped files cleanly when writes fail

When in doubt, treat those tests as the supported behavior of the release tooling.
