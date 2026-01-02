#!/usr/bin/env python3
"""Validate analysis batch files for correct structure and data types.

Usage:
    uv run validate-analysis.py [project_info.json]

If project_info.json is not provided, defaults to ${PWD}/.analyze-project/project_info.json
"""

import json
import sys
from pathlib import Path
from typing import Any


def validate_entry(entry: dict[str, Any], batch_file: str) -> list[str]:
    """Validate a single file entry in an analysis batch.

    Returns list of error messages (empty if valid).
    """
    errors = []

    # Check required fields
    required_fields = ["file", "language", "functions", "classes", "imports"]
    for field in required_fields:
        if field not in entry:
            errors.append(f"Missing required field '{field}' in {entry.get('file', 'unknown file')}")
            continue

    # Type validation
    if "file" in entry and not isinstance(entry["file"], str):
        errors.append(f"'file' must be string, got {type(entry['file']).__name__}")

    if "language" in entry and not isinstance(entry["language"], str):
        errors.append(f"'language' must be string in {entry.get('file', 'unknown')}")

    # Critical: functions must be array, not string
    if "functions" in entry:
        if isinstance(entry["functions"], str):
            errors.append(f"'functions' is string, not array in file {entry.get('file', 'unknown')}")
        elif not isinstance(entry["functions"], list):
            errors.append(f"'functions' must be array, got {type(entry['functions']).__name__} in {entry.get('file', 'unknown')}")

    # Critical: classes must be array, not string
    if "classes" in entry:
        if isinstance(entry["classes"], str):
            errors.append(f"'classes' is string, not array in file {entry.get('file', 'unknown')}")
        elif not isinstance(entry["classes"], list):
            errors.append(f"'classes' must be array, got {type(entry['classes']).__name__} in {entry.get('file', 'unknown')}")

    # imports can be object or array
    if "imports" in entry:
        if not isinstance(entry["imports"], (dict, list)):
            errors.append(f"'imports' must be object or array, got {type(entry['imports']).__name__} in {entry.get('file', 'unknown')}")

    return errors


def validate_batch_file(batch_path: Path) -> tuple[bool, int, list[str]]:
    """Validate a single batch file.

    Returns:
        (is_valid, file_count, errors)
    """
    errors = []

    # Check file exists
    if not batch_path.exists():
        return False, 0, [f"File not found: {batch_path}"]

    # Parse JSON
    try:
        with open(batch_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, 0, [f"Invalid JSON: {e}"]
    except Exception as e:
        return False, 0, [f"Error reading file: {e}"]

    # Check root is array
    if not isinstance(data, list):
        return False, 0, [f"Root must be array, got {type(data).__name__}"]

    file_count = len(data)

    # Validate each entry
    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            errors.append(f"Entry {idx} must be object, got {type(entry).__name__}")
            continue

        entry_errors = validate_entry(entry, batch_path.name)
        errors.extend(entry_errors)

    is_valid = len(errors) == 0
    return is_valid, file_count, errors


def main() -> int:
    """Main entry point."""
    # Parse arguments
    if len(sys.argv) > 2:
        print("Usage: validate-analysis.py [project_info.json]", file=sys.stderr)
        return 1

    # Determine project_info.json path
    if len(sys.argv) == 2:
        project_info_path = Path(sys.argv[1])
    else:
        project_info_path = Path.cwd() / ".analyze-project" / "project_info.json"

    # Load project_info to get batch directory
    if not project_info_path.exists():
        print(f"❌ Error: {project_info_path} not found", file=sys.stderr)
        return 1

    try:
        with open(project_info_path) as f:
            project_info = json.load(f)
    except Exception as e:
        print(f"❌ Error reading {project_info_path}: {e}", file=sys.stderr)
        return 1

    batch_dir = Path(project_info.get("batch_dir", project_info_path.parent))

    # Find all batch files
    batch_files = sorted(batch_dir.glob("analysis_batch_*.json"))

    if not batch_files:
        print(f"⚠️  No analysis batch files found in {batch_dir}")
        return 0

    print("🔍 Validating analysis batches...")

    # Validate each batch
    total_valid = 0
    total_invalid = 0
    total_files = 0
    all_errors: dict[str, list[str]] = {}

    for batch_path in batch_files:
        is_valid, file_count, errors = validate_batch_file(batch_path)
        total_files += file_count

        if is_valid:
            print(f"✅ {batch_path.name}: {file_count} files, valid")
            total_valid += 1
        else:
            print(f"❌ {batch_path.name}: Error - {errors[0] if errors else 'unknown error'}")
            total_invalid += 1
            all_errors[batch_path.name] = errors

    # Print summary
    print()
    print("Summary:")
    print(f"  Total batches: {len(batch_files)}")
    print(f"  Valid: {total_valid}")
    print(f"  Invalid: {total_invalid}")
    print(f"  Total files: {total_files}")

    # Print all errors
    if all_errors:
        print()
        print("Errors found:")
        for batch_name, errors in all_errors.items():
            for error in errors:
                print(f"  - {batch_name}: {error}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
