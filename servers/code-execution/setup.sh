#!/bin/bash
# UTCP Code-Mode Server Setup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "UTCP Code-Mode Server Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Node.js version
echo "Checking Node.js version..."
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Error: Node.js 18 or higher is required (found v$NODE_VERSION)"
    echo "   Please upgrade Node.js: https://nodejs.org/"
    exit 1
fi
echo "✓ Node.js version: $(node --version)"
echo ""

# Check npm
echo "Checking npm..."
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed"
    exit 1
fi
echo "✓ npm version: $(npm --version)"
echo ""

# Check for config files
echo "Checking MCP server configurations..."
CONFIG_DIR="$HOME/.claude/code-execution-configs"
if [ -d "$CONFIG_DIR" ] && [ "$(ls -A $CONFIG_DIR/*.json 2>/dev/null)" ]; then
    CONFIG_COUNT=$(ls -1 $CONFIG_DIR/*.json 2>/dev/null | wc -l)
    echo "✓ Found $CONFIG_COUNT MCP server configuration(s)"
else
    echo "⚠️  Warning: No configuration files found in $CONFIG_DIR/ directory"
    echo "   Create JSON config files in $CONFIG_DIR/ to define your MCP servers."
    echo "   See $CONFIG_DIR/example.json.example for reference."
fi
echo ""

# Install dependencies
echo "Installing dependencies..."
if [ -f "package-lock.json" ]; then
    npm ci
else
    npm install
fi
echo "✓ Dependencies installed"
echo ""

# Type check
echo "Running type check..."
npm run type-check
echo "✓ TypeScript types are valid"
echo ""

# Build
echo "Building project..."
npm run build
echo "✓ Build successful"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Configure MCP servers in ~/.claude/code-execution-configs/ directory"
echo "  2. Start the server:        npm start"
echo ""
