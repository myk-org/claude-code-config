#!/bin/bash
# Archon UTCP Server Verification Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Archon UTCP Server Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

ERRORS=0
WARNINGS=0

# Function to print status
print_status() {
    local status=$1
    local message=$2

    if [ "$status" = "OK" ]; then
        echo "✓ $message"
    elif [ "$status" = "WARN" ]; then
        echo "⚠️  $message"
        ((WARNINGS++))
    elif [ "$status" = "FAIL" ]; then
        echo "❌ $message"
        ((ERRORS++))
    else
        echo "  $message"
    fi
}

# Check Node.js
echo "Checking prerequisites..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        print_status "OK" "Node.js version: $NODE_VERSION"
    else
        print_status "FAIL" "Node.js version too old: $NODE_VERSION (requires 18+)"
    fi
else
    print_status "FAIL" "Node.js not found"
fi

# Check npm
if command -v npm &> /dev/null; then
    print_status "OK" "npm version: $(npm --version)"
else
    print_status "FAIL" "npm not found"
fi

echo ""

# Check Archon server
echo "Checking Archon MCP server..."
ARCHON_URL="${ARCHON_SERVER_URL:-http://localhost:8051}"

if curl -sf "$ARCHON_URL/health" > /dev/null 2>&1; then
    HEALTH_DATA=$(curl -s "$ARCHON_URL/health")
    STATUS=$(echo "$HEALTH_DATA" | jq -r '.health.status' 2>/dev/null || echo "unknown")
    print_status "OK" "Archon server reachable at $ARCHON_URL"
    print_status "INFO" "Server status: $STATUS"
else
    print_status "WARN" "Cannot reach Archon server at $ARCHON_URL"
fi

echo ""

# Check directory structure
echo "Checking directory structure..."
REQUIRED_DIRS=("src" "examples" ".vscode")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        print_status "OK" "Directory exists: $dir"
    else
        print_status "FAIL" "Missing directory: $dir"
    fi
done

echo ""

# Check required files
echo "Checking required files..."
REQUIRED_FILES=(
    "package.json"
    "tsconfig.json"
    "src/server.ts"
    "src/config.ts"
    "src/types.ts"
    "examples/simple.ts"
    "examples/batched.ts"
    "examples/complex.ts"
    "README.md"
    "QUICKSTART.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_status "OK" "File exists: $file"
    else
        print_status "FAIL" "Missing file: $file"
    fi
done

echo ""

# Check dependencies
echo "Checking dependencies..."
if [ -d "node_modules" ]; then
    print_status "OK" "node_modules directory exists"

    # Check key dependencies
    DEPS=("@utcp/code-mode" "typescript" "tsx")
    for dep in "${DEPS[@]}"; do
        if [ -d "node_modules/$dep" ]; then
            print_status "OK" "Dependency installed: $dep"
        else
            print_status "WARN" "Missing dependency: $dep (run: npm install)"
        fi
    done
else
    print_status "WARN" "node_modules not found (run: npm install)"
fi

echo ""

# TypeScript check
echo "Checking TypeScript..."
if [ -d "node_modules" ]; then
    if npm run type-check > /dev/null 2>&1; then
        print_status "OK" "TypeScript type check passed"
    else
        print_status "WARN" "TypeScript type check failed (run: npm run type-check)"
    fi
else
    print_status "WARN" "Cannot run type check (dependencies not installed)"
fi

echo ""

# Build check
echo "Checking build..."
if [ -d "dist" ]; then
    print_status "OK" "dist directory exists"
    if [ -f "dist/server.js" ]; then
        print_status "OK" "server.js built successfully"
    else
        print_status "WARN" "server.js not built (run: npm run build)"
    fi
else
    print_status "WARN" "dist directory not found (run: npm run build)"
fi

echo ""

# Scripts check
echo "Checking npm scripts..."
SCRIPTS=("start" "dev" "build" "type-check" "example:simple" "example:batched" "example:complex")
for script in "${SCRIPTS[@]}"; do
    if npm run | grep -q "  $script$"; then
        print_status "OK" "Script available: npm run $script"
    else
        print_status "WARN" "Script missing: $script"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Summary
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✓ All checks passed! Server is ready to use."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Next steps:"
    echo "  npm run example:simple   - Test simple operations"
    echo "  npm run example:batched  - Test batched operations"
    echo "  npm run example:complex  - Test complex workflows"
    echo "  npm start                - Start the server"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  Verification completed with $WARNINGS warning(s)."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Server should work, but some features may be limited."
    echo "Run ./setup.sh to fix warnings."
    exit 0
else
    echo "❌ Verification failed with $ERRORS error(s) and $WARNINGS warning(s)."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Please fix the errors above before using the server."
    echo "Run ./setup.sh to install dependencies and fix issues."
    exit 1
fi
