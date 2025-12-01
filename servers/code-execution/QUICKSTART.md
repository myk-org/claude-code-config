# Archon UTCP Server - Quick Start Guide

Get up and running with the Archon UTCP code-mode server in 5 minutes.

## Prerequisites

- Node.js 18+ installed
- Access to Archon MCP server (http://localhost:8051)

## Installation (1 minute)

```bash
# Navigate to the server directory
cd ~/.claude/servers/code-execution

# Run automated setup
./setup.sh
```

The setup script will:
- Check Node.js version
- Verify Archon server connectivity
- Install dependencies
- Run type checking
- Build the project

## Verify Installation (30 seconds)

```bash
# Test simple operations
npm run example:simple
```

You should see output showing:
- Health check
- Task listing
- Knowledge base search
- Projects listing

## First Steps (3 minutes)

### 1. Run the Examples

```bash
# Simple single operations
npm run example:simple

# Batched multi-operations (POWERFUL!)
npm run example:batched

# Complex workflows with logic
npm run example:complex
```

### 2. Start the Server

```bash
npm start
```

### 3. Create Your First Script

Create a file `my-first-script.ts`:

```typescript
import { CodeModeUtcpClient } from '@utcp/code-mode';

async function myFirstScript() {
  // Create client
  const client = await CodeModeUtcpClient.create();

  // Register Archon
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

  // Execute your code
  const { result } = await client.callToolChain(`
    // Get all TODO tasks
    const tasks = await archon.find_tasks({ status: "todo" });

    // Find urgent ones
    const urgent = tasks.tasks.filter(t => t.priority > 80);

    return {
      total_todo: tasks.tasks.length,
      urgent_count: urgent.length,
      urgent_tasks: urgent.map(t => ({
        title: t.title,
        priority: t.priority,
        project: t.project_name
      }))
    };
  `);

  console.log('Result:', JSON.stringify(result, null, 2));
}

myFirstScript().catch(console.error);
```

Run it:

```bash
npx tsx my-first-script.ts
```

## Common Operations

### Get Dashboard Overview

```typescript
const { result } = await client.callToolChain(`
  const health = await archon.health_check();
  const tasks = await archon.find_tasks({ status: "todo" });
  const projects = await archon.list_projects({});

  return {
    system_healthy: health.success,
    todo_tasks: tasks.tasks.length,
    total_projects: projects.projects.length
  };
`);
```

### Search Knowledge Base

```typescript
const { result } = await client.callToolChain(`
  const results = await archon.rag_search_knowledge_base({
    query: "authentication patterns",
    limit: 5
  });

  return {
    found: results.total_results,
    top_results: results.results.map(r => ({
      score: r.score,
      preview: r.content.substring(0, 100)
    }))
  };
`);
```

### Create a Task

```typescript
const { result } = await client.callToolChain(`
  const newTask = await archon.create_task({
    title: "My new task",
    description: "Task description",
    project_id: "proj-123",
    priority: 75,
    status: "todo"
  });

  return { created: newTask.task_id };
`);
```

### Batch Multiple Operations

```typescript
const { result } = await client.callToolChain(`
  // Execute all in one batch!
  const health = await archon.health_check();
  const todoTasks = await archon.find_tasks({ status: "todo" });
  const doingTasks = await archon.find_tasks({ status: "doing" });
  const searchResults = await archon.rag_search_knowledge_base({
    query: "testing",
    limit: 3
  });

  return {
    health: health.health.status,
    tasks: {
      todo: todoTasks.tasks.length,
      doing: doingTasks.tasks.length
    },
    knowledge: {
      testing_docs: searchResults.total_results
    }
  };
`);
```

## Key Benefits Over CLI

### Before (CLI - Multiple Calls)
```bash
# 3 separate network calls
python archon_query.py health_check
python archon_query.py find_tasks --status todo
python archon_query.py list_projects
```
Time: ~900ms (3 × 300ms)

### After (UTCP - Batched)
```typescript
const { result } = await client.callToolChain(`
  const health = await archon.health_check();
  const tasks = await archon.find_tasks({ status: "todo" });
  const projects = await archon.list_projects({});
  return { health, tasks, projects };
`);
```
Time: ~300ms (1 call) - **3x faster!** ⚡

## Next Steps

1. **Read the full README**: `~/.claude/servers/code-execution/README.md`
2. **Explore examples**: Check `examples/` directory for more patterns
3. **Check types**: See `src/types.ts` for all available types
4. **Build workflows**: Combine operations for powerful automation

## Troubleshooting

### Can't connect to Archon server?

```bash
# Test server directly
curl http://localhost:8051/health

# Set custom URL
export ARCHON_SERVER_URL="http://your-server:port"
./setup.sh
```

### TypeScript errors?

```bash
npm run type-check
npm run build
```

### Examples fail?

```bash
# Check if dependencies are installed
npm install

# Try running setup again
./setup.sh
```

## Help & Support

- Check examples: `examples/*.ts`
- Review types: `src/types.ts`
- Read full docs: `README.md`
- Test connectivity: `curl http://localhost:8051/health`

---

**You're all set! Start building with Archon UTCP code-mode! 🚀**
