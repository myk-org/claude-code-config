# Auto Version Bump Implementation Plan

<!-- markdownlint-disable MD024 -->

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `detect-versions` and `bump-version` CLI subcommands to `myk-claude-tools release`, and update the `/myk-github:release` plugin prompt to use them.

**Architecture:** Two new Python modules (`detect_versions.py` and `bump_version.py`)
in `myk_claude_tools/release/`, wired as Click subcommands.
The detection module scans the current directory for universal version file patterns
and returns JSON. The bump module reads detected files, replaces version strings,
and writes them back. The plugin prompt (`release.md`) gets two new phases
that call these commands.

**Tech Stack:** Python 3.10+, Click CLI framework, regex for version parsing, pytest for testing, `tmp_path` fixture for temp dirs.

---

## Implementation Tasks

### Task 1: Version Detection Module — Tests

**Files:**

- Create: `tests/test_detect_versions.py`

#### Step 1: Write all detection tests

```python
"""Tests for version file detection."""

import json
import textwrap
from pathlib import Path

import pytest

from myk_claude_tools.release.detect_versions import VersionFile, detect_version_files


class TestDetectVersionFiles:
    """Tests for detect_version_files function."""

    def test_pyproject_toml(self, tmp_path: Path) -> None:
        """Detect version in pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [project]
                name = "my-package"
                version = "1.2.3"
                description = "A package"
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "pyproject.toml"
        assert result[0].current_version == "1.2.3"
        assert result[0].file_type == "pyproject"

    def test_package_json(self, tmp_path: Path) -> None:
        """Detect version in package.json."""
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "my-pkg", "version": "2.0.1", "main": "index.js"})
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "package.json"
        assert result[0].current_version == "2.0.1"
        assert result[0].file_type == "package_json"

    def test_setup_cfg(self, tmp_path: Path) -> None:
        """Detect version in setup.cfg."""
        (tmp_path / "setup.cfg").write_text(
            textwrap.dedent("""\
                [metadata]
                name = my-package
                version = 0.9.0

                [options]
                packages = find:
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "setup.cfg"
        assert result[0].current_version == "0.9.0"
        assert result[0].file_type == "setup_cfg"

    def test_cargo_toml(self, tmp_path: Path) -> None:
        """Detect version in Cargo.toml."""
        (tmp_path / "Cargo.toml").write_text(
            textwrap.dedent("""\
                [package]
                name = "my-crate"
                version = "3.1.4"
                edition = "2021"
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "Cargo.toml"
        assert result[0].current_version == "3.1.4"
        assert result[0].file_type == "cargo"

    def test_build_gradle(self, tmp_path: Path) -> None:
        """Detect version in build.gradle."""
        (tmp_path / "build.gradle").write_text(
            textwrap.dedent("""\
                plugins {
                    id 'java'
                }
                version = '1.0.5'
                group = 'com.example'
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "build.gradle"
        assert result[0].current_version == "1.0.5"
        assert result[0].file_type == "gradle"

    def test_build_gradle_kts(self, tmp_path: Path) -> None:
        """Detect version in build.gradle.kts."""
        (tmp_path / "build.gradle.kts").write_text(
            textwrap.dedent("""\
                plugins {
                    kotlin("jvm") version "1.9.0"
                }
                version = "2.3.0"
                group = "com.example"
            """)
        )
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "build.gradle.kts"
        assert result[0].current_version == "2.3.0"
        assert result[0].file_type == "gradle"

    def test_init_py_version(self, tmp_path: Path) -> None:
        """Detect __version__ in __init__.py."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('__version__ = "0.5.0"\n')
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "mypackage/__init__.py"
        assert result[0].current_version == "0.5.0"
        assert result[0].file_type == "python_version"

    def test_version_py(self, tmp_path: Path) -> None:
        """Detect __version__ in version.py."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "version.py").write_text('__version__ = "1.0.0"\n')
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].path == "mypackage/version.py"
        assert result[0].current_version == "1.0.0"
        assert result[0].file_type == "python_version"

    def test_multiple_file_types(self, tmp_path: Path) -> None:
        """Detect multiple version files in one repo."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
        result = detect_version_files(tmp_path)
        assert len(result) == 2
        paths = {r.path for r in result}
        assert paths == {"pyproject.toml", "package.json"}

    def test_no_version_files(self, tmp_path: Path) -> None:
        """Return empty list when no version files exist."""
        (tmp_path / "README.md").write_text("# Hello")
        result = detect_version_files(tmp_path)
        assert result == []

    def test_skips_excluded_dirs(self, tmp_path: Path) -> None:
        """Skip __init__.py files in excluded directories."""
        venv_dir = tmp_path / ".venv" / "lib" / "somepackage"
        venv_dir.mkdir(parents=True)
        (venv_dir / "__init__.py").write_text('__version__ = "9.9.9"\n')

        node_dir = tmp_path / "node_modules" / "somepkg"
        node_dir.mkdir(parents=True)
        (node_dir / "__init__.py").write_text('__version__ = "8.8.8"\n')

        result = detect_version_files(tmp_path)
        assert result == []

    def test_malformed_pyproject_no_version(self, tmp_path: Path) -> None:
        """Handle pyproject.toml without a version field."""
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
                [project]
                name = "my-package"
                description = "No version here"
            """)
        )
        result = detect_version_files(tmp_path)
        assert result == []

    def test_malformed_package_json(self, tmp_path: Path) -> None:
        """Handle package.json without valid JSON."""
        (tmp_path / "package.json").write_text("not json at all")
        result = detect_version_files(tmp_path)
        assert result == []

    def test_init_py_without_version(self, tmp_path: Path) -> None:
        """Skip __init__.py files that don't have __version__."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("# Just a package\n")
        result = detect_version_files(tmp_path)
        assert result == []

    def test_version_file_dataclass(self) -> None:
        """Test VersionFile to_dict conversion."""
        vf = VersionFile(path="pyproject.toml", current_version="1.0.0", file_type="pyproject")
        d = vf.to_dict()
        assert d == {"path": "pyproject.toml", "current_version": "1.0.0", "type": "pyproject"}

    def test_gradle_double_quote(self, tmp_path: Path) -> None:
        """Detect version with double quotes in build.gradle."""
        (tmp_path / "build.gradle").write_text('version "4.0.0"\n')
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].current_version == "4.0.0"

    def test_prerelease_version(self, tmp_path: Path) -> None:
        """Detect pre-release version strings."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0-rc.1"\n')
        result = detect_version_files(tmp_path)
        assert len(result) == 1
        assert result[0].current_version == "1.0.0-rc.1"
```

