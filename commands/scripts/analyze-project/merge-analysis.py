#!/usr/bin/env python3
"""Merge analysis batch files into a single all_analysis.json file."""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import re


def print_usage() -> None:
    """Print usage information."""
    print("Usage: uv run merge-analysis.py [project_info.json]")
    print()
    print("If project_info.json is not provided, defaults to ${PWD}/.analyze-project/project_info.json")


def load_project_info(project_info_path: Path) -> Dict[str, Any]:
    """Load project_info.json and extract temp_dir.

    Args:
        project_info_path: Path to project_info.json

    Returns:
        Project info dictionary

    Raises:
        FileNotFoundError: If project_info.json doesn't exist
        json.JSONDecodeError: If project_info.json is invalid
        KeyError: If temp_dir is missing
    """
    if not project_info_path.exists():
        raise FileNotFoundError(f"Project info file not found: {project_info_path}")

    with open(project_info_path, "r") as f:
        project_info = json.load(f)

    if "temp_dir" not in project_info:
        raise KeyError(f"temp_dir not found in {project_info_path}")

    return project_info


def extract_batch_number(filename: str) -> int:
    """Extract batch number from filename for sorting.

    Args:
        filename: Filename like 'analysis_batch_10.json'

    Returns:
        Batch number as integer
    """
    match = re.search(r'analysis_batch_(\d+)\.json', filename)
    if match:
        return int(match.group(1))
    return 0


def find_batch_files(temp_dir: Path) -> List[Path]:
    """Find and sort all analysis_batch_*.json files.

    Args:
        temp_dir: Directory containing batch files

    Returns:
        Sorted list of batch file paths

    Raises:
        ValueError: If no batch files found
    """
    batch_files = list(temp_dir.glob("analysis_batch_*.json"))

    if not batch_files:
        raise ValueError(f"No analysis_batch_*.json files found in {temp_dir}")

    # Sort numerically by batch number
    batch_files.sort(key=lambda p: extract_batch_number(p.name))

    return batch_files


def merge_batch_files(batch_files: List[Path]) -> List[Dict[str, Any]]:
    """Merge all batch files into a single array.

    Args:
        batch_files: List of batch file paths

    Returns:
        Merged analysis array

    Raises:
        json.JSONDecodeError: If any batch file is invalid JSON
    """
    all_analysis = []

    for batch_file in batch_files:
        with open(batch_file, "r") as f:
            batch_data = json.load(f)

        # Each batch file should contain an array
        if isinstance(batch_data, list):
            all_analysis.extend(batch_data)
        else:
            # If it's a single object, wrap it in a list
            all_analysis.append(batch_data)

    return all_analysis


def write_merged_file(output_path: Path, data: List[Dict[str, Any]]) -> None:
    """Write merged analysis to all_analysis.json.

    Args:
        output_path: Path to output file
        data: Merged analysis data
    """
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0=success, 1=usage error, 2=script error)
    """
    # Parse arguments
    if len(sys.argv) > 2:
        print("Error: Too many arguments", file=sys.stderr)
        print_usage()
        return 1

    # Determine project_info.json path
    if len(sys.argv) == 2:
        if sys.argv[1] in ["-h", "--help"]:
            print_usage()
            return 0
        project_info_path = Path(sys.argv[1]).resolve()
    else:
        project_info_path = Path.cwd() / ".analyze-project" / "project_info.json"

    try:
        # Load project info
        project_info = load_project_info(project_info_path)
        temp_dir = Path(project_info["temp_dir"])

        # Find batch files
        batch_files = find_batch_files(temp_dir)

        # Merge batch files
        all_analysis = merge_batch_files(batch_files)

        # Write merged file
        output_path = temp_dir / "all_analysis.json"
        write_merged_file(output_path, all_analysis)

        # Print summary
        print(f"✅ Merged {len(batch_files)} batch files into all_analysis.json")
        print(f"📊 Total files analyzed: {len(all_analysis)}")
        print(f"📄 Output: {output_path}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}", file=sys.stderr)
        return 2
    except KeyError as e:
        print(f"Error: Missing required field - {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error: Unexpected error - {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
