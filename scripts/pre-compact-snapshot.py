#!/usr/bin/env python3
"""Snapshot session state before compaction."""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
    """Validate transcript path is within expected directories.

    Handles symlinked subdirectories (e.g., via GNU stow) by checking
    both the original path and the fully resolved path.
    """
    if not transcript_path:
        return False

    try:
        path_original = Path(transcript_path)
        path_resolved = path_original.resolve()

        # Allowed directories: ~/.claude, /tmp/claude
        allowed_dirs = [
            Path.home() / ".claude",
            Path("/tmp/claude"),
        ]

        # Check original path first (handles symlinked subdirectories)
        # Example: ~/.claude/projects -> ~/dotfiles/.claude/projects
        for allowed_dir in allowed_dirs:
            if path_original.is_relative_to(allowed_dir):
                return True

        # Check resolved path against resolved allowed directories
        # (handles case where ~/.claude itself is a symlink)
        for allowed_dir in allowed_dirs:
            allowed_dir_resolved = allowed_dir.resolve()
            if path_resolved.is_relative_to(allowed_dir_resolved):
                return True

        return False
    except (ValueError, OSError) as e:
        debug_log(f"Path validation error: {e}")
        return False


def normalize_task_description(desc: str) -> str:
    """Normalize task description for deduplication.

    Converts to lowercase, strips whitespace, removes common variations.
    """
    normalized = desc.lower().strip()
    # Normalize common variations
    normalized = re.sub(r"\s+", " ", normalized)  # Collapse whitespace
    normalized = re.sub(
        r"commit and push (?:changes|to main)", "commit and push", normalized
    )
    normalized = re.sub(r"fix (?:the )?issues?", "fix issue", normalized)
    normalized = re.sub(r"update (?:the )?", "update ", normalized)
    return normalized


