#!/usr/bin/env bash
set -euo pipefail

# Check for required commands
for cmd in jq notify-send; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: Required command '$cmd' not found" >&2
        exit 1
    fi
done

# Read JSON input from stdin
input_json=$(cat)

# Verify input is not empty
if [[ -z "$input_json" ]]; then
    echo "Error: No input received from stdin" >&2
    exit 1
fi

# Parse JSON and extract message, capturing any jq errors
if ! notification_message=$(echo "$input_json" | jq -r '.message' 2>&1); then
    echo "Error: Failed to parse JSON - $notification_message" >&2
    exit 1
fi

# Verify notification_message is non-empty
if [[ -z "$notification_message" || "$notification_message" == "null" ]]; then
    echo "Error: Notification message is empty or missing from JSON" >&2
    exit 1
fi

# Send the notification and propagate any failures
if ! notify-send --icon="" --wait "Claude: $notification_message"; then
    echo "Error: notify-send failed" >&2
    exit 1
fi
