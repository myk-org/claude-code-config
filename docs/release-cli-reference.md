# Release CLI Reference

`myk-claude-tools release` is the release-focused command group in this repository. It gives you four building blocks:

- `info` checks whether the repository is ready for a release and lists commits since the last matching tag
- `detect-versions` finds version files the tool knows how to update
- `bump-version` rewrites those files to a new version
- `create` publishes the GitHub release from a changelog file

The CLI is installed as the `myk-claude-tools` command and requires Python 3.10+:

```7:24:pyproject.toml
requires-python = ">=3.10"
# ... other project metadata ...
[project.scripts]
myk-claude-tools = "myk_claude_tools.cli:main"
```

## At A Glance

| Command | What it does | External tools |
| --- | --- | --- |
| `release info` | Validates branch state, working tree, and remote sync, then returns tags and commits | `git`, `gh` |
| `release detect-versions` | Scans the current directory for known version files | None |
| `release bump-version` | Updates detected version files to a new version | None |
| `release create` | Creates a GitHub release from a changelog file | `gh` |

> **Note:** All four commands print JSON to stdout. `release info`, `release bump-version`, and `release create` exit with status code `1` on failure. `release detect-versions` reports “nothing found” with `"count": 0` instead of failing.

## `myk-claude-tools release info`

Use `release info` first. It tells you whether the current checkout is in a releasable state, and if it is, it returns the last tag and the commits that would be included in the release.

Syntax: `myk-claude-tools release info [--repo OWNER/REPO] [--target BRANCH] [--tag-match GLOB]`

Example commands used by the project release workflow:

```35:48:plugins/myk-github/commands/release.md
myk-claude-tools release info --target <branch>

myk-claude-tools release info --target <branch> --tag-match <pattern>

myk-claude-tools release info
```

### Inputs

| Input | Required | Description |
| --- | --- | --- |
| `--repo OWNER/REPO` | No | Repository in `owner/repo` format. If omitted, the command asks `gh` for the current repository. |
| `--target BRANCH` | No | Branch that must match the current checkout for release validation to pass. |
| `--tag-match GLOB` | No | Glob used to filter tags, such as `v2.10.*`. This is a glob, not a regular expression. |

### How target branch selection works

- If you pass `--target`, that branch becomes the release target.
- If you do not pass `--target` and your current branch looks like `v2.10`, that branch becomes the target automatically.
- In that auto-detected version-branch case, `tag_match` also defaults to `v2.10.*` unless you already provided `--tag-match`.
- Otherwise, the target branch is the repository default branch from GitHub, with a fallback to `main`.

> **Note:** The version-branch shortcut is designed for branch names in the `vMAJOR.MINOR` format, such as `v2.10`.

### What it validates

Before it gathers tags or commits, `release info` checks all of the following:

- You are on the effective target branch.
- The working tree is clean, including both staged and unstaged changes.
- `git fetch origin <target>` succeeds.
- The local branch has no unpushed commits relative to `origin/<target>`.
- The local branch is not behind `origin/<target>`.

> **Note:** Remote sync checks are always done against `origin/<target>`. If your release flow uses another remote, this command will not follow it automatically.

> **Warning:** If any validation fails, `release info` does not return partial history. In that case, `last_tag` is `null`, `all_tags` and `commits` are empty, `commit_count` is `0`, and `is_first_release` is `null`.

> **Tip:** `all_tags` is limited to the 10 most recent matching tags, and `commits` is limited to 100 entries. This command is meant for release preparation, not full-history export.

### Success JSON

Top-level fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `metadata` | object | Repository metadata: `owner`, `repo`, `current_branch`, and `default_branch`. |
| `validations` | object | Detailed validation results. |
| `last_tag` | `string \| null` | Most recent matching tag, or `null` if none was found. |
| `all_tags` | `string[]` | Recent matching tags, sorted by version, newest first. |
| `commits` | `object[]` | Commits since `last_tag`, or from `HEAD` if this is the first release. Each item contains `hash`, `short_hash`, `subject`, `body`, `author`, and `date`. |
| `commit_count` | `number` | Number of commit objects returned. |
| `is_first_release` | `boolean \| null` | `true` if no matching tag exists, `false` otherwise, and `null` when validation failed before history collection. |
| `target_branch` | `string` | The effective target branch after applying defaults and auto-detection. |
| `tag_match` | `string \| null` | The effective tag filter, whether explicit or auto-detected. |