#### Step 2: Run tests to verify they fail

Run: `cd /home/myakove/git/claude-code-config && uv run pytest tests/test_detect_versions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'myk_claude_tools.release.detect_versions'`

#### Step 3: Commit test file

```bash
git add tests/test_detect_versions.py
git commit -m "test: add tests for version file detection (issue #128)"
```

---

### Task 2: Version Detection Module — Implementation

**Files:**

- Create: `myk_claude_tools/release/detect_versions.py`

#### Step 1: Implement detect_versions module

```python
"""Detect version files in a repository.

Scans for well-known version file patterns across common ecosystems
(Python, Node.js, Rust, Java/Kotlin) and returns found files with
their current version strings.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Directories to skip when searching for Python __version__ files
EXCLUDED_DIRS = frozenset({
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    ".env",
    "env",
    "node_modules",
    "__pycache__",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".eggs",
    "site-packages",
    "target",
})


@dataclass
class VersionFile:
    """A detected version file."""

    path: str
    current_version: str
    file_type: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON output."""
        return {
            "path": self.path,
            "current_version": self.current_version,
            "type": self.file_type,
        }


def _parse_pyproject_toml(filepath: Path) -> str | None:
    """Extract version from pyproject.toml."""
    try:
        content = filepath.read_text()
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    return match.group(1) if match else None


def _parse_package_json(filepath: Path) -> str | None:
    """Extract version from package.json."""
    try:
        data = json.loads(filepath.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    version = data.get("version")
    return version if isinstance(version, str) else None


def _parse_setup_cfg(filepath: Path) -> str | None:
    """Extract version from setup.cfg."""
    try:
        content = filepath.read_text()
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*(\S+)', content, re.MULTILINE)
    return match.group(1) if match else None


def _parse_cargo_toml(filepath: Path) -> str | None:
    """Extract version from Cargo.toml [package] section."""
    try:
        content = filepath.read_text()
    except OSError:
        return None
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    return match.group(1) if match else None


def _parse_gradle(filepath: Path) -> str | None:
    """Extract version from build.gradle or build.gradle.kts."""
    try:
        content = filepath.read_text()
    except OSError:
        return None
    # Match: version = 'X.Y.Z', version = "X.Y.Z", version "X.Y.Z", version 'X.Y.Z'
    match = re.search(r"""^version\s*=?\s*['"]([^'"]+)['"]""", content, re.MULTILINE)
    return match.group(1) if match else None


def _parse_python_version(filepath: Path) -> str | None:
    """Extract __version__ from a Python file."""
    try:
        content = filepath.read_text()
    except OSError:
        return None
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    return match.group(1) if match else None


def _should_skip_dir(dir_name: str) -> bool:
    """Check if a directory should be skipped during recursive search."""
    return dir_name in EXCLUDED_DIRS or dir_name.startswith(".")


def _find_python_version_files(root: Path) -> list[VersionFile]:
    """Recursively find Python files with __version__ definitions."""
    results: list[VersionFile] = []
    for dirpath, dirnames, filenames in root.iterdir() if False else [(None, None, None)]:
        pass  # replaced by os.walk-like approach below

    # Use Path.rglob but filter excluded dirs
    results = []
    for pattern in ("**/__init__.py", "**/version.py"):
        for filepath in root.glob(pattern):
            # Check if any parent directory should be excluded
            rel_parts = filepath.relative_to(root).parts
            if any(_should_skip_dir(part) for part in rel_parts[:-1]):
                continue

            version = _parse_python_version(filepath)
            if version:
                results.append(
                    VersionFile(
                        path=str(filepath.relative_to(root)),
                        current_version=version,
                        file_type="python_version",
                    )
                )
    return results


# Root-level file scanners: (filename, parser_function, file_type)
_ROOT_SCANNERS: list[tuple[str, object, str]] = [
    ("pyproject.toml", _parse_pyproject_toml, "pyproject"),
    ("package.json", _parse_package_json, "package_json"),
    ("setup.cfg", _parse_setup_cfg, "setup_cfg"),
    ("Cargo.toml", _parse_cargo_toml, "cargo"),
    ("build.gradle", _parse_gradle, "gradle"),
    ("build.gradle.kts", _parse_gradle, "gradle"),
]


def detect_version_files(root: Path | None = None) -> list[VersionFile]:
    """Detect version files in a repository.

    Args:
        root: Repository root directory. Defaults to current working directory.

    Returns:
        List of detected version files with their current versions.
    """
    if root is None:
        root = Path.cwd()

    results: list[VersionFile] = []

    # Scan root-level files
    for filename, parser, file_type in _ROOT_SCANNERS:
        filepath = root / filename
        if filepath.is_file():
            version = parser(filepath)
            if version:
                results.append(
                    VersionFile(path=filename, current_version=version, file_type=file_type)
                )

    # Scan for Python __version__ files recursively
    results.extend(_find_python_version_files(root))

    return results


def run() -> None:
    """Entry point for CLI command."""
    results = detect_version_files()
    output = {
        "version_files": [r.to_dict() for r in results],
        "count": len(results),
    }
    print(json.dumps(output, indent=2))
    sys.exit(0)
```

