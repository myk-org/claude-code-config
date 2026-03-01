"""Update version strings in detected version files.

Reads files detected by detect_versions, replaces version strings
with the new version, and writes them back. Does not perform any
git operations.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from myk_claude_tools.release.detect_versions import detect_version_files


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
    content = filepath.read_text()
    # Find the [project] section and only bump version within it
    project_match = re.search(r"^\[project\]\s*$", content, re.MULTILINE)
    if not project_match:
        return None
    section_start = project_match.end()
    next_section = re.search(r"^\[", content[section_start:], re.MULTILINE)
    if next_section:
        section_content = content[section_start : section_start + next_section.start()]
    else:
        section_content = content[section_start:]
    match = re.search(r'^(version\s*=\s*["\'])([^"\']+)(["\'])', section_content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    # Adjust match positions to full file offsets
    abs_start = section_start + match.start(2)
    abs_end = section_start + match.end(2)
    new_content = content[:abs_start] + new_version + content[abs_end:]
    filepath.write_text(new_content)
    return old_version


def _bump_package_json(filepath: Path, new_version: str) -> str | None:
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
    content = filepath.read_text()
    match = re.search(r"^(version\s*=\s*)(\S+)", content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    # Skip dynamic version directives (attr:, file:) and non-numeric versions
    if not re.match(r"^\d+\.", old_version):
        return None
    new_content = content[: match.start(2)] + new_version + content[match.end(2) :]
    filepath.write_text(new_content)
    return old_version


def _bump_cargo_toml(filepath: Path, new_version: str) -> str | None:
    content = filepath.read_text()
    # Find the [package] section and only bump version within it
    package_match = re.search(r"^\[package\]\s*$", content, re.MULTILINE)
    if not package_match:
        return None
    section_start = package_match.end()
    next_section = re.search(r"^\[", content[section_start:], re.MULTILINE)
    if next_section:
        section_content = content[section_start : section_start + next_section.start()]
    else:
        section_content = content[section_start:]
    match = re.search(r'^(version\s*=\s*["\'])([^"\']+)(["\'])', section_content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    # Adjust match positions to full file offsets
    abs_start = section_start + match.start(2)
    abs_end = section_start + match.end(2)
    new_content = content[:abs_start] + new_version + content[abs_end:]
    filepath.write_text(new_content)
    return old_version


def _bump_gradle(filepath: Path, new_version: str) -> str | None:
    content = filepath.read_text()
    match = re.search(r"""^(version\s*=?\s*['"])([^'"]+)(['"])""", content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    new_content = content[: match.start(2)] + new_version + content[match.end(2) :]
    filepath.write_text(new_content)
    return old_version


def _bump_python_version(filepath: Path, new_version: str) -> str | None:
    content = filepath.read_text()
    match = re.search(r'^(__version__\s*=\s*["\'])([^"\']+)(["\'])', content, re.MULTILINE)
    if not match:
        return None
    old_version = match.group(2)
    new_content = content[: match.start(2)] + new_version + content[match.end(2) :]
    filepath.write_text(new_content)
    return old_version


_BUMPERS: dict[str, Callable[[Path, str], str | None]] = {
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

    detected = detect_version_files(root)
    if not detected:
        return BumpResult(status="failed", error="No version files found in repository.")

    unmatched: list[str] = []

    if files is not None:
        filtered = [vf for vf in detected if vf.path in files]
        if not filtered:
            available = [vf.path for vf in detected]
            return BumpResult(
                status="failed",
                error=f"None of the specified files were found in detected version files. Available: {available}",
            )
        # Report unmatched file paths as skipped
        matched_paths = {vf.path for vf in filtered}
        unmatched = [f for f in files if f not in matched_paths]
        detected = filtered

    updated: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for vf in detected:
        bumper = _BUMPERS.get(vf.file_type)
        if bumper is None:
            skipped.append({"path": vf.path, "reason": f"Unknown file type: {vf.file_type}"})
            continue

        filepath = root / vf.path
        try:
            old_version = bumper(filepath, new_version)
        except OSError as e:
            skipped.append({"path": vf.path, "reason": f"I/O error: {e}"})
            continue
        if old_version is not None:
            updated.append({"path": vf.path, "old_version": old_version, "new_version": new_version})
        else:
            skipped.append({"path": vf.path, "reason": "Could not find version pattern in file"})

    for path in unmatched:
        skipped.append({"path": path, "reason": "Not found in detected version files"})

    return BumpResult(
        status="success",
        version=new_version,
        updated=updated,
        skipped=skipped,
    )


def run(new_version: str, files: list[str] | None = None) -> None:
    """Entry point for CLI command."""
    result = bump_version_files(new_version=new_version, files=files if files else None)
    print(json.dumps(result.to_dict(), indent=2))
    if result.status == "failed":
        sys.exit(1)
