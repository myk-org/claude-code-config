#!/usr/bin/env python3
"""Validate analysis batch files against JSON schema.

Usage:
    uv run --with jsonschema validate-analysis.py [project_info.json]

If project_info.json is not provided, defaults to ${PWD}/.analyze-project/project_info.json
"""

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft7Validator, ValidationError
except ImportError:
    print("❌ Error: jsonschema library not found", file=sys.stderr)
    print("Run with: uv run --with jsonschema validate-analysis.py", file=sys.stderr)
    sys.exit(1)


def load_schema() -> dict:
    """Load the JSON schema from the script's directory."""
    script_dir = Path(__file__).parent
    schema_path = script_dir / "analysis_schema.json"

    if not schema_path.exists():
        print(f"❌ Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    with open(schema_path) as f:
        return json.load(f)


def format_schema_error(error: ValidationError, item_index: int | None = None) -> str:
    """Format a schema validation error into a human-readable message.

    Args:
        error: The validation error
        item_index: Optional index of the item in the array that failed

    Returns:
        Formatted error message
    """
    # Build the JSON path
    path_parts = ["$"]
    if item_index is not None:
        path_parts.append(f"items[{item_index}]")

    for part in error.absolute_path:
        if isinstance(part, int):
            path_parts.append(f"[{part}]")
        else:
            path_parts.append(str(part))

    json_path = ".".join(path_parts)

    # Format the error message
    if error.validator == "required":
        missing_field = error.message.split("'")[1]
        return f"{json_path}: missing required field '{missing_field}'"
    elif error.validator == "type":
        expected = error.validator_value
        actual = type(error.instance).__name__
        if actual == "str":
            actual = "string"
        elif actual == "dict":
            actual = "object"
        elif actual == "list":
            actual = "array"
        return f"{json_path}: expected {expected}, got {actual}"
    elif error.validator == "additionalProperties":
        return f"{json_path}: {error.message}"
    else:
        return f"{json_path}: {error.message}"


def validate_batch_file(batch_path: Path, validator: Draft7Validator) -> tuple[bool, int, list[str]]:
    """Validate a single batch file against the schema.

    Args:
        batch_path: Path to the batch file
        validator: Configured JSON schema validator

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

    file_count = len(data) if isinstance(data, list) else 0

    # Validate against schema
    validation_errors = sorted(validator.iter_errors(data), key=lambda e: e.path)

    for error in validation_errors:
        # Determine item index if error is within an array item
        item_index = None
        if error.absolute_path and isinstance(error.absolute_path[0], int):
            item_index = error.absolute_path[0]

        formatted_error = format_schema_error(error, item_index)
        errors.append(formatted_error)

    is_valid = len(errors) == 0
    return is_valid, file_count, errors


def main() -> int:
    """Main entry point."""
    # Parse arguments
    if len(sys.argv) > 2:
        print("Usage: uv run --with jsonschema validate-analysis.py [project_info.json]", file=sys.stderr)
        return 1

    # Load schema and create validator
    schema = load_schema()
    validator = Draft7Validator(schema)

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

    print("🔍 Validating analysis batches against schema...")

    # Validate each batch
    total_valid = 0
    total_invalid = 0
    total_files = 0
    all_errors: dict[str, list[str]] = {}

    for batch_path in batch_files:
        is_valid, file_count, errors = validate_batch_file(batch_path, validator)
        total_files += file_count

        if is_valid:
            print(f"✅ {batch_path.name}: {file_count} files, valid")
            total_valid += 1
        else:
            print(f"❌ {batch_path.name}: Schema violation")
            total_invalid += 1
            all_errors[batch_path.name] = errors

    # Print summary
    print()
    print("Summary:")
    print(f"  Total batches: {len(batch_files)}")
    print(f"  Valid: {total_valid}")
    print(f"  Invalid: {total_invalid}")
    print(f"  Total files: {total_files}")

    # Print all errors in the requested format
    if all_errors:
        print()
        print("Schema violations:")
        for batch_name, errors in all_errors.items():
            print(f"❌ {batch_name}: Schema violation")
            for error in errors:
                print(f"   - {error}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
