# Quick Command Reference

## Setup & Installation

```bash
# Navigate to directory
cd ~/.claude/servers/code-execution

# Automated setup
./setup.sh

# Manual setup
npm install
npm run build

# Verify installation
./verify.sh
```

## Running Examples

```bash
# Simple operations
npm run example:simple

# Batched operations (recommended)
npm run example:batched

# Complex workflows
npm run example:complex
```

## Development

```bash
# Start server
npm start

# Development mode with watch
npm run dev

# Type checking
npm run type-check

# Build project
npm run build
```

## Creating Your Own Scripts

```bash
# Create new script
touch my-script.ts

# Run with tsx
npx tsx my-script.ts

# Or add to package.json scripts section
npm run my-script
```

## Verification & Debugging

```bash
# Verify complete setup
./verify.sh

# Check Archon server health
curl http://localhost:8051/health | jq

# Check Node.js version
node --version

# Check npm version
npm --version

# View installed dependencies
npm list --depth=0
```

## Configuration

```bash
# Set custom Archon URL
export ARCHON_SERVER_URL="http://your-server:port"

# Set timeout (milliseconds)
export ARCHON_TIMEOUT="30000"

# Set retry attempts
export ARCHON_RETRY_ATTEMPTS="3"

# Set retry delay (milliseconds)
export ARCHON_RETRY_DELAY="1000"
```

## Common Operations

### Health Check
```typescript
const { result } = await client.callToolChain(`
  const health = await archon.health_check();
  return health;
`);
```

### List TODO Tasks
```typescript
const { result } = await client.callToolChain(`
  const tasks = await archon.find_tasks({ status: "todo" });
  return tasks;
`);
```

### Search Knowledge Base
```typescript
const { result } = await client.callToolChain(`
  const results = await archon.rag_search_knowledge_base({
    query: "your search query",
    limit: 5
  });
  return results;
`);
```

### Create Task
```typescript
const { result } = await client.callToolChain(`
  const task = await archon.create_task({
    title: "Task title",
    description: "Task description",
    project_id: "proj-id",
    priority: 75,
    status: "todo"
  });
  return task;
`);
```

### Batch Multiple Operations
```typescript
const { result } = await client.callToolChain(`
  const health = await archon.health_check();
  const tasks = await archon.find_tasks({ status: "todo" });
  const projects = await archon.list_projects({});

  return {
    healthy: health.success,
    taskCount: tasks.tasks.length,
    projectCount: projects.projects.length
  };
`);
```

## Troubleshooting

```bash
# Cannot connect to Archon
curl http://localhost:8051/health

# Dependencies not installed
npm install

# TypeScript errors
npm run type-check
npm run build

# Clean and reinstall
rm -rf node_modules dist
npm install
npm run build

# Reset to fresh state
git clean -fdx  # WARNING: Removes all untracked files
./setup.sh
```

## File Locations

```
Server:          ~/.claude/servers/code-execution/
Source:          ~/.claude/servers/code-execution/src/
Examples:        ~/.claude/servers/code-execution/examples/
Documentation:   ~/.claude/servers/code-execution/*.md
```

## Documentation Files

- **README.md** - Complete documentation
- **QUICKSTART.md** - Get started in 5 minutes
- **COMPARISON.md** - CLI vs UTCP comparison
- **PROJECT_SUMMARY.md** - Project overview
- **COMMANDS.md** - This file

## NPM Scripts

```bash
npm run start              # Start server
npm run dev                # Development mode with watch
npm run build              # Compile TypeScript
npm run type-check         # Check types without building
npm run example:simple     # Run simple examples
npm run example:batched    # Run batched examples
npm run example:complex    # Run complex examples
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| ARCHON_SERVER_URL | http://localhost:8051 | Archon MCP server URL |
| ARCHON_TIMEOUT | 30000 | Request timeout (ms) |
| ARCHON_RETRY_ATTEMPTS | 3 | Number of retry attempts |
| ARCHON_RETRY_DELAY | 1000 | Delay between retries (ms) |

## Quick Start Template

```typescript
#!/usr/bin/env tsx
import { CodeModeUtcpClient } from '@utcp/code-mode';

async function main() {
  const client = await CodeModeUtcpClient.create();

  await client.registerManual({
    name: 'archon',
    call_template_type: 'mcp',
    config: {
      mcpServers: {
        archon: {
          command: 'npx',
          args: ['-y', '@modelcontextprotocol/server-fetch', 'http://localhost:8051'],
          env: { MCP_SERVER_URL: 'http://localhost:8051' }
        }
      }
    }
  });

  const { result } = await client.callToolChain(`
    // Your code here
    const health = await archon.health_check();
    return health;
  `);

  console.log(result);
}

main().catch(console.error);
```

Save as `script.ts` and run: `npx tsx script.ts`