`validations` fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `on_target_branch` | `boolean` | Whether `current_branch` matches the effective target branch. |
| `default_branch` | `string` | Repository default branch. |
| `current_branch` | `string` | Current local branch name. |
| `working_tree_clean` | `boolean` | Whether both staged and unstaged changes are absent. |
| `dirty_files` | `string` | Up to the first 10 `git status --porcelain` lines when the tree is dirty; empty string when clean. |
| `fetch_successful` | `boolean` | Whether `git fetch origin <target>` succeeded. |
| `synced_with_remote` | `boolean` | Whether the local target branch is neither ahead of nor behind `origin/<target>`. |
| `unpushed_commits` | `number` | Number of commits local is ahead of `origin/<target>`. |
| `behind_remote` | `number` | Number of commits local is behind `origin/<target>`. |
| `all_passed` | `boolean` | Final release-readiness result. |

### Failure JSON

On failure, `release info` returns a bare error object:

| Field | Type | Meaning |
| --- | --- | --- |
| `error` | `string` | Reason the command failed, such as missing `git` or `gh`, an invalid repository format, an invalid target branch, or an invalid tag-match pattern. |

> **Tip:** `release info` is the only release command that fails with `{"error": "..."}` instead of `{"status": "failed", "error": "..."}`. If you are scripting the CLI, handle it separately.

## `myk-claude-tools release detect-versions`

Use `release detect-versions` to see which files the CLI can version-bump automatically in the current directory.

Syntax: `myk-claude-tools release detect-versions`

Example from the project workflow:

```62:64:plugins/myk-github/commands/release.md
myk-claude-tools release detect-versions
```

### What it scans

| Source | What it reads | Output `type` |
| --- | --- | --- |
| `pyproject.toml` | `project.version` | `pyproject` |
| `package.json` | Top-level `version` | `package_json` |
| `setup.cfg` | `[metadata] version` only | `setup_cfg` |
| `Cargo.toml` | `[package] version` | `cargo` |
| `build.gradle` | `version` assignment | `gradle` |
| `build.gradle.kts` | `version` assignment | `gradle` |
| `__init__.py` | `__version__ = "..."` | `python_version` |
| `version.py` | `__version__ = "..."` | `python_version` |

A few important details:

- Recursive scanning is only used for `__init__.py` and `version.py`.
- `setup.cfg` is only detected when the version is static. Dynamic forms like `attr:` and `file:` are skipped.
- The command skips hidden directories and common generated or dependency directories such as `.git`, `.venv`, `node_modules`, `dist`, `build`, `target`, and cache folders.

> **Tip:** Run `detect-versions` from the repository root. The returned `version_files[].path` values are repo-relative paths, and they are the exact values you should feed back into `release bump-version --files`.

> **Note:** Malformed or unsupported files are skipped rather than causing the whole command to fail. If nothing matches, you get `"count": 0`.

### JSON output

| Field | Type | Meaning |
| --- | --- | --- |
| `version_files` | `object[]` | Detected files. Each item contains `path`, `current_version`, and `type`. |
| `count` | `number` | Number of detected version files. |

Each `version_files[]` item contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `path` | `string` | Repo-relative path such as `pyproject.toml` or `mypackage/__init__.py`. |
| `current_version` | `string` | The version string currently found in that file. |
| `type` | `string` | One of `pyproject`, `package_json`, `setup_cfg`, `cargo`, `gradle`, or `python_version`. |

## `myk-claude-tools release bump-version`

Use `release bump-version` to rewrite version strings in the files discovered by `release detect-versions`.

Syntax: `myk-claude-tools release bump-version VERSION [--files PATH]...`

Example from the project workflow:

```118:120:plugins/myk-github/commands/release.md
myk-claude-tools release bump-version <VERSION> --files <file1> --files <file2>
```

### Inputs

| Input | Required | Description |
| --- | --- | --- |
| `VERSION` | Yes | New version string, such as `1.2.0`. It must be non-empty, single-line, and must not start with `v` or `V`. |
| `--files PATH` | No | Repeatable filter. Limits the update to specific files returned by `release detect-versions`. If omitted, all detected version files are updated. |

> **Warning:** Pass the bare version number, such as `1.2.0`, not `v1.2.0`. The command rejects a leading `v` or `V`.

> **Warning:** If you use `--files`, every listed file must match the output of `release detect-versions`. One bad path makes the whole command fail before any file is rewritten.

### What gets updated

| Detected `type` | Update behavior |
| --- | --- |
| `pyproject` | Rewrites `version` inside the `[project]` section only. |
| `package_json` | Rewrites the top-level `version` field. |
| `setup_cfg` | Rewrites `version` inside `[metadata]` only. Dynamic `attr:` and `file:` versions are skipped. |
| `cargo` | Rewrites `version` inside `[package]` only. |
| `gradle` | Rewrites the first matching `version` assignment. |
| `python_version` | Rewrites the first matching `__version__ = "..."` assignment. |