#### Step 2: Run tests to verify they pass

Run: `cd /home/myakove/git/claude-code-config && uv run pytest tests/test_detect_versions.py -v`
Expected: ALL PASS

#### Step 3: Commit

```bash
git add myk_claude_tools/release/detect_versions.py
git commit -m "feat: add version file detection module (issue #128)"
```

---

### Task 3: Version Bump Module — Tests

**Files:**

- Create: `tests/test_bump_version.py`

#### Step 1: Write all bump tests

```python
"""Tests for version file bumping."""

import json
import textwrap
from pathlib import Path

import pytest

from myk_claude_tools.release.bump_version import BumpResult, bump_version_files


class TestBumpVersionFiles:
    """Tests for bump_version_files function."""

    def test_bump_pyproject_toml(self, tmp_path: Path) -> None:
        """Bump version in pyproject.toml."""
        content = textwrap.dedent("""\
            [project]
            name = "my-package"
            version = "1.0.0"
            description = "A package"
        """)
        (tmp_path / "pyproject.toml").write_text(content)
        result = bump_version_files("2.0.0", root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 1
        assert result.updated[0]["old_version"] == "1.0.0"
        assert result.updated[0]["new_version"] == "2.0.0"
        # Verify file was written correctly
        new_content = (tmp_path / "pyproject.toml").read_text()
        assert 'version = "2.0.0"' in new_content
        assert 'name = "my-package"' in new_content

    def test_bump_package_json(self, tmp_path: Path) -> None:
        """Bump version in package.json."""
        data = {"name": "my-pkg", "version": "1.0.0", "main": "index.js"}
        (tmp_path / "package.json").write_text(json.dumps(data, indent=2))
        result = bump_version_files("1.1.0", root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 1
        new_data = json.loads((tmp_path / "package.json").read_text())
        assert new_data["version"] == "1.1.0"
        assert new_data["name"] == "my-pkg"

    def test_bump_setup_cfg(self, tmp_path: Path) -> None:
        """Bump version in setup.cfg."""
        content = textwrap.dedent("""\
            [metadata]
            name = my-package
            version = 1.0.0

            [options]
            packages = find:
        """)
        (tmp_path / "setup.cfg").write_text(content)
        result = bump_version_files("1.1.0", root=tmp_path)
        assert result.status == "success"
        new_content = (tmp_path / "setup.cfg").read_text()
        assert "version = 1.1.0" in new_content
        assert "name = my-package" in new_content

    def test_bump_cargo_toml(self, tmp_path: Path) -> None:
        """Bump version in Cargo.toml."""
        content = textwrap.dedent("""\
            [package]
            name = "my-crate"
            version = "1.0.0"
            edition = "2021"
        """)
        (tmp_path / "Cargo.toml").write_text(content)
        result = bump_version_files("1.0.1", root=tmp_path)
        assert result.status == "success"
        new_content = (tmp_path / "Cargo.toml").read_text()
        assert 'version = "1.0.1"' in new_content

    def test_bump_gradle(self, tmp_path: Path) -> None:
        """Bump version in build.gradle."""
        content = "plugins { id 'java' }\nversion = '1.0.0'\ngroup = 'com.example'\n"
        (tmp_path / "build.gradle").write_text(content)
        result = bump_version_files("1.1.0", root=tmp_path)
        assert result.status == "success"
        new_content = (tmp_path / "build.gradle").read_text()
        assert "version = '1.1.0'" in new_content

    def test_bump_python_version(self, tmp_path: Path) -> None:
        """Bump __version__ in __init__.py."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('__version__ = "1.0.0"\n')
        result = bump_version_files("1.1.0", root=tmp_path)
        assert result.status == "success"
        new_content = (pkg_dir / "__init__.py").read_text()
        assert '__version__ = "1.1.0"' in new_content

    def test_bump_multiple_files(self, tmp_path: Path) -> None:
        """Bump version in multiple files at once."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
        result = bump_version_files("2.0.0", root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 2

    def test_bump_with_files_filter(self, tmp_path: Path) -> None:
        """Only bump specified files when --files is given."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
        result = bump_version_files("2.0.0", files=["pyproject.toml"], root=tmp_path)
        assert result.status == "success"
        assert len(result.updated) == 1
        assert result.updated[0]["path"] == "pyproject.toml"
        # package.json should be unchanged
        pkg_data = json.loads((tmp_path / "package.json").read_text())
        assert pkg_data["version"] == "1.0.0"

    def test_bump_no_version_files(self, tmp_path: Path) -> None:
        """Return error when no version files found."""
        (tmp_path / "README.md").write_text("# Hello")
        result = bump_version_files("1.0.0", root=tmp_path)
        assert result.status == "failed"
        assert result.error is not None

    def test_bump_files_filter_nonexistent(self, tmp_path: Path) -> None:
        """Return error when filtered file doesn't exist in detected files."""
        (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
        result = bump_version_files("2.0.0", files=["nonexistent.toml"], root=tmp_path)
        assert result.status == "failed"

    def test_preserves_file_content(self, tmp_path: Path) -> None:
        """Ensure only the version line changes, rest is preserved."""
        content = textwrap.dedent("""\
            [project]
            name = "my-package"
            version = "1.0.0"
            description = "A great package"
            requires-python = ">=3.10"

            [build-system]
            requires = ["hatchling"]
        """)
        (tmp_path / "pyproject.toml").write_text(content)
        bump_version_files("2.0.0", root=tmp_path)
        new_content = (tmp_path / "pyproject.toml").read_text()
        assert 'name = "my-package"' in new_content
        assert 'description = "A great package"' in new_content
        assert 'requires-python = ">=3.10"' in new_content
        assert 'requires = ["hatchling"]' in new_content

    def test_bump_result_to_dict(self) -> None:
        """Test BumpResult to_dict conversion."""
        result = BumpResult(
            status="success",
            version="2.0.0",
            updated=[{"path": "pyproject.toml", "old_version": "1.0.0", "new_version": "2.0.0"}],
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["version"] == "2.0.0"
        assert len(d["updated"]) == 1

    def test_bump_result_error_to_dict(self) -> None:
        """Test BumpResult error to_dict conversion."""
        result = BumpResult(status="failed", error="No version files found")
        d = result.to_dict()
        assert d == {"status": "failed", "error": "No version files found"}
```

