#!/usr/bin/env python3
"""
Create smart batches of files based on total content size.

Splits files_to_analyze.txt into batches where each batch's total size
stays under max_size threshold. Large files get isolated batches.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict


class BatchInfo(TypedDict):
    """Information about a single batch."""

    batch: int
    files: int
    total_bytes: int
    file_list: str
    oversized: bool


class BatchManifest(TypedDict):
    """Manifest of all created batches."""

    total_files: int
    total_batches: int
    max_size_bytes: int
    batches: list[BatchInfo]


class FileSizeInfo(TypedDict):
    """File path and its size in bytes."""

    path: str
    size_bytes: int


def load_project_info(project_info_path: Path) -> dict:
    """Load project info JSON file."""
    try:
        with open(project_info_path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {project_info_path} not found", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing {project_info_path}: {e}", file=sys.stderr)
        sys.exit(1)


def get_file_sizes(files_to_analyze: Path, project_root: Path) -> list[FileSizeInfo]:
    """
    Read files_to_analyze.txt and get size for each file.

    Returns list of dicts with path and size_bytes.
    """
    if not files_to_analyze.exists():
        print(f"❌ Error: {files_to_analyze} not found", file=sys.stderr)
        sys.exit(1)

    file_sizes: list[FileSizeInfo] = []

    with open(files_to_analyze) as f:
        for line in f:
            file_path = line.strip()
            if not file_path:
                continue

            full_path = project_root / file_path
            if not full_path.exists():
                print(f"⚠️  Warning: {file_path} not found, skipping", file=sys.stderr)
                continue

            try:
                size = full_path.stat().st_size
                file_sizes.append({"path": file_path, "size_bytes": size})
            except OSError as e:
                print(
                    f"⚠️  Warning: Cannot read {file_path}: {e}, skipping",
                    file=sys.stderr,
                )
                continue

    return file_sizes


def create_batches(
    file_sizes: list[FileSizeInfo], max_size_bytes: int, temp_dir: Path
) -> BatchManifest:
    """
    Create batches based on total size threshold.

    Logic:
    - Group small files together until batch reaches max_size
    - Files larger than max_size get their own batch (marked oversized)
    - Write batch files and manifest
    """
    batches: list[BatchInfo] = []
    current_batch_files: list[str] = []
    current_batch_size = 0
    batch_num = 1

    for file_info in file_sizes:
        file_path = file_info["path"]
        file_size = file_info["size_bytes"]

        # Large file gets its own batch
        if file_size > max_size_bytes:
            # First, flush current batch if not empty
            if current_batch_files:
                _write_batch(
                    temp_dir,
                    batch_num,
                    current_batch_files,
                    current_batch_size,
                    batches,
                    oversized=False,
                )
                batch_num += 1
                current_batch_files = []
                current_batch_size = 0

            # Write oversized file as its own batch
            _write_batch(
                temp_dir, batch_num, [file_path], file_size, batches, oversized=True
            )
            batch_num += 1
            continue

        # Check if adding this file would exceed limit
        if current_batch_size + file_size > max_size_bytes and current_batch_files:
            # Flush current batch
            _write_batch(
                temp_dir,
                batch_num,
                current_batch_files,
                current_batch_size,
                batches,
                oversized=False,
            )
            batch_num += 1
            current_batch_files = []
            current_batch_size = 0

        # Add file to current batch
        current_batch_files.append(file_path)
        current_batch_size += file_size

    # Flush final batch if not empty
    if current_batch_files:
        _write_batch(
            temp_dir,
            batch_num,
            current_batch_files,
            current_batch_size,
            batches,
            oversized=False,
        )

    total_files = len(file_sizes)
    total_batches = len(batches)

    return {
        "total_files": total_files,
        "total_batches": total_batches,
        "max_size_bytes": max_size_bytes,
        "batches": batches,
    }


def _write_batch(
    temp_dir: Path,
    batch_num: int,
    files: list[str],
    total_bytes: int,
    batches: list[BatchInfo],
    oversized: bool,
) -> None:
    """Write a single batch file and add to batches list."""
    batch_file = temp_dir / f"file_batch_{batch_num}.txt"

    with open(batch_file, "w") as f:
        for file_path in files:
            f.write(f"{file_path}\n")

    batch_info: BatchInfo = {
        "batch": batch_num,
        "files": len(files),
        "total_bytes": total_bytes,
        "file_list": batch_file.name,
        "oversized": oversized,
    }

    batches.append(batch_info)


def format_bytes(bytes_count: int) -> str:
    """Format bytes as human-readable string (KB, MB)."""
    if bytes_count < 1024:
        return f"{bytes_count}B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.0f}KB"
    else:
        return f"{bytes_count / (1024 * 1024):.1f}MB"


def print_summary(manifest: BatchManifest, temp_dir: Path) -> None:
    """Print batch creation summary."""
    print(
        f"📦 Created {manifest['total_batches']} batches from {manifest['total_files']} files"
    )
    print("📊 Size distribution:")

    for batch in manifest["batches"]:
        oversized_flag = " ⚠️  oversized" if batch["oversized"] else ""
        file_plural = "file" if batch["files"] == 1 else "files"
        print(
            f"   Batch {batch['batch']}: {batch['files']} {file_plural}, "
            f"{format_bytes(batch['total_bytes'])}{oversized_flag}"
        )

    manifest_path = temp_dir / "batch_manifest.json"
    print(f"📄 Manifest: {manifest_path}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create smart batches based on file size"
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=50000,
        help="Maximum total size per batch in bytes (default: 50000 = 50KB)",
    )
    parser.add_argument(
        "project_info",
        nargs="?",
        default=Path.cwd() / ".analyze-project" / "project_info.json",
        help="Path to project_info.json (default: .analyze-project/project_info.json)",
    )

    args = parser.parse_args()

    # Load project info
    project_info_path = Path(args.project_info)
    project_info = load_project_info(project_info_path)

    # Extract paths
    temp_dir = Path(project_info["temp_dir"])
    project_root = Path(project_info.get("working_dir", Path.cwd()))
    files_to_analyze = temp_dir / "files_to_analyze.txt"

    # Get file sizes
    file_sizes = get_file_sizes(files_to_analyze, project_root)

    if not file_sizes:
        print("❌ Error: No valid files to analyze", file=sys.stderr)
        sys.exit(1)

    # Create batches
    manifest = create_batches(file_sizes, args.max_size, temp_dir)

    # Write manifest
    manifest_path = temp_dir / "batch_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Print summary
    print_summary(manifest, temp_dir)


if __name__ == "__main__":
    main()
