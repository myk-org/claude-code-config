# Archon UTCP Code-Mode Server - Complete Index

## Quick Navigation

- [Getting Started](#getting-started)
- [Documentation](#documentation)
- [Source Code](#source-code)
- [Examples](#examples)
- [Configuration](#configuration)
- [Tools](#tools)

## Getting Started

### First Time Setup (5 minutes)

1. **Install & Setup**
   ```bash
   cd ~/.claude/servers/code-execution
   ./setup.sh
   ```

2. **Verify Installation**
   ```bash
   ./verify.sh
   ```

3. **Run Examples**
   ```bash
   npm run example:simple
   ```

4. **Read Quick Start**
   - See [QUICKSTART.md](QUICKSTART.md) for detailed walkthrough

### What to Read First

1. **QUICKSTART.md** - Get up and running in 5 minutes
2. **COMMANDS.md** - Quick reference for common commands
3. **README.md** - Comprehensive documentation
4. **COMPARISON.md** - Understand when to use UTCP vs CLI

## Documentation

### Main Documentation Files

| File | Lines | Description | When to Read |
|------|-------|-------------|--------------|
| [QUICKSTART.md](QUICKSTART.md) | 300+ | 5-minute quick start guide | First time setup |
| [README.md](README.md) | 850+ | Complete comprehensive docs | Detailed understanding |
| [COMPARISON.md](COMPARISON.md) | 600+ | CLI vs UTCP comparison | Decision making |
| [COMMANDS.md](COMMANDS.md) | 150+ | Quick command reference | Daily usage |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | 400+ | Project overview | Understanding scope |
| [INDEX.md](INDEX.md) | - | This file | Navigation |

### Documentation by Topic

#### Installation & Setup
- **QUICKSTART.md** - Installation section
- **README.md** - Installation & Configuration sections
- **setup.sh** - Automated setup script
- **verify.sh** - Installation verification

#### Usage & Examples
- **QUICKSTART.md** - First script example
- **README.md** - Example use cases section
- **COMMANDS.md** - Quick reference
- **examples/simple.ts** - Simple examples
- **examples/batched.ts** - Batched examples
- **examples/complex.ts** - Complex examples

#### Understanding UTCP vs CLI
- **COMPARISON.md** - Complete comparison
- **README.md** - "When to Use" section
- **QUICKSTART.md** - Performance comparison

#### API Reference
- **README.md** - Available Archon Tools section
- **src/types.ts** - TypeScript type definitions
- **examples/*.ts** - Usage examples

#### Performance & Optimization
- **COMPARISON.md** - Performance benchmarks
- **README.md** - Performance Tips section
- **examples/batched.ts** - Performance demonstrations

#### Troubleshooting
- **README.md** - Troubleshooting section
- **COMMANDS.md** - Troubleshooting commands
- **verify.sh** - Diagnostic tool

## Source Code

### Core Server Implementation

| File | Lines | Description | Key Exports |
|------|-------|-------------|-------------|
| [src/server.ts](src/server.ts) | 122 | Main UTCP server | `main()` |
| [src/config.ts](src/config.ts) | 66 | Configuration management | `getValidatedConfig()` |
| [src/types.ts](src/types.ts) | 145 | TypeScript types | All Archon types |

### Source Code Structure

```
src/
├── server.ts          # Main entry point
│   ├── Creates UTCP client
│   ├── Registers Archon MCP server
│   ├── Performs health check
│   └── Exports client
│
├── config.ts          # Configuration
│   ├── Environment variable handling
│   ├── Default values
│   ├── Validation
│   └── Display utilities
│
└── types.ts           # Type definitions
    ├── ArchonTask
    ├── ArchonProject
    ├── ArchonSearchResult
    ├── Request/Response types
    └── Configuration types
```

## Examples

### Example Files Overview

| File | Lines | Focus | Complexity |
|------|-------|-------|------------|
| [examples/simple.ts](examples/simple.ts) | 184 | Single operations | Basic |
| [examples/batched.ts](examples/batched.ts) | 238 | Multi-operations | Intermediate |
| [examples/complex.ts](examples/complex.ts) | 335 | Conditional logic | Advanced |

### Example Topics

#### Simple Examples (simple.ts)
1. Health Check
2. List TODO Tasks
3. Search Knowledge Base
4. List Projects
5. Get Documentation Sources

#### Batched Examples (batched.ts)
1. Dashboard Data (3+ operations)
2. Project Summary with Tasks
3. Multi-Query Knowledge Search
4. Task Priority Analysis

#### Complex Examples (complex.ts)
1. Intelligent Task Alert System
2. Smart Knowledge Search with Fallback
3. Project Health Score Calculator
4. Task Assignment Suggestions

### Running Examples

```bash
# Run all examples in sequence
npm run example:simple && npm run example:batched && npm run example:complex

# Run specific example
npm run example:simple

# Run with custom script
npx tsx examples/simple.ts
```

## Configuration

### Configuration Files

| File | Purpose | Key Settings |
|------|---------|--------------|
| [package.json](package.json) | npm configuration | Dependencies, scripts |
| [tsconfig.json](tsconfig.json) | TypeScript config | ES2022, strict mode |
| [.npmrc](.npmrc) | npm settings | Registry, save-exact |
| [.gitignore](.gitignore) | Git ignore | node_modules, dist |

### Environment Variables

Set these before running:

```bash
# Archon server URL (default: http://localhost:8051)
export ARCHON_SERVER_URL="http://your-server:port"

# Timeout in milliseconds (default: 30000)
export ARCHON_TIMEOUT="30000"

# Retry attempts (default: 3)
export ARCHON_RETRY_ATTEMPTS="3"

# Retry delay in milliseconds (default: 1000)
export ARCHON_RETRY_DELAY="1000"
```

See [src/config.ts](src/config.ts) for implementation details.

## Tools

### Scripts & Utilities

| Script | Executable | Purpose | When to Use |
|--------|-----------|---------|-------------|
| [setup.sh](setup.sh) | Yes | Automated setup | First time installation |
| [verify.sh](verify.sh) | Yes | Verify installation | After setup or changes |

### NPM Scripts

```bash
# Development
npm start              # Start server
npm run dev            # Development mode with watch

# Building
npm run build          # Compile TypeScript
npm run type-check     # Check types only

# Examples
npm run example:simple    # Simple operations
npm run example:batched   # Batched operations
npm run example:complex   # Complex workflows
```

See [package.json](package.json) for all available scripts.

## Architecture

### System Architecture

```
Your Application (TypeScript)
    ↓
CodeModeUtcpClient.callToolChain()
    ↓
UTCP Code-Mode Server
    ↓
MCP Protocol (HTTP)
    ↓
Archon MCP Server (http://localhost:8051)
```

### Data Flow

```
1. TypeScript code → UTCP client
2. Execute in sandbox → Archon tools available as functions
3. Batch operations → Single network call
4. Transform data → JavaScript/TypeScript
5. Return result → Your application
```

## Quick Reference

### Common Commands

```bash
# Setup
./setup.sh

# Verify
./verify.sh

# Run examples
npm run example:simple
npm run example:batched
npm run example:complex

# Development
npm run dev

# Build
npm run build
```

See [COMMANDS.md](COMMANDS.md) for complete reference.

### Common Operations

```typescript
// Health check
await archon.health_check()

// List tasks
await archon.find_tasks({ status: "todo" })

// Search knowledge
await archon.rag_search_knowledge_base({ query: "test", limit: 5 })

// Create task
await archon.create_task({ title: "...", project_id: "...", priority: 75 })
```

See [README.md](README.md#available-archon-tools) for complete API reference.

## Project Statistics

- **Total Files**: 19 files
- **Total Lines**: 3,063 lines
- **Source Code**: ~900 lines (TypeScript)
- **Documentation**: ~2,100 lines (Markdown)
- **Examples**: ~760 lines (TypeScript)

### File Distribution

```
TypeScript Files:      6 files (src + examples)
Documentation:         6 files (.md)
Configuration:         5 files (json, npmrc, gitignore, tsconfig)
Scripts:              2 files (.sh)
```

## Support & Help

### Troubleshooting Resources

1. **Installation Issues**
   - Run `./verify.sh`
   - Check [README.md Troubleshooting](README.md#troubleshooting)
   - Verify Node.js version: `node --version`

2. **Connection Issues**
   - Test server: `curl http://localhost:8051/health`
   - Check environment: `echo $ARCHON_SERVER_URL`

3. **Type Errors**
   - Run `npm run type-check`
   - See [src/types.ts](src/types.ts)

4. **Runtime Errors**
   - Check examples work: `npm run example:simple`
   - Review [examples/](examples/) for patterns

### Documentation by Problem

| Problem | See |
|---------|-----|
| Can't install | setup.sh, QUICKSTART.md |
| Don't know how to start | QUICKSTART.md |
| Need quick command | COMMANDS.md |
| Want to understand deeply | README.md |
| Choosing UTCP vs CLI | COMPARISON.md |
| Type errors | src/types.ts |
| Example not working | examples/*.ts |
| Configuration issues | src/config.ts |

## Learning Path

### Beginner (0-15 minutes)

1. Run `./setup.sh`
2. Run `npm run example:simple`
3. Read [QUICKSTART.md](QUICKSTART.md)
4. Try modifying [examples/simple.ts](examples/simple.ts)

### Intermediate (15-60 minutes)

1. Read [COMPARISON.md](COMPARISON.md)
2. Run `npm run example:batched`
3. Study [examples/batched.ts](examples/batched.ts)
4. Create your first batched script

### Advanced (1+ hours)

1. Read full [README.md](README.md)
2. Study [src/](src/) implementation
3. Run `npm run example:complex`
4. Build production integration

## File Quick Links

### Most Important Files (Start Here)

1. **QUICKSTART.md** - Get started immediately
2. **COMMANDS.md** - Quick command reference
3. **examples/simple.ts** - See basic usage
4. **README.md** - Complete documentation

### By Use Case

**I want to...**

- **Get started fast** → QUICKSTART.md
- **Find a command** → COMMANDS.md
- **Understand concepts** → README.md
- **See examples** → examples/
- **Compare with CLI** → COMPARISON.md
- **Fix an issue** → README.md (Troubleshooting)
- **Understand code** → src/
- **Check types** → src/types.ts

## Next Steps

1. **If new**: Start with [QUICKSTART.md](QUICKSTART.md)
2. **Need commands**: See [COMMANDS.md](COMMANDS.md)
3. **Want details**: Read [README.md](README.md)
4. **Compare approaches**: Check [COMPARISON.md](COMPARISON.md)
5. **See examples**: Browse [examples/](examples/)

---

**Location**: `~/.claude/servers/code-execution/`

**Server**: http://localhost:8051

**Status**: ✅ Ready to use