#### Step 2: Run tests to verify they fail

Run: `cd /home/myakove/git/claude-code-config && uv run pytest tests/test_bump_version.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'myk_claude_tools.release.bump_version'`

#### Step 3: Commit test file

```bash
git add tests/test_bump_version.py
git commit -m "test: add tests for version file bumping (issue #128)"
```

---

### Task 4: Version Bump Module — Implementation

**Files:**

- Create: `myk_claude_tools/release/bump_version.py`

#### Step 1: Implement bump_version module

```python
"""Update version strings in detected version files.

Reads files detected by detect_versions, replaces version strings
with the new version, and writes them back. Does not perform any
git operations.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from myk_claude_tools.release.detect_versions import VersionFile, detect_version_files


@dataclass
class BumpResult:
    """Result of a version bump operation."""

    status: str
    version: str | None = None
    updated: list[dict[str, str]] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary for JSON output."""
        if self.status == "success":
            return {
                "status": self.status,
                "version": self.version,
                "updated": self.updated,
                "skipped": self.skipped,
            }
        return {"status": self.status, "error": self.error}


def _bump_pyproject_toml(filepath: Path, new_version: str) -> str | None:
    """Replace version in pyproject.toml. Returns old version or None."""
    content = filepath.read_text()
    match = re.search(r'^(version\s*=\s*["\'])([^"\']+)(["\'])', content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    new_content = content[: match.start(2)] + new_version + content[match.end(2) :]
    filepath.write_text(new_content)
    return old_version


def _bump_package_json(filepath: Path, new_version: str) -> str | None:
    """Replace version in package.json. Returns old version or None."""
    try:
        data = json.loads(filepath.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    old_version = data.get("version")
    if not isinstance(old_version, str):
        return None
    data["version"] = new_version
    filepath.write_text(json.dumps(data, indent=2) + "\n")
    return old_version


def _bump_setup_cfg(filepath: Path, new_version: str) -> str | None:
    """Replace version in setup.cfg. Returns old version or None."""
    content = filepath.read_text()
    match = re.search(r'^(version\s*=\s*)(\S+)', content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    new_content = content[: match.start(2)] + new_version + content[match.end(2) :]
    filepath.write_text(new_content)
    return old_version


def _bump_cargo_toml(filepath: Path, new_version: str) -> str | None:
    """Replace version in Cargo.toml. Returns old version or None."""
    content = filepath.read_text()
    match = re.search(r'^(version\s*=\s*["\'])([^"\']+)(["\'])', content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    new_content = content[: match.start(2)] + new_version + content[match.end(2) :]
    filepath.write_text(new_content)
    return old_version


def _bump_gradle(filepath: Path, new_version: str) -> str | None:
    """Replace version in build.gradle or build.gradle.kts. Returns old version or None."""
    content = filepath.read_text()
    match = re.search(r"""^(version\s*=?\s*['"])([^'"]+)(['"])""", content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    new_content = content[: match.start(2)] + new_version + content[match.end(2) :]
    filepath.write_text(new_content)
    return old_version


def _bump_python_version(filepath: Path, new_version: str) -> str | None:
    """Replace __version__ in a Python file. Returns old version or None."""
    content = filepath.read_text()
    match = re.search(r'^(__version__\s*=\s*["\'])([^"\']+)(["\'])', content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    new_content = content[: match.start(2)] + new_version + content[match.end(2) :]
    filepath.write_text(new_content)
    return old_version


# Map file_type to bumper function
_BUMPERS: dict[str, object] = {
    "pyproject": _bump_pyproject_toml,
    "package_json": _bump_package_json,
    "setup_cfg": _bump_setup_cfg,
    "cargo": _bump_cargo_toml,
    "gradle": _bump_gradle,
    "python_version": _bump_python_version,
}


def bump_version_files(
    new_version: str,
    files: list[str] | None = None,
    root: Path | None = None,
) -> BumpResult:
    """Update version strings in detected version files.

    Args:
        new_version: The new version string (e.g., "1.2.0").
        files: Optional list of specific file paths to update.
               If None, updates all detected version files.
        root: Repository root directory. Defaults to current working directory.

    Returns:
        BumpResult with status and details.
    """
    if root is None:
        root = Path.cwd()

    # Detect version files
    detected = detect_version_files(root)
    if not detected:
        return BumpResult(status="failed", error="No version files found in repository.")

    # Filter to specified files if provided
    if files is not None:
        filtered = [vf for vf in detected if vf.path in files]
        if not filtered:
            available = [vf.path for vf in detected]
            return BumpResult(
                status="failed",
                error=f"None of the specified files were found in detected version files. Available: {available}",
            )
        detected = filtered

    updated: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for vf in detected:
        bumper = _BUMPERS.get(vf.file_type)
        if bumper is None:
            skipped.append({"path": vf.path, "reason": f"Unknown file type: {vf.file_type}"})
            continue

        filepath = root / vf.path
        old_version = bumper(filepath, new_version)
        if old_version is not None:
            updated.append({"path": vf.path, "old_version": old_version, "new_version": new_version})
        else:
            skipped.append({"path": vf.path, "reason": "Could not find version pattern in file"})

    return BumpResult(
        status="success",
        version=new_version,
        updated=updated,
        skipped=skipped,
    )


def run(new_version: str, files: list[str] | None = None) -> None:
    """Entry point for CLI command.

    Args:
        new_version: The new version string.
        files: Optional list of specific file paths to update.
    """
    result = bump_version_files(new_version=new_version, files=files if files else None)
    print(json.dumps(result.to_dict(), indent=2))
    if result.status == "failed":
        sys.exit(1)
```

