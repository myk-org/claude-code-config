#!/usr/bin/env python3
"""Restore context after compaction."""
import json
import os
import sys
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "state"


def get_snapshot_file(session_id: str) -> Path:
    """Get session-specific snapshot file path."""
    return STATE_DIR / f"{session_id}-snapshot.json"


def load_snapshot(session_id: str) -> dict:
    """Load pre-compaction snapshot."""
    snapshot_file = get_snapshot_file(session_id)
    if not snapshot_file.exists():
        print(f"Snapshot file not found: {snapshot_file}", file=sys.stderr)
        return {}

    try:
        return json.loads(snapshot_file.read_text(encoding='utf-8', errors='replace'))
    except json.JSONDecodeError as e:
        print(f"Failed to parse snapshot JSON: {e}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Failed to load snapshot: {e}", file=sys.stderr)
        return {}


def format_context(snapshot: dict) -> str:
    """Format snapshot into readable context."""
    lines = []

    # Project info
    project = snapshot.get("project", "unknown")
    working_dir = snapshot.get("working_dir", "")
    lines.append(f"**Project**: {project}")
    if working_dir:
        lines.append(f"**Working Directory**: {working_dir}")

    # Current focus
    focus = snapshot.get("current_focus", "")
    if focus:
        lines.append(f"\n## Current Focus\n{focus}")

    # Tasks by status
    tasks = snapshot.get("tasks", [])
    if tasks:
        lines.append("\n## Tasks")
        for task in tasks:
            status = task.get("status", "unknown")
            task_text = task.get("task", "")
            status_emoji = {"completed": "done", "in_progress": "doing", "pending": "todo"}.get(status, status)
            lines.append(f"- [{status_emoji}] {task_text}")

    # Decisions
    decisions = snapshot.get("decisions", [])
    if decisions:
        lines.append("\n## Key Decisions")
        for d in decisions[:5]:
            lines.append(f"- {d}")

    return "\n".join(lines)


def main():
    # Read hook input to get session_id
    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(f"Failed to parse hook input JSON: {e}", file=sys.stderr)
        hook_input = {}
    except Exception as e:
        print(f"Failed to read hook input: {e}", file=sys.stderr)
        hook_input = {}

    # Extract session_id from stdin JSON input (not environment variables)
    session_id = hook_input.get("session_id", "unknown")

    snapshot = load_snapshot(session_id)

    if not snapshot:
        print(json.dumps({"status": "no_snapshot_found"}))
        print("No snapshot found - context restoration skipped", file=sys.stderr)
        return

    context = format_context(snapshot)

    if context:
        header = "[SESSION CONTEXT RESTORED AFTER COMPACTION]"
        timestamp = snapshot.get("timestamp", "unknown")
        full_context = f"{header}\nSnapshot from: {timestamp}\n\n{context}"

        output = {"additionalContext": full_context}
        print(json.dumps(output))
    else:
        print(json.dumps({"status": "empty_snapshot"}))
        print("Snapshot found but empty - no context to restore", file=sys.stderr)


if __name__ == "__main__":
    main()
