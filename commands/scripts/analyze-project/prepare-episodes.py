#!/usr/bin/env python3
"""
prepare-episodes.py - Convert analysis data into episodes for graphiti-memory

Usage: uv run prepare-episodes.py <episode_type> [--batch-size N] [project_info.json]

Where episode_type is one of: relationships, files, classes
Options:
  --batch-size N   Split episodes into batches of N (default: 20)
If project_info.json is not provided, defaults to ${PWD}/.analyze-project/project_info.json

Exit codes:
  0 = success
  1 = usage error
  2 = script error
"""

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List
from collections import Counter


def error_exit(message: str, code: int = 2) -> None:
    """Print error message and exit with code."""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def load_json(file_path: Path) -> Dict[str, Any]:
    """Load JSON file, exit on error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        error_exit(f"File not found: {file_path}")
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON in {file_path}: {e}")
    except Exception as e:
        error_exit(f"Failed to read {file_path}: {e}")


def save_json(file_path: Path, data: Any) -> None:
    """Save JSON file, exit on error."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        error_exit(f"Failed to write {file_path}: {e}")


def prepare_relationships_episodes(
    temp_dir: Path,
    group_id: str,
    project_name: str
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Prepare episodes from relationships.json."""
    relationships_file = temp_dir / "relationships.json"
    relationships = load_json(relationships_file)

    episodes = []
    type_counts: Dict[str, int] = Counter()

    for rel in relationships:
        source = rel.get("source", "")
        target = rel.get("target", "")
        rel_type = rel.get("relationship_type", "unknown")
        context = rel.get("context", "")

        # Create episode body as JSON string
        episode_body = {
            "type": "relationship",
            "source": source,
            "target": target,
            "relationship_type": rel_type,
            "context": context
        }

        episode = {
            "name": f"relationship:{source}→{target}",
            "episode_body": json.dumps(episode_body, ensure_ascii=False),
            "group_id": group_id,
            "source": "json",
            "source_description": f"{rel_type}: {source} → {target}"
        }

        episodes.append(episode)
        type_counts[rel_type] += 1

    return episodes, dict(type_counts)


def prepare_files_episodes(
    temp_dir: Path,
    group_id: str,
    project_name: str,
    working_dir: Path
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Prepare episodes from analysis batch files."""
    # Load file hashes
    hashes_file = working_dir / ".analyze-project" / "current_hashes.json"
    hashes = load_json(hashes_file) if hashes_file.exists() else {}

    # Find all analysis batch files
    batch_files = sorted(temp_dir.glob("analysis_batch_*.json"))
    if not batch_files:
        error_exit(f"No analysis_batch_*.json files found in {temp_dir}")

    episodes = []
    type_counts: Dict[str, int] = Counter()

    for batch_file in batch_files:
        batch_data = load_json(batch_file)

        for file_data in batch_data:
            file_path = file_data.get("file", "")
            language = file_data.get("language", "unknown")
            file_hash = hashes.get(file_path, "")

            # Extract metadata
            imports = file_data.get("imports", [])
            classes = file_data.get("classes", [])
            functions = file_data.get("functions", [])

            # Create episode body
            episode_body = {
                "type": "file",
                "file_path": file_path,
                "language": language,
                "hash": file_hash,
                "imports": imports,
                "class_count": len(classes),
                "function_count": len(functions),
                "classes": [c.get("name", "") for c in classes],
                "functions": [f.get("name", "") for f in functions]
            }

            episode = {
                "name": f"file:{file_path}",
                "episode_body": json.dumps(episode_body, ensure_ascii=False),
                "group_id": group_id,
                "source": "json",
                "source_description": f"{language} file: {file_path}"
            }

            episodes.append(episode)
            type_counts[language] += 1

    return episodes, dict(type_counts)


def prepare_classes_episodes(
    temp_dir: Path,
    group_id: str,
    project_name: str
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Prepare episodes from class definitions in analysis batch files."""
    # Find all analysis batch files
    batch_files = sorted(temp_dir.glob("analysis_batch_*.json"))
    if not batch_files:
        error_exit(f"No analysis_batch_*.json files found in {temp_dir}")

    episodes = []
    type_counts: Dict[str, int] = Counter()

    for batch_file in batch_files:
        batch_data = load_json(batch_file)

        for file_data in batch_data:
            file_path = file_data.get("file", "")
            language = file_data.get("language", "unknown")
            classes = file_data.get("classes", [])

            for cls in classes:
                class_name = cls.get("name", "")
                bases = cls.get("bases", [])
                methods = cls.get("methods", [])
                docstring = cls.get("docstring", "")

                # Create episode body
                episode_body = {
                    "type": "class",
                    "name": class_name,
                    "file_path": file_path,
                    "language": language,
                    "bases": bases,
                    "methods": [m.get("name", "") for m in methods],
                    "method_count": len(methods),
                    "docstring": docstring
                }

                episode = {
                    "name": f"class:{class_name}",
                    "episode_body": json.dumps(episode_body, ensure_ascii=False),
                    "group_id": group_id,
                    "source": "json",
                    "source_description": f"{language} class: {class_name} in {file_path}"
                }

                episodes.append(episode)
                type_counts[language] += 1

    return episodes, dict(type_counts)


def save_batches(
    temp_dir: Path,
    episode_type: str,
    episodes: List[Dict[str, Any]],
    batch_size: int
) -> List[str]:
    """
    Save episodes in batches and return list of batch filenames.

    Also creates a manifest file with metadata about the batches.
    """
    total_episodes = len(episodes)
    batch_files = []

    # Split into batches
    for i in range(0, total_episodes, batch_size):
        batch_num = (i // batch_size) + 1
        batch = episodes[i:i + batch_size]

        # Save batch file
        batch_filename = f"episodes_{episode_type}_batch_{batch_num}.json"
        batch_path = temp_dir / batch_filename
        save_json(batch_path, batch)
        batch_files.append(batch_filename)

    # Create manifest
    manifest = {
        "type": episode_type,
        "total_episodes": total_episodes,
        "batch_size": batch_size,
        "total_batches": len(batch_files),
        "batches": batch_files
    }

    manifest_filename = f"episodes_{episode_type}_manifest.json"
    manifest_path = temp_dir / manifest_filename
    save_json(manifest_path, manifest)

    return batch_files


def main() -> None:
    """Main entry point."""
    try:
        # Parse arguments
        parser = argparse.ArgumentParser(
            description="Convert analysis data into episodes for graphiti-memory",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="If project_info.json is not provided, defaults to ${PWD}/.analyze-project/project_info.json"
        )
        parser.add_argument(
            "episode_type",
            choices=["relationships", "files", "classes"],
            help="Type of episodes to prepare"
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=20,
            help="Number of episodes per batch file (default: 20)"
        )
        parser.add_argument(
            "project_info",
            nargs="?",
            default=None,
            help="Path to project_info.json"
        )

        args = parser.parse_args()

        episode_type = args.episode_type
        batch_size = args.batch_size

        # Default to ${PWD}/.analyze-project/project_info.json if not provided
        if args.project_info:
            project_info_file = Path(args.project_info)
        else:
            project_info_file = Path.cwd() / ".analyze-project" / "project_info.json"

        # Validate batch size
        if batch_size < 1:
            error_exit("batch_size must be at least 1", code=1)

        # Load project info
        project_info = load_json(project_info_file)
        temp_dir = Path(project_info.get("temp_dir", ""))
        group_id = project_info.get("group_id", "")
        project_name = project_info.get("project_name", "")
        working_dir = Path(project_info.get("working_dir", ""))

        if not temp_dir or not group_id or not project_name or not working_dir:
            error_exit("project_info.json missing required fields: temp_dir, group_id, project_name, working_dir")

        if not temp_dir.exists():
            error_exit(f"Temp directory does not exist: {temp_dir}")

        # Prepare episodes based on type
        if episode_type == "relationships":
            episodes, breakdown = prepare_relationships_episodes(temp_dir, group_id, project_name)
        elif episode_type == "files":
            episodes, breakdown = prepare_files_episodes(temp_dir, group_id, project_name, working_dir)
        elif episode_type == "classes":
            episodes, breakdown = prepare_classes_episodes(temp_dir, group_id, project_name)
        else:
            error_exit(f"Unknown episode_type: {episode_type}")

        # Save episodes in batches
        batch_files = save_batches(temp_dir, episode_type, episodes, batch_size)
        manifest_file = temp_dir / f"episodes_{episode_type}_manifest.json"

        # Print summary
        print(f"✅ Prepared {len(episodes)} episodes (type: {episode_type})")
        print(f"📦 Split into {len(batch_files)} batches of {batch_size}")
        print(f"📄 Manifest: {manifest_file}")
        print()
        print("Breakdown:")
        for key, count in sorted(breakdown.items()):
            print(f"  {key}: {count}")

        sys.exit(0)

    except SystemExit:
        raise
    except Exception as e:
        # Get line number from traceback
        tb = traceback.extract_tb(sys.exc_info()[2])
        if tb:
            last_frame = tb[-1]
            print(f"ERROR: Script failed at line {last_frame.lineno}: {e}", file=sys.stderr)
        else:
            print(f"ERROR: Script failed: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