### Behavior

- The command uses the same file-detection logic as `release detect-versions`.
- It only updates files that are already recognized by that detector.
- Rewrites are done atomically, so a file is written through a temporary file and then replaced.
- The command does not run `git add`, `git commit`, or any other Git operation.
- A run can succeed even when some files are skipped. It only fails when zero files were updated, or when input validation fails.

> **Tip:** For automation, treat `updated[]` as the source of truth for what actually changed. `skipped[]` tells you which files were ignored and why.

### JSON output

| Field | Appears when | Type | Meaning |
| --- | --- | --- | --- |
| `status` | Always | `string` | `success` or `failed`. |
| `version` | Success | `string` | The new version that was written. |
| `updated` | Success | `object[]` | Files that were updated. Each item contains `path`, `old_version`, and `new_version`. |
| `skipped` | Success or some failures | `object[]` | Files that were not updated. Each item contains `path` and `reason`. |
| `error` | Failure | `string` | Why the command failed, such as an invalid version string, no detected version files, unmatched `--files`, or no files updated. |

`updated[]` items:

| Field | Type | Meaning |
| --- | --- | --- |
| `path` | `string` | Updated file path. |
| `old_version` | `string` | Version found before the rewrite. |
| `new_version` | `string` | Version written to the file. |

`skipped[]` items:

| Field | Type | Meaning |
| --- | --- | --- |
| `path` | `string` | Skipped file path. |
| `reason` | `string` | Reason the file was skipped, such as an unrecognized pattern or I/O error. |

## `myk-claude-tools release create`

Use `release create` to publish the GitHub release once you have a final tag and a changelog file.

Syntax: `myk-claude-tools release create OWNER/REPO TAG CHANGELOG_FILE [--prerelease] [--draft] [--target BRANCH] [--title TEXT]`

Example from the project workflow:

```197:204:plugins/myk-github/commands/release.md
CHANGELOG_FILE=$(mktemp /tmp/claude-release-XXXXXX.md)
trap "rm -f $CHANGELOG_FILE" EXIT

cat > "$CHANGELOG_FILE" << 'EOF'
<changelog content from Phase 3>
EOF

myk-claude-tools release create {owner}/{repo} {tag} "$CHANGELOG_FILE" [--prerelease] [--draft] [--target {target_branch}]
```

### Inputs

| Input | Required | Description |
| --- | --- | --- |
| `OWNER/REPO` | Yes | Repository in `owner/repo` format. |
| `TAG` | Yes | Release tag, usually something like `v1.2.0`. |
| `CHANGELOG_FILE` | Yes | Path to a file containing the release notes. The file must already exist. |
| `--prerelease` | No | Marks the release as a prerelease. |
| `--draft` | No | Creates the release as a draft. |
| `--target BRANCH` | No | Target branch passed through to GitHub. |
| `--title TEXT` | No | Release title. If omitted or blank, the tag is used as the title. |

### Behavior

- The command validates that `OWNER/REPO` looks like `owner/repo`.
- It validates that `CHANGELOG_FILE` exists before calling `gh`.
- It runs `gh release create` with a 300-second timeout.
- If `gh` prints a release URL, that URL is returned. If not, the CLI constructs the standard GitHub release URL from the repo and tag.
- The success payload echoes `prerelease` and `draft`, but it does not echo `target` or `title`.

> **Warning:** `release create` has real side effects. It creates a GitHub release in the repository named by `OWNER/REPO` using your current `gh` authentication and GitHub context.

> **Note:** A tag that does not look like `vX.Y.Z` or `vX.Y.Z-suffix` only triggers a warning on stderr. The command still attempts to create the release.

> **Tip:** `release create` is independent. If you already have a tag and a changelog file, you can use it without running the other release commands first.

### JSON output

| Field | Appears when | Type | Meaning |
| --- | --- | --- | --- |
| `status` | Always | `string` | `success` or `failed`. |
| `tag` | Success | `string` | Tag used for the release. |
| `url` | Success | `string` | GitHub release URL, either extracted from `gh` output or constructed by the CLI. |
| `prerelease` | Success | `boolean` | Whether the release was created as a prerelease. |
| `draft` | Success | `boolean` | Whether the release was created as a draft. |
| `error` | Failure | `string` | Why the command failed, such as a missing `gh` installation, invalid repo format, missing changelog file, or `gh release create` failure. |
