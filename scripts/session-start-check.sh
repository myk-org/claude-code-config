#!/usr/bin/env bash
set -euo pipefail

# Session start check - validates required tools are available
# Runs silently if all tools present, outputs missing tools report otherwise

missing_critical=()
missing_optional=()

# CRITICAL: uv - Required for Python hooks
if ! command -v uv &>/dev/null; then
  missing_critical+=("[CRITICAL] uv - Required for running Python hooks
  Install: https://docs.astral.sh/uv/")
fi

# OPTIONAL: gh - Only check if this is a GitHub repository
if git remote -v 2>/dev/null | grep -q "github.com"; then
  if ! command -v gh &>/dev/null; then
    missing_optional+=("[OPTIONAL] gh - Required for GitHub operations (PRs, issues, releases)
  Install: https://cli.github.com/")
  fi
fi

# OPTIONAL: jq - Required for AI review handlers
if ! command -v jq &>/dev/null; then
  missing_optional+=("[OPTIONAL] jq - Required for AI review handlers (JSON processing)
  Install: https://stedolan.github.io/jq/download/")
fi

# OPTIONAL: gawk - Required for AI review handlers
if ! command -v gawk &>/dev/null; then
  missing_optional+=("[OPTIONAL] gawk - Required for AI review handlers (text processing)
  Install: brew install gawk (macOS) or apt install gawk (Linux)")
fi

# OPTIONAL: prek - Only check if .pre-commit-config.yaml exists
if [[ -f ".pre-commit-config.yaml" ]]; then
  if ! command -v prek &>/dev/null; then
    missing_optional+=("[OPTIONAL] prek - Required for pre-commit hooks (detected .pre-commit-config.yaml)
  Install: https://github.com/j178/prek")
  fi
fi

# OPTIONAL: mcpl - MCP Launchpad (always check)
if ! command -v mcpl &>/dev/null; then
  missing_optional+=("[OPTIONAL] mcpl - MCP Launchpad for MCP server access
  Install: https://github.com/kenneth-liao/mcp-launchpad")
fi

# Output report only if something is missing
if [[ ${#missing_critical[@]} -gt 0 || ${#missing_optional[@]} -gt 0 ]]; then
  echo "MISSING_TOOLS_REPORT:"
  echo ""
  echo "[AI INSTRUCTION - YOU MUST FOLLOW THIS]"
  echo "Some tools required by this configuration are missing."
  echo ""
  echo "Criticality levels:"
  echo "- CRITICAL: Configuration will NOT work without these. Must install."
  echo "- OPTIONAL: Enhances functionality. Nice to have."
  echo ""
  echo "YOUR REQUIRED ACTION:"
  echo "1. List each missing tool with its purpose"
  echo "2. ASK the user: 'Would you like me to help install these tools?'"
  echo "3. If user accepts, provide the installation command for each tool"
  echo "4. Prioritize CRITICAL tools first"
  echo ""
  echo "DO NOT just mention the tools. You MUST ask if the user wants help installing them."
  echo ""

  for item in "${missing_critical[@]}"; do
    echo "$item"
    echo ""
  done

  for item in "${missing_optional[@]}"; do
    echo "$item"
    echo ""
  done
fi

# Always exit 0 (non-blocking)
exit 0