#### Step 2: Run tests to verify they pass

Run: `cd /home/myakove/git/claude-code-config && uv run pytest tests/test_bump_version.py -v`
Expected: ALL PASS

#### Step 3: Run detection tests too (regression check)

Run: `cd /home/myakove/git/claude-code-config && uv run pytest tests/test_detect_versions.py tests/test_bump_version.py -v`
Expected: ALL PASS

#### Step 4: Commit

```bash
git add myk_claude_tools/release/bump_version.py
git commit -m "feat: add version file bump module (issue #128)"
```

---

### Task 5: Wire CLI Commands

**Files:**

- Modify: `myk_claude_tools/release/commands.py`

#### Step 1: Add the two new subcommands to the release group

Update `myk_claude_tools/release/commands.py` to add `detect-versions` and `bump-version` commands:

```python
"""Release-related CLI commands."""

import click

from myk_claude_tools.release.bump_version import run as bump_run
from myk_claude_tools.release.create import run as create_run
from myk_claude_tools.release.detect_versions import run as detect_run
from myk_claude_tools.release.info import run as info_run


@click.group()
def release() -> None:
    """GitHub release commands."""
    pass


@release.command("info")
@click.option("--repo", help="Repository in owner/repo format")
def release_info(repo: str | None) -> None:
    """Fetch release validation info and commits since last tag."""
    info_run(repo)


@release.command("create")
@click.argument("owner_repo")
@click.argument("tag")
@click.argument("changelog_file")
@click.option("--prerelease", is_flag=True, help="Mark as pre-release")
@click.option("--draft", is_flag=True, help="Create as draft")
@click.option("--target", help="Target branch for the release")
def release_create(
    owner_repo: str,
    tag: str,
    changelog_file: str,
    prerelease: bool,
    draft: bool,
    target: str | None,
) -> None:
    """Create a GitHub release."""
    create_run(owner_repo, tag, changelog_file, prerelease, draft, target)


@release.command("detect-versions")
def release_detect_versions() -> None:
    """Detect version files in the current repository."""
    detect_run()


@release.command("bump-version")
@click.argument("version")
@click.option("--files", multiple=True, help="Specific files to update (can be repeated)")
def release_bump_version(version: str, files: tuple[str, ...]) -> None:
    """Update version strings in detected version files."""
    bump_run(version, list(files) if files else None)
```

