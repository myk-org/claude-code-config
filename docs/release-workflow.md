# Release Workflow

Releases in this repository are driven by two layers:

- `/myk-github:release` gives you the guided, end-to-end workflow.
- `myk-claude-tools release ...` provides the underlying CLI steps for validation, version detection, version bumping, and GitHub release creation.

The CLI is installed as `myk-claude-tools`:

```23:24:pyproject.toml
[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

> **Note:** This repository does not define a separate checked-in release pipeline in GitHub Actions. Release prep and publishing are driven by the plugin workflow, `git`, `gh`, and the `myk-claude-tools` CLI.

## What to use

For most releases, start with the guided slash command:

```text
/myk-github:release
/myk-github:release --dry-run
/myk-github:release --prerelease
/myk-github:release --draft
```

If you want to run the steps yourself, the CLI exposes these subcommands:

- `myk-claude-tools release info`
- `myk-claude-tools release detect-versions`
- `myk-claude-tools release bump-version`
- `myk-claude-tools release create`

> **Warning:** `/myk-github:release --dry-run` appears in the plugin workflow, but there is no matching `--dry-run` flag in the checked-in `myk-claude-tools release ...` CLI commands. Treat it as a workflow-level preview mode, not a standalone CLI option.

## 1. Validate the repository

The workflow starts with `myk-claude-tools release info`. This is the safety check that decides whether the repository is in a releasable state.

Use it like this:

```bash
myk-claude-tools release info
myk-claude-tools release info --target <branch>
myk-claude-tools release info --target <branch> --tag-match <pattern>
```

It validates three things before doing the more expensive release analysis:

- You are on the correct target branch.
- Your working tree is clean.
- Your local branch is fully synced with the remote.

```217:238:myk_claude_tools/release/info.py
def _perform_validations(default_branch: str, current_branch: str, target_branch: str | None = None) -> Validations:
    """Perform release prerequisite validations."""
    # 1. Default Branch Check
    effective_target = target_branch or default_branch
    on_target_branch = current_branch == effective_target

    # 2. Clean Working Tree Check
    working_tree_clean = True
    dirty_files = ""

    diff_code, _ = _run_command(["git", "diff", "--quiet"])
    cached_code, _ = _run_command(["git", "diff", "--cached", "--quiet"])

    if diff_code != 0 or cached_code != 0:
        working_tree_clean = False
        _, status_output = _run_command(["git", "status", "--porcelain"])
        if status_output:
            dirty_files = "\n".join(status_output.split("\n")[:10])

    # 3. Remote Sync Check
    fetch_code, _ = _run_command(["git", "fetch", "origin", effective_target, "--quiet"])
    fetch_successful = fetch_code == 0
```

When validation succeeds, the command prints structured JSON that includes repo metadata, validation results, the last tag, the recent matching tags, and the commit list:

```103:115:myk_claude_tools/release/info.py
return {
    "metadata": self.metadata.to_dict(),
    "validations": self.validations.to_dict(),
    "last_tag": self.last_tag,
    "all_tags": self.all_tags,
    "commits": [c.to_dict() for c in self.commits],
    "commit_count": self.commit_count,
    "is_first_release": self.is_first_release,
    "target_branch": self.target_branch,
    "tag_match": self.tag_match,
}
```

> **Warning:** If validation fails, `release info` returns no commit list. That does not mean there is nothing to release. It means you need to fix the branch state first.

### Version-branch auto-detection

If you are on a maintenance branch named like `v2.10`, the tool auto-detects that branch as the release target and scopes tag lookup to the same release line.

```201:214:myk_claude_tools/release/info.py
def _detect_version_branch(current_branch: str) -> tuple[str | None, str | None]:
    """Auto-detect version branch and infer tag match pattern.

    If the current branch matches vMAJOR.MINOR (e.g., v2.10), returns
    the branch as the target and a glob pattern to scope tag discovery.
    """
    match = _VERSION_BRANCH_RE.match(current_branch)
    if match:
        version_prefix = match.group(1)
        return current_branch, f"v{version_prefix}.*"
    return None, None
```

That means a branch such as `v2.10` automatically uses `v2.10.*` when looking for the most recent relevant tag.

> **Tip:** If your branch naming does not follow `vMAJOR.MINOR`, pass `--target` and `--tag-match` explicitly.

## 2. Analyze commits and choose the bump

`myk-claude-tools release info` returns raw commit data. The guided slash command is the part that interprets those commits into a proposed version bump and changelog.

The release workflow definition is explicit about that step:

```75:83:plugins/myk-github/commands/release.md
### Phase 3: Changelog Analysis

