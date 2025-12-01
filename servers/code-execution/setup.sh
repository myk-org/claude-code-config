#!/bin/bash
# Archon UTCP Server Setup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Archon UTCP Server Setup"
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

# Check Archon server connectivity
echo "Checking Archon MCP server connectivity..."
ARCHON_URL="${ARCHON_SERVER_URL:-http://localhost:8051}"
if curl -sf "$ARCHON_URL/health" > /dev/null 2>&1; then
    echo "✓ Archon server is reachable at $ARCHON_URL"
else
    echo "⚠️  Warning: Cannot reach Archon server at $ARCHON_URL"
    echo "   The server may be down or the URL may be incorrect."
    echo "   You can set ARCHON_SERVER_URL environment variable to override."
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
echo "  1. Start the server:        npm start"
echo "  2. Run simple examples:     npm run example:simple"
echo "  3. Run batched examples:    npm run example:batched"
echo "  4. Run complex examples:    npm run example:complex"
echo ""
echo "Configuration:"
echo "  Server URL: $ARCHON_URL"
echo "  (Set ARCHON_SERVER_URL to override)"
echo ""