#### Step 2: Test CLI commands manually

Run: `cd /home/myakove/git/claude-code-config && uv run myk-claude-tools release detect-versions`
Expected: JSON output with version files found in this repo

Run: `cd /home/myakove/git/claude-code-config && uv run myk-claude-tools release --help`
Expected: Shows `detect-versions` and `bump-version` in the command list

#### Step 3: Run all tests

Run: `cd /home/myakove/git/claude-code-config && uv run pytest tests/test_detect_versions.py tests/test_bump_version.py -v`
Expected: ALL PASS

#### Step 4: Commit

```bash
git add myk_claude_tools/release/commands.py
git commit -m "feat: wire detect-versions and bump-version CLI commands (issue #128)"
```

---

### Task 6: Update Plugin Prompt

**Files:**

- Modify: `plugins/myk-github/commands/release.md`

#### Step 1: Update release.md with new phases

Replace the entire content of `plugins/myk-github/commands/release.md` with:

````markdown
---
description: Create a GitHub release with automatic changelog generation
argument-hint: [--dry-run] [--prerelease] [--draft]
allowed-tools: Bash(myk-claude-tools:*), Bash(uv:*), Bash(git:*), Bash(gh:*), AskUserQuestion
---

# GitHub Release Command

Creates a GitHub release with automatic changelog generation based on conventional commits.
Optionally detects and updates version files before creating the release.

