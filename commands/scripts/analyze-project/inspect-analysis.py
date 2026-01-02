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
            return json.load(f)
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
        path = file_info.get("path", "Unknown")
        lang = file_info.get("language", "Unknown")
        print(f"  {idx}. {path} ({lang})")

        # Show structure info if available
        if "analysis" in file_info:
            analysis = file_info["analysis"]
            classes = len(analysis.get("classes", []))
            functions = len(analysis.get("functions", []))
            print(f"     Classes: {classes}, Functions: {functions}")
        elif "error" in file_info:
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
        print(f"  File: {file_info.get('path', 'Unknown')}")
        print(f"  Language: {file_info.get('language', 'Unknown')}")

        if "analysis" in file_info:
            analysis = file_info["analysis"]
            classes = len(analysis.get("classes", []))
            functions = len(analysis.get("functions", []))
            print("  Has valid structure: ✅")
            print(f"  Classes: {classes}, Functions: {functions}")
        elif "error" in file_info:
            print("  Has valid structure: ❌")
            print(f"  Error: {file_info['error']}")
        else:
            print("  Has valid structure: ⚠️  Unknown")


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
        default="project_info.json",
        help="Path to project_info.json (default: project_info.json)"
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

    # Load project info
    project_path = Path(args.project_info)
    project_info = load_project_info(project_path)

    # Get batches
    batches = project_info.get("batches", [])
    if not batches:
        print("❌ No batches found in project info", file=sys.stderr)
        sys.exit(2)

    # Execute requested action
    if args.sample:
        show_sample(batches)
    elif args.batch is not None:
        show_batch_details(batches, args.batch)
    else:
        show_summary(batches)


if __name__ == "__main__":
    main()
