#!/usr/bin/env python3
"""Snapshot session state before compaction."""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Constants
STATE_DIR = Path.home() / ".claude" / "state"
MAX_TASKS_PER_STATUS = 5
MAX_DECISIONS = 10
FOCUS_CONTEXT_CHARS = 5000
MAX_TRANSCRIPT_SIZE = 10 * 1024 * 1024  # 10MB


def get_snapshot_file() -> Path:
    """Get session-specific snapshot file path."""
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    return STATE_DIR / f"{session_id}-snapshot.json"


def validate_transcript_path(transcript_path: str) -> bool:
    """Validate transcript path is within expected directories."""
    if not transcript_path:
        return False

    try:
        path = Path(transcript_path).resolve()

        # Allowed directories: ~/.claude, /tmp/claude
        allowed_dirs = [
            Path.home() / ".claude",
            Path("/tmp/claude"),
        ]

        # Check if path is within any allowed directory
        return any(
            path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs
        )
    except (ValueError, OSError) as e:
        print(f"Path validation error: {e}", file=sys.stderr)
        return False


def extract_from_transcript(transcript_path: str) -> dict:
    """Extract tasks and decisions from conversation transcript."""
    result = {"tasks": [], "decisions": [], "current_focus": ""}

    if not transcript_path or not Path(transcript_path).exists():
        return result

    # Security: validate path is within expected directories
    if not validate_transcript_path(transcript_path):
        print(f"Security: Transcript path outside allowed directories: {transcript_path}", file=sys.stderr)
        return result

    try:
        path = Path(transcript_path)

        # Security: check file size before reading
        file_size = path.stat().st_size
        if file_size > MAX_TRANSCRIPT_SIZE:
            print(f"Transcript file too large: {file_size} bytes (max {MAX_TRANSCRIPT_SIZE})", file=sys.stderr)
            return result

        # Read with explicit encoding and error handling
        content = path.read_text(encoding='utf-8', errors='replace')

        # Extract tasks (completed, in-progress patterns)
        # Limit match length to prevent ReDoS
        task_patterns = [
            (r"(?:completed|done|finished)[:\s]+([^\n.]{1,500}?)(?:\.|$)", "completed"),
            (r"(?:working on|in progress|currently)[:\s]+([^\n.]{1,500}?)(?:\.|$)", "in_progress"),
            (r"(?:TODO|todo|next)[:\s]+([^\n.]{1,500}?)(?:\.|$)", "pending"),
        ]
        for pattern, status in task_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches[:MAX_TASKS_PER_STATUS]:
                result["tasks"].append({"task": match.strip(), "status": status})

        # Extract decisions (with length limit)
        decision_patterns = [
            r"(?:decided|decision|chose|choosing|will use|going with)[:\s]+([^\n.]{1,500}?)(?:\.|$)",
            r"(?:approach|strategy|solution)[:\s]+([^\n.]{1,500}?)(?:\.|$)",
        ]
        for pattern in decision_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            result["decisions"].extend([m.strip() for m in matches[:MAX_TASKS_PER_STATUS]])

        # Get last mentioned focus/task (most recent context)
        focus_match = re.search(
            r"(?:working on|implementing|fixing|creating)[:\s]+([^\n.]{1,500}?)(?:\.|$)",
            content[-FOCUS_CONTEXT_CHARS:],
            re.IGNORECASE
        )
        if focus_match:
            result["current_focus"] = focus_match.group(1).strip()

    except OSError as e:
        print(f"Error reading transcript file: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Unexpected error processing transcript: {e}", file=sys.stderr)

    return result


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Read hook input
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        hook_input = {}

    transcript_path = os.environ.get("CLAUDE_TRANSCRIPT_PATH", "")
    session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
    working_dir = os.environ.get("PWD", os.getcwd())

    # Extract from transcript
    extracted = extract_from_transcript(transcript_path)

    # Build snapshot
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "working_dir": working_dir,
        "project": Path(working_dir).name,
        "trigger": hook_input.get("trigger", "unknown"),
        "tasks": extracted["tasks"],
        "decisions": extracted["decisions"][:MAX_DECISIONS],
        "current_focus": extracted["current_focus"],
    }

    snapshot_file = get_snapshot_file()
    snapshot_file.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')

    # Allow compaction to proceed
    print(json.dumps({"status": "snapshot_saved", "file": str(snapshot_file)}))


if __name__ == "__main__":
    main()
