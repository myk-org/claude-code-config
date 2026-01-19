#!/usr/bin/env python3
"""PreToolUse hook - blocks direct python/pip and pre-commit commands."""

import json
import sys


def is_forbidden_python_command(command: str) -> bool:
    """Check if command uses python/pip directly instead of uv."""
    cmd = command.strip().lower()

    # Allow uv/uvx commands
    if cmd.startswith(("uv ", "uvx ")):
        return False

    # Block direct python/pip
    forbidden = ("python ", "python3 ", "pip ", "pip3 ")
    return cmd.startswith(forbidden)


def is_forbidden_precommit_command(command: str) -> bool:
    """Check if command uses pre-commit directly instead of prek."""
    cmd = command.strip().lower()

    # Block direct pre-commit commands
    return cmd.startswith("pre-commit ")


def main() -> None:
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
                        "permissionDecisionReason": "Direct python/pip commands are forbidden.",
                        "additionalContext": (
                            "You attempted to run python/pip directly. Instead:\n"
                            "1. Delegate Python tasks to the python-expert agent\n"
                            "2. Use 'uv run script.py' to run Python scripts\n"
                            "3. Use 'uvx package-name' to run package CLIs\n"
                            "See: https://docs.astral.sh/uv/"
                        ),
                    }
                }
                print(json.dumps(output))
                sys.exit(0)

            if is_forbidden_precommit_command(command):
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Direct pre-commit commands are forbidden.",
                        "additionalContext": (
                            "You attempted to run pre-commit directly. Instead:\n"
                            "1. Use the 'prek' command which wraps pre-commit\n"
                            "2. Example: prek run --all-files\n"
                            "See: https://github.com/j178/prek"
                        ),
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
