#!/bin/bash

# Read the JSON input from stdin
input_json=$(cat)

# Extract the message using jq
notification_message=$(echo "$input_json" | jq -r '.message')

# Send the notification
notify-send --wait "Claude: $notification_message"
