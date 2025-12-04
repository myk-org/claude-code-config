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
DEBUG_LOG = Path("/tmp/claude/pre-compact-debug.log")
MAX_TASKS_PER_STATUS = 5
MAX_DECISIONS = 10
FOCUS_CONTEXT_CHARS = 5000
MAX_TRANSCRIPT_SIZE = 10 * 1024 * 1024  # 10MB


def debug_log(msg: str) -> None:
    """Write debug message to log file with timestamp."""
    DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    with DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")


def get_snapshot_file(session_id: str) -> Path:
    """Get session-specific snapshot file path."""
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
        debug_log(f"Path validation error: {e}")
        return False


def extract_from_transcript(transcript_path: str) -> dict:
    """Extract tasks and decisions from conversation transcript."""
    result = {"tasks": [], "decisions": [], "current_focus": ""}

    # DEBUG: Check file existence and path
    debug_log(f"extract_from_transcript called with: {transcript_path!r}")

    if not transcript_path:
        debug_log("transcript_path is empty or None")
        return result

    path_obj = Path(transcript_path)
    file_exists = path_obj.exists()
    debug_log(f"File exists: {file_exists}")

    if not file_exists:
        return result

    # Security: validate path is within expected directories
    path_valid = validate_transcript_path(transcript_path)
    debug_log(f"Path validation passed: {path_valid}")

    if not path_valid:
        debug_log(f"Security: Transcript path outside allowed directories: {transcript_path}")
        return result

    try:
        path = Path(transcript_path)

        # Security: check file size before reading
        file_size = path.stat().st_size
        debug_log(f"File size: {file_size} bytes")

        if file_size > MAX_TRANSCRIPT_SIZE:
            debug_log(f"Transcript file too large: {file_size} bytes (max {MAX_TRANSCRIPT_SIZE})")
            return result

        # Read with explicit encoding and error handling
        content = path.read_text(encoding='utf-8', errors='replace')

        # DEBUG: Print sample of content
        content_sample = content[:500] if len(content) > 500 else content
        debug_log(f"Transcript content sample (first 500 chars):\n{content_sample}")
        debug_log(f"Total content length: {len(content)} chars")

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
        debug_log(f"Error reading transcript file: {e}")
    except Exception as e:
        debug_log(f"Unexpected error processing transcript: {e}")

    return result


def main():
    # Log session start
    debug_log("=" * 80)
    debug_log("PRE-COMPACT SNAPSHOT - SESSION START")
    debug_log("=" * 80)

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Read hook input
    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        debug_log(f"Failed to parse hook input JSON: {e}")
        hook_input = {}
    except Exception as e:
        debug_log(f"Failed to read hook input: {e}")
        hook_input = {}

    # Extract from stdin JSON input (not environment variables)
    session_id = hook_input.get("session_id", "unknown")
    transcript_path = hook_input.get("transcript_path", "")
    working_dir = os.environ.get("PWD", os.getcwd())

    # DEBUG: Print hook_input details
    debug_log(f"hook_input keys: {list(hook_input.keys())}")
    debug_log(f"transcript_path = {transcript_path!r}")

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

    snapshot_file = get_snapshot_file(session_id)
    snapshot_file.write_text(json.dumps(snapshot, indent=2), encoding='utf-8')

    # Allow compaction to proceed
    print(json.dumps({"status": "snapshot_saved", "file": str(snapshot_file)}))


if __name__ == "__main__":
    main()
