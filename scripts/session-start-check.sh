#!/usr/bin/env bash
set -euo pipefail

# Session start check - validates required tools are available
# Runs silently if all tools present, outputs missing tools report otherwise

missing_critical=()
missing_optional=()

# Precompute all installed plugin.json paths once (avoids repeated find scans)
_plugin_cache=$(find "${HOME}/.claude" -maxdepth 6 -type f -name "plugin.json" 2>/dev/null || true)

# Helper: check if a marketplace plugin is installed
# Usage: check_plugin_installed "plugin-name"
# Returns 0 if found, 1 if not
check_plugin_installed() {
  local plugin="$1"
  # Check common plugin locations
  if [[ -d "${HOME}/.claude/share/plugins/${plugin}@claude-plugins-official" ]]; then
    return 0
  elif [[ -d "${HOME}/.claude/plugins/${plugin}@claude-plugins-official" ]]; then
    return 0
  elif grep -Fq "/${plugin}@claude-plugins-official/" <<<"$_plugin_cache"; then
    return 0
  fi
  return 1
}

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

# CRITICAL: Review plugins - Required for mandatory code review loop
critical_marketplace_plugins=(
  pr-review-toolkit
  superpowers
  feature-dev
)

missing_critical_plugins=()
for plugin in "${critical_marketplace_plugins[@]}"; do
  if ! check_plugin_installed "$plugin"; then
    missing_critical_plugins+=("$plugin")
  fi
done

if [[ ${#missing_critical_plugins[@]} -gt 0 ]]; then
  missing_list=$(printf '%s, ' "${missing_critical_plugins[@]}")
  missing_list=${missing_list%, }
  install_cmds=""
  for p in "${missing_critical_plugins[@]}"; do
    install_cmds+="    /plugin install ${p}@claude-plugins-official"$'\n'
  done
  missing_critical+=("[CRITICAL] Missing review plugins - Required for mandatory code review loop
  Install:
    /plugin marketplace add claude-plugins-official
${install_cmds}  Missing: ${missing_list}")
fi

# OPTIONAL: Marketplace plugins - Check @claude-plugins-official plugins
optional_marketplace_plugins=(
  claude-code-setup
  claude-md-management
  code-review
  code-simplifier
  coderabbit
  commit-commands
  frontend-design
  github
  gopls-lsp
  jdtls-lsp
  lua-lsp
  playground
  pyright-lsp
  security-guidance
)

missing_plugins=()
for plugin in "${optional_marketplace_plugins[@]}"; do
  if ! check_plugin_installed "$plugin"; then
    missing_plugins+=("$plugin")
  fi
done

if [[ ${#missing_plugins[@]} -gt 0 ]]; then
  missing_list=$(printf '%s, ' "${missing_plugins[@]}")
  missing_list=${missing_list%, }
  install_cmds=""
  for p in "${missing_plugins[@]}"; do
    install_cmds+="    /plugin install ${p}@claude-plugins-official"$'\n'
  done
  missing_optional+=("[OPTIONAL] Missing marketplace plugins - Enhance functionality but not mandatory
  Install with:
    /plugin marketplace add claude-plugins-official
${install_cmds}  Missing: ${missing_list}")
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
