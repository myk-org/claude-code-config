#!/usr/bin/env python3
"""
Inspect analysis batch files - useful for debugging and verification.

Usage:
    uv run inspect-analysis.py [project_info.json]
    uv run inspect-analysis.py --batch 5
    uv run inspect-analysis.py --sample
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_project_info(path: Path) -> dict[str, Any]:
    """Load and parse project_info.json file."""
    try:
        with path.open() as f:
            data = json.load(f)
        if "temp_dir" not in data:
            print(f"❌ Error: temp_dir not found in {path}", file=sys.stderr)
            sys.exit(2)
        return data
    except FileNotFoundError:
        print(f"❌ Error: File not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(2)


def count_language_files(batch: list[dict[str, Any]]) -> dict[str, int]:
    """Count files by language in a batch."""
    counts: dict[str, int] = {}
    for file_info in batch:
        lang = file_info.get("language", "Unknown")
        counts[lang] = counts.get(lang, 0) + 1
    return counts


def format_language_counts(counts: dict[str, int]) -> str:
    """Format language counts as a string."""
    return ", ".join(f"{lang}: {count}" for lang, count in sorted(counts.items()))


def show_summary(batches: list[list[dict[str, Any]]]) -> None:
    """Show summary of all batches."""
    print("📦 Analysis Batches Summary")
    print("=" * 50)

    total_files = 0
    for idx, batch in enumerate(batches, 1):
        batch_num = f"Batch {idx:03d}"
        file_count = len(batch)
        total_files += file_count
        lang_counts = count_language_files(batch)
        lang_str = format_language_counts(lang_counts)

        print(f"{batch_num}: {file_count} files ({lang_str})")

    print()
    print(f"Total: {len(batches)} batches, {total_files} files")


def show_batch_details(batches: list[list[dict[str, Any]]], batch_num: int) -> None:
    """Show detailed information for a specific batch."""
    if batch_num < 1 or batch_num > len(batches):
        print(f"❌ Error: Batch {batch_num} not found (available: 1-{len(batches)})", file=sys.stderr)
        sys.exit(1)

    batch = batches[batch_num - 1]
    print(f"📦 Batch {batch_num} Details")
    print("=" * 50)
    print(f"Files: {len(batch)}")

    lang_counts = count_language_files(batch)
    lang_str = format_language_counts(lang_counts)
    print(f"Languages: {lang_str}")
    print()
    print("Files in batch:")

    for idx, file_info in enumerate(batch, 1):
        file_path = file_info.get("file", "Unknown")
        lang = file_info.get("language", "Unknown")
        print(f"  {idx}. {file_path} ({lang})")

        # Show structure info
        classes = len(file_info.get("classes", []))
        functions = len(file_info.get("functions", []))
        imports = len(file_info.get("imports", []))
        print(f"     Classes: {classes}, Functions: {functions}, Imports: {imports}")

        if "error" in file_info:
            print(f"     ⚠️  Error: {file_info['error']}")


def show_sample(batches: list[list[dict[str, Any]]]) -> None:
    """Show sample data from first, middle, and last batch."""
    if not batches:
        print("❌ No batches found", file=sys.stderr)
        return

    print("📦 Sample Analysis")
    print("=" * 50)

    # Define which batches to sample
    samples = [
        (1, "first"),
        (len(batches) // 2 + 1, "middle"),
        (len(batches), "last")
    ]

    for batch_num, label in samples:
        if batch_num > len(batches):
            continue

        batch = batches[batch_num - 1]
        if not batch:
            continue

        file_info = batch[0]  # First file in batch

        print(f"\n=== Batch {batch_num} ({label}) ===")
        print(f"  File: {file_info.get('file', 'Unknown')}")
        print(f"  Language: {file_info.get('language', 'Unknown')}")

        classes = len(file_info.get("classes", []))
        functions = len(file_info.get("functions", []))
        imports = len(file_info.get("imports", []))

        print("  Has valid structure: ✅")
        print(f"  Classes: {classes}, Functions: {functions}, Imports: {imports}")

        if "error" in file_info:
            print(f"  ⚠️  Error: {file_info['error']}")


def load_batch_files(temp_dir: Path) -> list[list[dict[str, Any]]]:
    """Load all analysis batch files from temp_dir."""
    batch_files = sorted(temp_dir.glob("analysis_batch_*.json"))
    if not batch_files:
        print(f"❌ No analysis_batch_*.json files found in {temp_dir}", file=sys.stderr)
        sys.exit(2)

    batches = []
    for batch_file in batch_files:
        try:
            with batch_file.open() as f:
                batch_data = json.load(f)
            batches.append(batch_data)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in {batch_file}: {e}", file=sys.stderr)
            sys.exit(2)

    return batches


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Inspect analysis batch files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run inspect-analysis.py                    # Show summary
  uv run inspect-analysis.py project_info.json  # Show summary for specific file
  uv run inspect-analysis.py --batch 5          # Show batch 5 details
  uv run inspect-analysis.py --sample           # Show sample data
        """
    )
    parser.add_argument(
        "project_info",
        nargs="?",
        default=None,
        help="Path to project_info.json (default: ${PWD}/.analyze-project/project_info.json)"
    )
    parser.add_argument(
        "--batch",
        type=int,
        metavar="N",
        help="Show details for batch N"
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Show sample data from first, middle, and last batch"
    )

    args = parser.parse_args()

    # Determine project_info.json path
    if args.project_info:
        project_path = Path(args.project_info)
    else:
        project_path = Path.cwd() / ".analyze-project" / "project_info.json"

    # Load project info
    project_info = load_project_info(project_path)
    temp_dir = Path(project_info["temp_dir"])

    # Load batch files from temp_dir
    batches = load_batch_files(temp_dir)

    # Execute requested action
    if args.sample:
        show_sample(batches)
    elif args.batch is not None:
        show_batch_details(batches, args.batch)
    else:
        show_summary(batches)


if __name__ == "__main__":
    main()