## Prerequisites Check (MANDATORY)

### Step 1: Check myk-claude-tools

```bash
myk-claude-tools --version
```

If not found, prompt to install: `uv tool install myk-claude-tools`

## Usage

- `/myk-github:release` - Normal release
- `/myk-github:release --dry-run` - Preview without creating
- `/myk-github:release --prerelease` - Create prerelease
- `/myk-github:release --draft` - Create draft release

## Workflow

### Phase 1: Validation

```bash
myk-claude-tools release info
```

Check validations:

- Must be on default branch
- Working tree must be clean
- Must be synced with remote

### Phase 2: Version Detection

```bash
myk-claude-tools release detect-versions
```

Parse the JSON output. If version files are found, store them for Phase 4.
If no version files are detected, skip version bumping phases and continue normally.

### Phase 3: Changelog Analysis

Parse commits from Phase 1 output and categorize by conventional commit type:

- Breaking Changes (MAJOR)
- Features (MINOR)
- Bug Fixes, Docs, Maintenance (PATCH)

Determine version bump and generate changelog.

### Phase 4: User Approval

Display the proposed release information. If version files were detected in Phase 2,
include them in the approval prompt.

**With version files:**

Present using AskUserQuestion. Show:

- Proposed version (e.g., v1.2.0, minor bump)
- List of version files to update with current → new version
- Changelog preview

