#!/usr/bin/env python3
"""
Create smart batches of files based on estimated token count.

Splits files_to_analyze.txt into batches where each batch's total estimated tokens
stays under max_tokens threshold. Large files get isolated batches.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import TypedDict


def estimate_tokens(byte_count: int) -> int:
    """Estimate tokens from byte count. Rule: ~4 chars/bytes per token."""
    return byte_count // 4


class BatchInfo(TypedDict):
    """Information about a single batch."""

    batch: int
    files: int
    estimated_tokens: int
    file_list: str
    oversized: bool


class ChunkedFileInfo(TypedDict):
    """Information about a chunked file."""

    original_file: str
    chunk_files: list[str]
    chunk_manifest: str


class BatchManifest(TypedDict):
    """Manifest of all created batches."""

    total_files: int
    total_batches: int
    max_tokens: int
    batches: list[BatchInfo]
    chunked_files: list[ChunkedFileInfo]


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
    file_sizes: list[FileSizeInfo], max_tokens: int, temp_dir: Path, project_root: Path
) -> BatchManifest:
    """
    Create batches based on estimated token threshold.

    Logic:
    - Group small files together until batch reaches max_tokens
    - Files larger than max_tokens get split into chunks
    - Chunks are added to batches like regular files
    - Write batch files and manifest
    """
    batches: list[BatchInfo] = []
    chunked_files: list[ChunkedFileInfo] = []
    current_batch_files: list[str] = []
    current_batch_tokens = 0
    batch_num = 1

    for file_info in file_sizes:
        file_path = file_info["path"]
        file_size = file_info["size_bytes"]
        file_tokens = estimate_tokens(file_size)

        # Large file needs to be split into chunks
        if file_tokens > max_tokens:
            # First, flush current batch if not empty
            if current_batch_files:
                _write_batch(
                    temp_dir,
                    batch_num,
                    current_batch_files,
                    current_batch_tokens,
                    batches,
                    oversized=False,
                )
                batch_num += 1
                current_batch_files = []
                current_batch_tokens = 0

            # Split the large file into chunks
            chunk_info = _split_large_file(
                file_path, max_tokens, temp_dir, project_root
            )
            chunked_files.append(chunk_info)

            # Add chunk files to batches
            for chunk_file in chunk_info["chunk_files"]:
                chunk_path = Path(chunk_file)
                chunk_size = chunk_path.stat().st_size
                chunk_tokens = estimate_tokens(chunk_size)

                # Check if adding this chunk would exceed limit
                if current_batch_tokens + chunk_tokens > max_tokens and current_batch_files:
                    _write_batch(
                        temp_dir,
                        batch_num,
                        current_batch_files,
                        current_batch_tokens,
                        batches,
                        oversized=False,
                    )
                    batch_num += 1
                    current_batch_files = []
                    current_batch_tokens = 0

                # Add chunk to current batch
                current_batch_files.append(chunk_file)
                current_batch_tokens += chunk_tokens

            continue

        # Check if adding this file would exceed limit
        if current_batch_tokens + file_tokens > max_tokens and current_batch_files:
            # Flush current batch
            _write_batch(
                temp_dir,
                batch_num,
                current_batch_files,
                current_batch_tokens,
                batches,
                oversized=False,
            )
            batch_num += 1
            current_batch_files = []
            current_batch_tokens = 0

        # Add file to current batch
        current_batch_files.append(file_path)
        current_batch_tokens += file_tokens

    # Flush final batch if not empty
    if current_batch_files:
        _write_batch(
            temp_dir,
            batch_num,
            current_batch_files,
            current_batch_tokens,
            batches,
            oversized=False,
        )

    total_files = len(file_sizes)
    total_batches = len(batches)

    return {
        "total_files": total_files,
        "total_batches": total_batches,
        "max_tokens": max_tokens,
        "batches": batches,
        "chunked_files": chunked_files,
    }


def _split_large_file(
    file_path: str, max_tokens: int, temp_dir: Path, project_root: Path
) -> ChunkedFileInfo:
    """
    Split a large file into chunks using split-large-files.py.

    Args:
        file_path: Relative path to file (from files_to_analyze.txt)
        max_tokens: Maximum tokens per chunk
        temp_dir: Temporary directory for chunks
        project_root: Project root directory

    Returns:
        ChunkedFileInfo with chunk details
    """
    script_dir = Path(__file__).parent
    split_script = script_dir / "split-large-files.py"
    full_path = project_root / file_path

    # Call split-large-files.py
    cmd = [
        "uv",
        "run",
        "--with",
        "tree-sitter-languages",
        str(split_script),
        str(full_path),
        "--output-dir",
        str(temp_dir),
        "--max-tokens",
        str(max_tokens),
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        # Print the script's output
        if result.stdout:
            print(result.stdout, end="")
    except subprocess.CalledProcessError as e:
        print(
            f"❌ Error splitting {file_path}:\n{e.stderr}",
            file=sys.stderr,
        )
        sys.exit(1)
    except FileNotFoundError:
        print(
            f"❌ Error: split-large-files.py not found at {split_script}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load the chunk manifest
    safe_prefix = file_path.replace("/", "__").replace("\\", "__")
    manifest_path = temp_dir / f"{safe_prefix}.chunks.json"

    try:
        with open(manifest_path) as f:
            chunk_manifest = json.load(f)
    except FileNotFoundError:
        print(
            f"❌ Error: Chunk manifest not found at {manifest_path}",
            file=sys.stderr,
        )
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(
            f"❌ Error parsing chunk manifest {manifest_path}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Extract chunk file paths
    chunk_files = [chunk["file_path"] for chunk in chunk_manifest["chunks"]]

    return {
        "original_file": file_path,
        "chunk_files": chunk_files,
        "chunk_manifest": str(manifest_path),
    }


def _write_batch(
    temp_dir: Path,
    batch_num: int,
    files: list[str],
    estimated_tokens: int,
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
        "estimated_tokens": estimated_tokens,
        "file_list": batch_file.name,
        "oversized": oversized,
    }

    batches.append(batch_info)


def format_tokens(token_count: int) -> str:
    """Format token count as human-readable string with thousands separator."""
    return f"{token_count:,}"


def print_summary(manifest: BatchManifest, temp_dir: Path) -> None:
    """Print batch creation summary."""
    print(
        f"📦 Created {manifest['total_batches']} batches from {manifest['total_files']} files"
    )

    # Show chunked files if any
    chunked_files = manifest.get("chunked_files", [])
    if chunked_files:
        print(f"🔪 Split {len(chunked_files)} large files into chunks:")
        for chunked in chunked_files:
            num_chunks = len(chunked["chunk_files"])
            chunk_plural = "chunk" if num_chunks == 1 else "chunks"
            print(f"   {chunked['original_file']} → {num_chunks} {chunk_plural}")

    print("📊 Token distribution:")

    for batch in manifest["batches"]:
        oversized_flag = " ⚠️  oversized" if batch["oversized"] else ""
        file_plural = "file" if batch["files"] == 1 else "files"
        print(
            f"   Batch {batch['batch']}: {batch['files']} {file_plural}, "
            f"~{format_tokens(batch['estimated_tokens'])} tokens{oversized_flag}"
        )

    manifest_path = temp_dir / "batch_manifest.json"
    print(f"📄 Manifest: {manifest_path}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create smart batches based on estimated token count"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8000,
        help="Maximum estimated tokens per batch (default: 8000)",
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
    manifest = create_batches(file_sizes, args.max_tokens, temp_dir, project_root)

    # Write manifest
    manifest_path = temp_dir / "batch_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Print summary
    print_summary(manifest, temp_dir)


if __name__ == "__main__":
    main()
