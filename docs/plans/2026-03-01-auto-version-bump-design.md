# Design: Auto-Detect and Update Version Files During Release

**Issue:** #128
**Date:** 2026-03-01
**Status:** Approved

## Problem

The `/myk-github:release` plugin creates GitHub releases with changelog generation
but does not update version numbers in project files.
Version bumps must be done manually before creating a release,
which is error-prone and easy to forget.

## Key Constraint

This feature must be **generic** --- it works in any repository
where a user runs `/myk-github:release`, not just this project.
The scanner detects whatever universal version files exist in the target repo.

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Where does detection live? | CLI tool (`myk-claude-tools`) | Testable, reusable, follows existing pattern |
| When does bumping happen? | Before tag/release creation | Version bump commit is part of the release, clean history |
| Who updates files? | CLI tool | Deterministic, reliable, testable |
| Who commits? | Plugin prompt | Flexible commit message, plugin controls git flow |
| File selection? | Per-file confirmation | User can exclude specific files |
| Scan scope? | Universal standards only | No project-specific files (plugin.json, marketplace.json) |

## New CLI Commands

### `myk-claude-tools release detect-versions`

Scans the current repository for version files using well-known patterns.

**Supported file patterns:**

| File | Version Pattern | Ecosystem |
|---|---|---|
| `pyproject.toml` | `version = "X.Y.Z"` | Python |
| `package.json` | `"version": "X.Y.Z"` | Node.js |
| `setup.cfg` | `version = X.Y.Z` | Python (legacy) |
| `Cargo.toml` | `version = "X.Y.Z"` | Rust |
| `build.gradle` / `build.gradle.kts` | `version = 'X.Y.Z'` or `version "X.Y.Z"` | Java/Kotlin |
| `**/__init__.py` with `__version__` | `__version__ = "X.Y.Z"` | Python modules |
| `**/version.py` with `__version__` | `__version__ = "X.Y.Z"` | Python modules |

**Output (JSON to stdout):**

```json
{
  "version_files": [
    {
      "path": "pyproject.toml",
      "current_version": "1.1.7",
      "type": "pyproject"
    },
    {
      "path": "package.json",
      "current_version": "1.1.7",
      "type": "package_json"
    }
  ],
  "count": 2
}
```

If no version files are found:

```json
{
  "version_files": [],
  "count": 0
}
```

### `myk-claude-tools release bump-version <version> [--files file1 file2 ...]`

Updates version strings in detected version files.

**Arguments:**

- `<version>` (required): The new version string (e.g., `1.2.0`, without `v` prefix)
- `--files` (optional): Specific file paths to update. If omitted, updates all detected version files.

**Output (JSON to stdout):**

```json
{
  "status": "success",
  "version": "1.2.0",
  "updated": [
    {
      "path": "pyproject.toml",
      "old_version": "1.1.7",
      "new_version": "1.2.0"
    }
  ],
  "skipped": []
}
```

On error:

```json
{
  "status": "failed",
  "error": "No version files found. Run 'detect-versions' first."
}
```

## Updated Plugin Flow (`release.md`)

```text
Phase 1: Validation (unchanged)
  → myk-claude-tools release info

Phase 2: Version Detection (NEW)
  → myk-claude-tools release detect-versions
  → Present found files to user

Phase 3: Changelog Analysis (was Phase 2)
  → Parse commits, categorize, determine version bump

Phase 4: User Approval (was Phase 3, enhanced)
  → Show proposed version + changelog + detected version files
  → User can: approve, override version, exclude files, cancel

Phase 5: Bump Version (NEW)
  → myk-claude-tools release bump-version <version> [--files ...]
  → git add + commit + push the changed files

Phase 6: Create Release (was Phase 4)
  → myk-claude-tools release create ...

Phase 7: Summary (was Phase 5)
  → Display release URL
```

### Phase 4 User Approval (enhanced)

The approval step now shows:

```text
Proposed version: v1.2.0 (minor bump)

Version files to update:
  [1] pyproject.toml (1.1.7 → 1.2.0)
  [2] package.json (1.1.7 → 1.2.0)

Changelog:
  ## Features
  - feat: auto-detect version files (#128)
  ...

Options:
  - 'yes' — Proceed with above
  - 'major/minor/patch' — Override version bump
  - 'exclude 2' — Exclude file #2 from version bump
  - 'no' — Cancel
```

### Phase 5 Version Bump (new)

After user approval:

1. Run `myk-claude-tools release bump-version <version> --files <confirmed-files>`
2. Stage changed files: `git add <files>`
3. Commit: `git commit -m "chore: bump version to <version>"`
4. Push: `git push`

## Code Structure

New files in `myk_claude_tools/release/`:

```text
myk_claude_tools/release/
├── __init__.py          (existing)
├── commands.py          (existing, add 2 new commands)
├── info.py              (existing, unchanged)
├── create.py            (existing, unchanged)
├── detect_versions.py   (NEW - version file detection)
└── bump_version.py      (NEW - version file updating)
```

New test files:

```text
tests/
├── test_detect_versions.py   (NEW)
└── test_bump_version.py      (NEW)
```

## Detection Logic (`detect_versions.py`)

1. Walk the repository root directory
2. For each supported file pattern, check if the file exists
3. Parse the file to extract the current version string using regex
4. For `**/__init__.py` and `**/version.py`, search recursively but skip common non-project dirs (`.git`, `node_modules`, `.venv`, `__pycache__`, etc.)
5. Return list of found version files with paths, current versions, and types

## Bump Logic (`bump_version.py`)

1. Accept target version and optional file list
2. If no file list given, run detection to find all version files
3. For each file, read content, replace version string using type-specific regex, write back
4. Return results JSON with old/new versions per file

## Testing Strategy

Unit tests using temporary directories with sample version files:

- `test_detect_versions.py`:
  - Test detection of each file type individually
  - Test repo with multiple version file types
  - Test repo with no version files (empty result)
  - Test that non-project directories are skipped
  - Test malformed files (missing version field) are handled gracefully

- `test_bump_version.py`:
  - Test version replacement for each file type
  - Test that only the version line changes, rest of file is preserved
  - Test `--files` filtering (only specified files updated)
  - Test error when no version files exist
  - Test version string edge cases (pre-release versions, etc.)
