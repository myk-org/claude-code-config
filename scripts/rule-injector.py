#!/usr/bin/env python3
"""
UserPromptSubmit Hook: Rule Injector

Injects concise rule reminders into every user prompt to maintain rule adherence.
"""

import json
import sys


def main() -> None:
    """Inject rule reminder into user prompt context."""

    # Read stdin (required by hook protocol)
    try:
        _ = sys.stdin.read()
    except Exception:
        pass  # Ignore stdin errors

    try:
        rule_reminder = (
            "[SYSTEM RULES] You are a MANAGER. NEVER do work directly. ALWAYS delegate:\n"
            "- Edit/Write → language specialists (python-expert, go-expert, etc.)\n"
            "- ALL Bash commands → bash-expert or appropriate specialist\n"
            "- Git commands → git-expert\n"
            "- MCP tools → manager agents\n"
            "- Multi-file exploration → Explore agent\n"
            "HOOKS WILL BLOCK VIOLATIONS."
        )

        output = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": rule_reminder}}

        # Output JSON to stdout
        print(json.dumps(output, indent=2))
        sys.exit(0)

    except Exception as e:
        # On error, still exit successfully to not block user prompts
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