def extract_from_transcript(transcript_path: str) -> dict[str, Any]:
    """Extract tasks and decisions from conversation transcript.

    Parses JSONL transcript structure to extract:
    - Tasks from Task tool calls (agent delegations)
    - Tasks from TodoWrite tool calls (built-in todo list)
    - Files modified from Edit/Write tool calls (including within agent results)
    - Decisions from assistant message content
    - Current focus from last active task or user request
    - Last user request for context
    """
    result: dict[str, Any] = {
        "tasks": [],
        "files_modified": [],
        "decisions": [],
        "current_focus": "",
        "last_user_request": "",
    }

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
        debug_log(
            f"Security: Transcript path outside allowed directories: {transcript_path}"
        )
        return result

    try:
        path = Path(transcript_path)

        # Security: check file size before reading
        file_size = path.stat().st_size
        debug_log(f"File size: {file_size} bytes")

        if file_size > MAX_TRANSCRIPT_SIZE:
            debug_log(
                f"Transcript file too large: {file_size} bytes (max {MAX_TRANSCRIPT_SIZE})"
            )
            return result

        # Parse JSONL line by line - track tool calls and their results
        task_tool_calls = {}  # id -> tool_use dict
        last_todowrite = None  # Track most recent TodoWrite call
        assistant_messages = []
        user_messages = []
        files_modified_set = set()
        line_count = 0

        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_count += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as e:
                    debug_log(f"Skipping invalid JSON on line {line_count}: {e}")
                    continue

                entry_type = entry.get("type", "")

                # Extract from assistant messages
                if entry_type == "assistant":
                    message = entry.get("message", {})
                    content = message.get("content", [])

                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                item_type = item.get("type", "")

                                # Task tool call (agent delegation)
                                if (
                                    item_type == "tool_use"
                                    and item.get("name") == "Task"
                                ):
                                    tool_id = item.get("id", "")
                                    if tool_id:
                                        task_tool_calls[tool_id] = item
                                        debug_log(f"Found Task tool call: {tool_id}")

                                # TodoWrite tool call (built-in todo list)
                                elif (
                                    item_type == "tool_use"
                                    and item.get("name") == "TodoWrite"
                                ):
                                    # Track the most recent TodoWrite call
                                    last_todowrite = item
                                    debug_log(
                                        f"Found TodoWrite tool call: {item.get('id', '')}"
                                    )

                                # Edit tool call - track file modifications
                                elif (
                                    item_type == "tool_use"
                                    and item.get("name") == "Edit"
                                ):
                                    file_path = item.get("input", {}).get(
                                        "file_path", ""
                                    )
                                    if file_path:
                                        files_modified_set.add(file_path)

                                # Write tool call - track file modifications
                                elif (
                                    item_type == "tool_use"
                                    and item.get("name") == "Write"
                                ):
                                    file_path = item.get("input", {}).get(
                                        "file_path", ""
                                    )
                                    if file_path:
                                        files_modified_set.add(file_path)

                                # Assistant text content
                                elif item_type == "text":
                                    text = item.get("text", "")
                                    if text and not _is_code_block(text):
                                        assistant_messages.append(text)

                # Extract from user messages
                elif entry_type == "user":
                    message = entry.get("message", {})
                    content = message.get("content", "")

                    # Handle both string and array content
                    if isinstance(content, str):
                        text = content.strip()
                        if text:
                            user_messages.append(text)
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                item_type = item.get("type", "")

                                # Text content
                                if item_type == "text":
                                    text = item.get("text", "").strip()
                                    if text:
                                        user_messages.append(text)

                                # Tool result - mark task as completed
                                elif item_type == "tool_result":
                                    tool_use_id = item.get("tool_use_id", "")
                                    if tool_use_id in task_tool_calls:
                                        # Mark this task as having a result (completed)
                                        task_tool_calls[tool_use_id]["_has_result"] = True
                                        debug_log(f"Marked task as completed: {tool_use_id}")

                                    # Extract file paths from tool results (agent operations)
                                    result_content = item.get("content", "")
                                    if result_content:
                                        # Try to parse as JSON - agent results are often JSON
                                        try:
                                            if isinstance(result_content, str):
                                                content_obj = json.loads(result_content)
                                            else:
                                                content_obj = result_content

                                            # Recursively look for file_path keys
                                            def extract_file_paths(obj, paths_set):
                                                if isinstance(obj, dict):
                                                    if "file_path" in obj and obj["file_path"]:
                                                        paths_set.add(obj["file_path"])
                                                    for value in obj.values():
                                                        extract_file_paths(value, paths_set)
                                                elif isinstance(obj, list):
                                                    for item in obj:
                                                        extract_file_paths(item, paths_set)

                                            extract_file_paths(content_obj, files_modified_set)
                                        except (json.JSONDecodeError, TypeError):
                                            # If not JSON, try regex pattern matching for file paths
                                            # Look for patterns like "file_path": "/path/to/file"
                                            file_path_matches = re.findall(
                                                r'"file_path"\s*:\s*"([^"]+)"', str(result_content)
                                            )
                                            files_modified_set.update(file_path_matches)

        debug_log(
            f"Processed {line_count} lines, found {len(task_tool_calls)} task calls"
        )
        debug_log(
            f"Found {len(assistant_messages)} assistant messages, {len(user_messages)} user messages"
        )
        debug_log(f"Found {len(files_modified_set)} modified files")
        debug_log(f"Found TodoWrite: {last_todowrite is not None}")

        # Extract tasks with deduplication (limit to 10)
        # Priority: TodoWrite tasks first, then Task tool calls
        last_active_task = None
        seen_tasks = {}  # normalized_description -> (task_dict, original_text)
        all_tasks = []  # Final list in priority order

        # 1. Extract from TodoWrite (most recent state)
        if last_todowrite:
            todos_input = last_todowrite.get("input", {})
            todos_list = todos_input.get("todos", [])
            debug_log(f"Processing {len(todos_list)} TodoWrite tasks")

            for todo in todos_list:
                if not isinstance(todo, dict):
                    continue

                task_text = todo.get("content", "").strip()
                status_raw = todo.get("status", "pending")

                if not task_text:
                    continue

                # Map TodoWrite status to our format
                if status_raw == "completed":
                    status = "completed"
                elif status_raw == "in_progress":
                    status = "in_progress"
                else:  # pending or unknown
                    status = "pending"

                # Normalize for deduplication
                normalized = normalize_task_description(task_text)

                # Add to seen_tasks (TodoWrite tasks take priority)
                if normalized not in seen_tasks:
                    # No agent field for TodoWrite (direct work)
                    task_dict = {"task": task_text, "status": status}
                    seen_tasks[normalized] = (task_dict, task_text)
                    all_tasks.append(task_dict)

                    # Track last active task for current_focus
                    if status == "in_progress":
                        last_active_task = task_text

        # 2. Extract tasks from Task tool calls (agent delegations)
        for tool_id, tool_call in task_tool_calls.items():
            input_data = tool_call.get("input", {})
            agent = input_data.get("subagent_type", "unknown")
            description = input_data.get("description", "")
            prompt = input_data.get("prompt", "")
            has_result = tool_call.get("_has_result", False)

            # Build task description
            if description:
                task_text = description
            elif prompt:
                # Use first 200 chars of prompt
                task_text = prompt[:200]
                if len(prompt) > 200:
                    task_text += "..."
            else:
                task_text = f"Task delegated to {agent}"

            # Normalize for deduplication
            normalized = normalize_task_description(task_text)

            # Check if we've seen this task before (from TodoWrite or previous Task calls)
            if normalized in seen_tasks:
                # Update existing task: prefer completed over in_progress, keep most recent
                existing_task, existing_text = seen_tasks[normalized]
                if has_result and existing_task["status"] in ("in_progress", "pending"):
                    # Update to completed
                    existing_task["status"] = "completed"
                # Add agent info if missing (TodoWrite tasks don't have it)
                if "agent" not in existing_task and agent != "unknown":
                    existing_task["agent"] = agent
                # Keep the more detailed description
                if len(task_text) > len(existing_text):
                    existing_task["task"] = task_text
                    seen_tasks[normalized] = (existing_task, task_text)
                continue

            # New unique task
            status = "completed" if has_result else "in_progress"
            task_dict = {"task": task_text, "status": status, "agent": agent}
            seen_tasks[normalized] = (task_dict, task_text)
            all_tasks.append(task_dict)

            # Track last active (in_progress) task for current_focus
            if not has_result and not last_active_task:
                last_active_task = task_text

        # Use all_tasks list (already in priority order: TodoWrite first, then Task calls)
        # Limit to 10 most recent
        result["tasks"] = all_tasks[:10]
        debug_log(
            f"Final task count: {len(result['tasks'])} (TodoWrite + Task, deduplicated)"
        )

        # Extract files modified (limit to 10)
        result["files_modified"] = sorted(list(files_modified_set))[:10]

        # Extract last user request (most recent non-empty user message)
        if user_messages:
            result["last_user_request"] = user_messages[-1][:200]

        # Determine current focus
        if last_active_task:
            # Use the last in-progress task
            result["current_focus"] = last_active_task
        elif user_messages:
            # Fallback to last user request
            result["current_focus"] = user_messages[-1][:100]

        # Extract decisions from assistant messages
        decision_patterns = [
            r"(?:I(?:'ll| will)|Let's|We'll|Going to)\s+(?:use|implement|choose|go with|adopt)\s+([^.!?\n]{10,200})",
            r"(?:decided|choosing|selected|opted for)\s+([^.!?\n]{10,200})",
            r"(?:The (?:approach|strategy|solution) is|Best approach:)\s+([^.!?\n]{10,200})",
        ]

        # Look at recent messages for decisions (last 20%)
        recent_messages = assistant_messages[-max(5, len(assistant_messages) // 5) :]

        for msg in recent_messages:
            for pattern in decision_patterns:
                matches = re.findall(pattern, msg, re.IGNORECASE)
                for match in matches:
                    decision = match.strip()
                    # Filter out noise: skip if too short or looks like code
                    if len(decision) > 15 and not _looks_like_code(decision):
                        result["decisions"].append(decision)
                        if len(result["decisions"]) >= 5:  # Limit to 5 decisions
                            break
            if len(result["decisions"]) >= 5:
                break

        debug_log(
            f"Extracted {len(result['tasks'])} unique tasks (from {len(task_tool_calls)} total), {len(result['files_modified'])} files, {len(result['decisions'])} decisions"
        )

    except OSError as e:
        debug_log(f"Error reading transcript file: {e}")
    except Exception as e:
        debug_log(f"Unexpected error processing transcript: {e}")
        import traceback

        debug_log(f"Traceback: {traceback.format_exc()}")

    return result


def _is_code_block(text: str) -> bool:
    """Check if text appears to be a code block."""
    # Common indicators of code blocks
    return (
        text.strip().startswith("```")
        or text.strip().startswith("    ")  # Indented code
        or ("{" in text and "}" in text and ":" in text)  # JSON-like
    )


def _looks_like_code(text: str) -> bool:
    """Check if text looks like code or technical noise."""
    # Count code-like indicators
    indicators = sum(
        [
            text.count("{") > 1,
            text.count("}") > 1,
            text.count("(") > 2,
            text.count(")") > 2,
            text.count(";") > 1,
            text.count("import ") > 0,
            text.count("def ") > 0,
            text.count("class ") > 0,
            text.startswith("#"),
            text.startswith("//"),
        ]
    )
    return indicators >= 2


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
        "files_modified": extracted["files_modified"],
        "decisions": extracted["decisions"][:MAX_DECISIONS],
        "current_focus": extracted["current_focus"],
        "last_user_request": extracted["last_user_request"],
    }

    snapshot_file = get_snapshot_file(session_id)
    snapshot_file.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    # Allow compaction to proceed
    print(json.dumps({"status": "snapshot_saved", "file": str(snapshot_file)}))


if __name__ == "__main__":
    main()
