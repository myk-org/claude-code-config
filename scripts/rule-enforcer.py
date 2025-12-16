#!/usr/bin/env python3
"""PreToolUse hook - blocks direct python/pip commands."""

import json
import sys


def is_forbidden_python_command(command):
    """Check if command uses python/pip directly instead of uv."""
    cmd = command.strip().lower()

    # Allow uv/uvx commands
    if cmd.startswith(("uv ", "uvx ")):
        return False

    # Block direct python/pip
    forbidden = ("python ", "python3 ", "pip ", "pip3 ")
    return cmd.startswith(forbidden)


def main():
    try:
        input_data = json.loads(sys.stdin.read())
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Block direct python/pip commands
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if is_forbidden_python_command(command):
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Python/pip commands forbidden. Use 'uv run' or 'uvx' instead. See: https://docs.astral.sh/uv/"
                    }
                }
                print(json.dumps(output))
                sys.exit(0)

        # Allow everything else
        sys.exit(0)

    except Exception:
        # Fail open on errors
        sys.exit(0)


if __name__ == "__main__":
    main()