User options:

- 'yes' — Proceed with proposed version and all listed files
- 'major/minor/patch' — Override the version bump type
- User can request to exclude specific files from the version bump
- 'no' — Cancel the release

**Without version files:**

Same as before — show proposed version and changelog, ask for confirmation.

### Phase 5: Bump Version (if version files detected)

Skip this phase if no version files were detected in Phase 2.

Run the bump command with the confirmed version and files:

```bash
myk-claude-tools release bump-version <VERSION> --files <file1> --files <file2>
```

Where `<VERSION>` is the version number without `v` prefix (e.g., `1.2.0`).

Then commit and push the version bump:

```bash
git add <updated-files>
git commit -m "chore: bump version to <VERSION>"
git push
```

### Phase 6: Create Release

Create temp directory with cleanup, write changelog to temp file, and create release:

```bash
mkdir -p /tmp/claude
trap 'rm -f /tmp/claude/release-changelog.md' EXIT
```

Write the changelog content (generated from Phase 3 analysis) to the file,
then create the release:

```bash
# Write changelog content to file (use heredoc or echo)
cat > /tmp/claude/release-changelog.md << 'EOF'
<changelog content from Phase 3>
EOF

myk-claude-tools release create {owner}/{repo} {tag} /tmp/claude/release-changelog.md [--prerelease] [--draft]
```

### Phase 7: Summary

Display release URL and summary.
If version files were bumped, include the list of updated files in the summary.

````

#### Step 2: Verify the plugin command is accessible

Run: `cd /home/myakove/git/claude-code-config && cat plugins/myk-github/commands/release.md | head -5`
Expected: Shows the frontmatter with description and allowed-tools

#### Step 3: Commit

```bash
git add plugins/myk-github/commands/release.md
git commit -m "feat: update release plugin with version detection and bump phases (issue #128)"
```

---

### Task 7: Run Full Test Suite

**Files:** None (verification only)

#### Step 1: Run all project tests

Run: `cd /home/myakove/git/claude-code-config && uv run pytest -v`
Expected: ALL PASS (including existing tests + new tests)

#### Step 2: Run linting

Run: `cd /home/myakove/git/claude-code-config && uv run ruff check myk_claude_tools/release/detect_versions.py myk_claude_tools/release/bump_version.py`
Expected: No issues

Run: `cd /home/myakove/git/claude-code-config && uv run ruff format --check myk_claude_tools/release/detect_versions.py myk_claude_tools/release/bump_version.py`
Expected: No issues (or auto-fixed)

Run: `cd /home/myakove/git/claude-code-config && uv run mypy myk_claude_tools/release/detect_versions.py myk_claude_tools/release/bump_version.py`
Expected: No type errors

#### Step 3: Quick manual smoke test

Run: `cd /home/myakove/git/claude-code-config && uv run myk-claude-tools release detect-versions`
Expected: JSON showing pyproject.toml and package.json (at minimum) with their current versions