Parse commits from Phase 1 output and categorize by conventional commit type:

- Breaking Changes (MAJOR)
- Features (MINOR)
- Bug Fixes, Docs, Maintenance (PATCH)

Determine version bump and generate changelog.
```

In practice, that means:

- The CLI gathers commit history since the last matching tag.
- The slash command groups those commits into breaking changes, features, and patch-level changes.
- The workflow then proposes `major`, `minor`, or `patch`.

If the repository has no matching tag yet, the tool treats it as a first release and works from the full history.

> **Note:** Commit analysis is a workflow responsibility. The checked-in CLI does not have a separate `analyze` or `recommend-version` subcommand.

> **Note:** The commit collection helper reads up to 100 commits from the release range. If your next release spans more than that, review the result before relying on the generated changelog.

## 3. Detect which version files can be updated

Next, the workflow runs:

```bash
myk-claude-tools release detect-versions
```

This command prints JSON with the detected files and a total count:

```205:212:myk_claude_tools/release/detect_versions.py
results = detect_version_files()
output = {
    "version_files": [r.to_dict() for r in results],
    "count": len(results),
}
print(json.dumps(output, indent=2))
```

The supported root-level version files are defined directly in code:

```167:174:myk_claude_tools/release/detect_versions.py
_ROOT_SCANNERS: list[tuple[str, Callable[[Path], str | None], str]] = [
    ("pyproject.toml", _parse_pyproject_toml, "pyproject"),
    ("package.json", _parse_package_json, "package_json"),
    ("setup.cfg", _parse_setup_cfg, "setup_cfg"),
    ("Cargo.toml", _parse_cargo_toml, "cargo"),
    ("build.gradle", _parse_gradle, "gradle"),
    ("build.gradle.kts", _parse_gradle, "gradle"),
]
```

The detector also searches for Python `__version__` assignments in files named `__init__.py` and `version.py`, while skipping common generated or environment directories such as `.venv`, `node_modules`, `dist`, `build`, and `target`.

Supported version sources are:

- `pyproject.toml` via `project.version`
- `package.json` via top-level `version`
- `setup.cfg` via static `[metadata] version`
- `Cargo.toml` via `[package] version`
- `build.gradle` and `build.gradle.kts` via `version`
- `__init__.py` and `version.py` via `__version__`

This repository itself uses `pyproject.toml` for the CLI package version:

```1:4:pyproject.toml
[project]
name = "myk-claude-tools"
version = "1.7.2"
description = "CLI utilities for Claude Code plugins"
```

> **Note:** `setup.cfg` values that use `attr:` or `file:` are intentionally skipped. Only static version values are detected and bumped.

> **Note:** Automatic version detection does not scan `.claude-plugin/plugin.json`. In this repository, files such as `plugins/myk-github/.claude-plugin/plugin.json` contain their own version field, but they are not part of the supported detection list above.

## 4. Review the proposal before anything is changed

If version files are found, the guided workflow shows you:

- The proposed new version
- The files it plans to update
- A changelog preview

You can then accept the proposal, override the bump type, exclude a file, or cancel.

```85:106:plugins/myk-github/commands/release.md
### Phase 4: User Approval

Display the proposed release information. If version files were detected in Phase 2,
include them in the approval prompt.

- 'yes' -- Proceed with proposed version and all listed files
- 'major/minor/patch' -- Override the version bump type
- 'exclude N' -- Exclude file by number from the version bump (e.g., 'exclude 2')
- 'no' -- Cancel the release
```

This approval step is important because version detection is intentionally conservative. The tool can find multiple valid version files, but you still control which ones actually get updated for the release.

## 5. Bump version files

When you confirm the version, the workflow runs `myk-claude-tools release bump-version`.

Typical usage looks like this:

```bash
myk-claude-tools release bump-version <VERSION>
myk-claude-tools release bump-version <VERSION> --files <file1> --files <file2>
```

A few rules matter here:

- Pass `1.2.0`, not `v1.2.0`.
- `--files` can be repeated to limit the update to a subset of detected files.
- Every file passed to `--files` must match a detected version file.
- The CLI rewrites files only. It does not create branches, commits, or PRs by itself.

The version string is validated strictly:

```217:227:myk_claude_tools/release/bump_version.py
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

If you use `--files`, the filter must match exactly:

```236:256:myk_claude_tools/release/bump_version.py
if files is not None:
    normalized_files = [Path(f).as_posix() for f in files]
    filtered = [vf for vf in detected if vf.path in normalized_files]
    if not filtered:
        available = [vf.path for vf in detected]
        return BumpResult(
            status="failed",
            error=f"None of the specified files were found in detected version files. Available: {available}",
        )
    matched_paths = {vf.path for vf in filtered}
    unmatched = [f for f in normalized_files if f not in matched_paths]
    if unmatched:
        available = [vf.path for vf in detected]
        return BumpResult(
            status="failed",
            error=(
                f"Some specified files were not found in detected version files."
                f" Unmatched: {unmatched}. Available: {available}"
            ),
        )
    detected = filtered
```

The result JSON distinguishes between `updated` files and `skipped` files, which lets the workflow stage only successful updates and tell you about anything that was skipped.

> **Tip:** Use `--files` when you want to keep automatic detection but narrow the actual bump to a smaller set of version files.

## 6. Prepare the release with a PR

If version files were updated, the guided workflow does not release directly from that local state. It creates a dedicated bump branch, commits the updated files, opens a PR, merges it, and then syncs the target branch before creating the GitHub release.

The documented flow is:

```bash
BUMP_BRANCH="chore/bump-version-<VERSION>-$(date +%s)"
git checkout -b "$BUMP_BRANCH"
git add <updated-files>

uv lock
git add uv.lock

git commit -m "chore: bump version to <VERSION>"
git push -u origin "$BUMP_BRANCH"

PR_URL=$(gh pr create --title "chore: bump version to <VERSION>" \
  --body "Bump version to <VERSION>" --base <target_branch>)

gh pr merge --merge --admin --delete-branch
```

A few practical details are worth knowing:

- The timestamp suffix on `BUMP_BRANCH` avoids collisions with earlier bump attempts.
- `uv lock` is only relevant when `uv.lock` exists at the repo root.
- After merge, the workflow switches back to the target branch and pulls the latest changes before continuing.

> **Warning:** The workflow attempts `gh pr merge --merge --admin --delete-branch`. If you do not have admin privileges, expect the documented fallback: merge the PR manually, then confirm before the release continues.

## 7. Create the GitHub release

Once the branch is current and the changelog is ready, the workflow writes the release notes to a temporary file and calls `release create`.

The workflow’s handoff looks like this:

```bash
CHANGELOG_FILE=$(mktemp /tmp/claude-release-XXXXXX.md)
trap "rm -f $CHANGELOG_FILE" EXIT

cat > "$CHANGELOG_FILE" << 'EOF'
<changelog content from Phase 3>
EOF

myk-claude-tools release create {owner}/{repo} {tag} "$CHANGELOG_FILE" [--prerelease] [--draft] [--target {target_branch}]
```

You can also run the CLI directly if you already have a changelog file:

```bash
myk-claude-tools release create <owner/repo> <tag> <changelog-file>
myk-claude-tools release create <owner/repo> <tag> <changelog-file> --prerelease
myk-claude-tools release create <owner/repo> <tag> <changelog-file> --draft --target <branch>
```

The CLI forwards the main release flags directly to `gh release create`:

```144:165:myk_claude_tools/release/create.py
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

The command expects:

- A repository in `owner/repo` format
- A release tag
- An existing changelog file
- Optional `--prerelease`, `--draft`, `--target`, and `--title` flags

It also checks whether the tag looks like semantic versioning:

```76:79:myk_claude_tools/release/create.py
def _is_semver_tag(tag: str) -> bool:
    """Check if tag follows semantic versioning format (vX.Y.Z)."""
    pattern = r"^v[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$"
```

> **Warning:** Non-semver tags are warned about, not blocked. `release create` can still proceed if the tag does not match `vX.Y.Z`.

## End-to-end summary

A typical guided release looks like this:

1. Run `/myk-github:release`.
2. The workflow calls `myk-claude-tools release info` to validate the repo and collect commits since the last matching tag.
3. It analyzes those commits to propose a `major`, `minor`, or `patch` bump and drafts the changelog.
4. It calls `myk-claude-tools release detect-versions` to discover bumpable version files.
5. It asks you to approve the proposed version, exclude files, override the bump type, or cancel.
6. If files need updating, it runs `myk-claude-tools release bump-version ...`, creates a PR, merges it, and syncs the target branch.
7. It writes the changelog to a temporary file and calls `myk-claude-tools release create ...`.
8. GitHub creates the release, optionally as a prerelease or draft.

That split is intentional:

- The CLI handles validation, JSON output, version-file discovery, version rewriting, and GitHub release creation.
- The slash command handles the interactive decisions, commit interpretation, changelog planning, and PR orchestration.
