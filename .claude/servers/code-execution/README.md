# Archon UTCP Code-Mode Server

A UTCP (Universal Tool Calling Protocol) code-mode server that provides direct, batched access to the Archon MCP server for task management, knowledge base search, and project operations.

## What is UTCP Code-Mode?

UTCP code-mode is a powerful protocol that allows you to:

1. **Execute TypeScript code in a sandboxed environment** with MCP tools available as async functions
2. **Batch multiple operations** into a single execution, reducing network latency
3. **Apply conditional logic** based on API responses without round-trips
4. **Transform and process data** server-side before returning results

### UTCP vs Traditional CLI Approach

| Feature | UTCP Code-Mode | CLI Wrapper (archon_query.py) |
|---------|----------------|-------------------------------|
| **Batching** | ✅ Multiple operations in one call | ❌ One operation per invocation |
| **Conditional Logic** | ✅ Execute logic in sandbox | ❌ Requires multiple calls |
| **Data Processing** | ✅ Transform data server-side | ❌ Must process client-side |
| **Network Efficiency** | ✅ Minimal round-trips | ❌ One round-trip per operation |
| **Complex Workflows** | ✅ Full TypeScript capabilities | ⚠️ Limited to script logic |
| **Type Safety** | ✅ Full TypeScript types | ⚠️ Python type hints only |

### Example: The Power of Batching

**Traditional CLI (3 separate calls):**
```bash
python archon_query.py health_check
python archon_query.py find_tasks --status todo
python archon_query.py list_projects
```
Result: 3 network round-trips, ~600-900ms total

**UTCP Code-Mode (1 batched call):**
```typescript
const { result } = await client.callToolChain(`
  const health = await archon.health_check();
  const tasks = await archon.find_tasks({ status: "todo" });
  const projects = await archon.list_projects({});

  return { health, taskCount: tasks.tasks.length, projects };
`);
```
Result: 1 network round-trip, ~200-300ms total ⚡

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Your Application                        │
│  (TypeScript code using CodeModeUtcpClient)                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ callToolChain(typescript_code)
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  UTCP Code-Mode Server                       │
│  • Executes TypeScript in sandboxed environment             │
│  • Provides Archon tools as async functions                 │
│  • Handles batching and orchestration                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ MCP Protocol (HTTP)
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Archon MCP Server                           │
│  http://localhost:8051                                 │
│  • Task management                                          │
│  • RAG knowledge base                                       │
│  • Project operations                                       │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Node.js 18.0.0 or higher
- npm, yarn, or pnpm
- Access to Archon MCP server (default: http://localhost:8051)

### Setup

```bash
# Navigate to the server directory
cd ~/.claude/servers/code-execution

# Install dependencies
npm install

# Verify installation
npm run type-check
```

## Configuration

The server can be configured via environment variables:

```bash
# Archon MCP server URL (default: http://localhost:8051)
export ARCHON_SERVER_URL="http://localhost:8051"

# Request timeout in milliseconds (default: 30000)
export ARCHON_TIMEOUT="30000"

# Number of retry attempts (default: 3)
export ARCHON_RETRY_ATTEMPTS="3"

# Delay between retries in milliseconds (default: 1000)
export ARCHON_RETRY_DELAY="1000"
```

## Usage

### Starting the Server

```bash
# Start the server
npm start

# Or in development mode with watch
npm run dev
```

### Running Examples

The repository includes three comprehensive example files:

```bash
# Simple single operations
npm run example:simple

# Batched multi-operations
npm run example:batched

# Complex workflows with conditional logic
npm run example:complex
```

### Programmatic Usage

```typescript
import { CodeModeUtcpClient } from '@utcp/code-mode';

// Create and configure client
const client = await CodeModeUtcpClient.create();

await client.registerManual({
  name: 'archon',
  call_template_type: 'mcp',
  config: {
    mcpServers: {
      archon: {
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-fetch', 'http://localhost:8051'],
        env: {
          MCP_SERVER_URL: 'http://localhost:8051'
        }
      }
    }
  }
});

// Execute TypeScript code with Archon tools
const { result } = await client.callToolChain(`
  const health = await archon.health_check();
  const tasks = await archon.find_tasks({ status: "todo", limit: 10 });

  return {
    healthy: health.success,
    urgentTasks: tasks.tasks.filter(t => t.priority > 80).length
  };
`);

console.log(result);
```

## Available Archon Tools

All Archon MCP tools are available as async functions within the code-mode sandbox:

### Task Management

```typescript
// Find tasks with filters
const tasks = await archon.find_tasks({
  status: "todo",
  priority_min: 70,
  project_id: "proj-123",
  limit: 20
});

// Create a new task
const newTask = await archon.create_task({
  title: "Implement feature X",
  description: "Detailed description",
  project_id: "proj-123",
  priority: 80,
  status: "todo"
});

// Update task
const updated = await archon.update_task({
  task_id: "task-456",
  status: "doing",
  priority: 85
});

// Get task by ID
const task = await archon.get_task({ task_id: "task-456" });

// Delete task
await archon.delete_task({ task_id: "task-456" });
```

### Project Management

```typescript
// List projects
const projects = await archon.list_projects({ limit: 10 });

// Get project details
const project = await archon.get_project({ project_id: "proj-123" });

// Create project
const newProject = await archon.create_project({
  name: "New Project",
  description: "Project description",
  github_repo: "https://github.com/user/repo"
});

// Update project
await archon.update_project({
  project_id: "proj-123",
  status: "active"
});
```

### Knowledge Base (RAG)

```typescript
// Search knowledge base
const results = await archon.rag_search_knowledge_base({
  query: "authentication patterns",
  limit: 5,
  min_score: 0.7
});

// Find code examples
const examples = await archon.rag_code_examples({
  query: "React hooks",
  language: "typescript",
  limit: 3
});

// Get documentation sources
const sources = await archon.rag_get_sources();

// Search specific documentation
const docs = await archon.rag_search_docs({
  query: "API design",
  source_id: "source-123",
  limit: 5
});
```

### System Operations

```typescript
// Health check
const health = await archon.health_check();

// Get system info
const info = await archon.get_system_info();
```

## Example Use Cases

### 1. Dashboard Data Aggregation

```typescript
const { result } = await client.callToolChain(`
  const [health, todoTasks, doingTasks, projects] = await Promise.all([
    archon.health_check(),
    archon.find_tasks({ status: "todo" }),
    archon.find_tasks({ status: "doing" }),
    archon.list_projects({ limit: 10 })
  ]);

  return {
    system: {
      healthy: health.success,
      uptime_hours: (health.uptime_seconds / 3600).toFixed(1)
    },
    tasks: {
      todo: todoTasks.tasks.length,
      doing: doingTasks.tasks.length,
      urgent: todoTasks.tasks.filter(t => t.priority > 80).length
    },
    projects: {
      total: projects.projects.length,
      active: projects.projects.filter(p => p.status === 'active').length
    }
  };
`);
```

### 2. Intelligent Task Prioritization

```typescript
const { result } = await client.callToolChain(`
  const tasks = await archon.find_tasks({ status: "todo" });

  // Group by priority level
  const critical = tasks.tasks.filter(t => t.priority >= 90);
  const high = tasks.tasks.filter(t => t.priority >= 70 && t.priority < 90);
  const medium = tasks.tasks.filter(t => t.priority >= 40 && t.priority < 70);
  const low = tasks.tasks.filter(t => t.priority < 40);

  // Check for overdue tasks (older than 7 days with priority > 50)
  const now = Date.now();
  const overdue = tasks.tasks.filter(t => {
    const age = (now - new Date(t.created_at).getTime()) / (1000 * 60 * 60 * 24);
    return age > 7 && t.priority > 50;
  });

  return {
    distribution: {
      critical: critical.length,
      high: high.length,
      medium: medium.length,
      low: low.length
    },
    alerts: overdue.length > 0 ? [
      { level: 'WARNING', message: \`\${overdue.length} overdue tasks need attention\` }
    ] : [],
    topPriority: critical.slice(0, 5).map(t => ({
      id: t.task_id,
      title: t.title,
      priority: t.priority,
      project: t.project_name
    }))
  };
`);
```

### 3. Multi-Source Knowledge Search

```typescript
const { result } = await client.callToolChain(`
  // Search multiple topics in parallel
  const [authResults, apiResults, testResults] = await Promise.all([
    archon.rag_search_knowledge_base({ query: "authentication", limit: 3 }),
    archon.rag_search_knowledge_base({ query: "REST API", limit: 3 }),
    archon.rag_search_knowledge_base({ query: "testing", limit: 3 })
  ]);

  // Aggregate and rank all results
  const allResults = [
    ...authResults.results.map(r => ({ ...r, topic: 'auth' })),
    ...apiResults.results.map(r => ({ ...r, topic: 'api' })),
    ...testResults.results.map(r => ({ ...r, topic: 'testing' }))
  ];

  // Sort by score
  allResults.sort((a, b) => b.score - a.score);

  return {
    total_results: allResults.length,
    by_topic: {
      auth: authResults.total_results,
      api: apiResults.total_results,
      testing: testResults.total_results
    },
    top_results: allResults.slice(0, 5).map(r => ({
      topic: r.topic,
      score: r.score,
      source: r.metadata.source,
      preview: r.content.substring(0, 100)
    }))
  };
`);
```

### 4. Project Health Monitoring

```typescript
const { result } = await client.callToolChain(`
  const projects = await archon.list_projects({});

  const projectHealth = [];
  for (const project of projects.projects) {
    const tasks = await archon.find_tasks({ project_id: project.project_id });

    // Calculate health metrics
    const totalTasks = tasks.tasks.length;
    const todoCount = tasks.tasks.filter(t => t.status === 'todo').length;
    const doneCount = tasks.tasks.filter(t => t.status === 'done').length;

    const completionRate = totalTasks > 0 ? (doneCount / totalTasks * 100).toFixed(1) : 0;
    const todoRate = totalTasks > 0 ? (todoCount / totalTasks * 100).toFixed(1) : 0;

    // Health score (0-100)
    let score = 100;
    if (parseFloat(todoRate) > 70) score -= 30;  // Too many TODOs
    if (parseFloat(completionRate) < 20) score -= 20;  // Low completion

    projectHealth.push({
      name: project.name,
      id: project.project_id,
      health_score: Math.max(0, score),
      metrics: {
        total_tasks: totalTasks,
        completion_rate: completionRate + '%',
        todo_rate: todoRate + '%'
      },
      status: score >= 70 ? 'Healthy' : score >= 40 ? 'Fair' : 'Needs Attention'
    });
  }

  // Sort by health score
  projectHealth.sort((a, b) => b.health_score - a.health_score);

  return {
    total_projects: projectHealth.length,
    average_health: (projectHealth.reduce((sum, p) => sum + p.health_score, 0) / projectHealth.length).toFixed(1),
    projects: projectHealth
  };
`);
```

## When to Use UTCP vs Archon Skill

### Use UTCP Code-Mode When:

✅ You need to **batch multiple operations** together
✅ You need **conditional logic** based on API responses
✅ You need **data transformation** or aggregation
✅ You need **complex workflows** with multiple decision points
✅ You're building **automated systems** or **integrations**
✅ **Performance is critical** (minimize round-trips)

### Use Archon Skill When:

✅ You need **interactive CLI operations**
✅ You want **simple, one-off queries**
✅ You prefer **Python scripting** environment
✅ You need **command-line arguments** parsing
✅ You want **human-readable output** formatting
✅ You're working in **Claude Code sessions**

### Hybrid Approach:

You can use both! The Archon skill is great for ad-hoc queries and exploration, while UTCP code-mode excels at automated workflows and complex data operations.

## TypeScript Types

All Archon responses are fully typed. See `src/types.ts` for complete type definitions:

- `ArchonTask` - Task object with all fields
- `ArchonProject` - Project object
- `ArchonSearchResult` - RAG search result
- `ArchonRAGResponse` - Complete RAG response
- `ArchonHealthCheck` - System health status
- And more...

## Error Handling

UTCP code-mode provides error handling within the sandbox:

```typescript
const { result } = await client.callToolChain(`
  try {
    const task = await archon.get_task({ task_id: "task-123" });
    return { success: true, task };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      fallback: "Task not found, returning defaults"
    };
  }
`);
```

## Performance Tips

1. **Batch operations**: Combine multiple API calls into one execution
2. **Use Promise.all**: Execute independent operations in parallel
3. **Filter early**: Apply filters at the API level, not in code
4. **Limit results**: Use `limit` parameter to reduce data transfer
5. **Cache when possible**: Store frequently accessed data in variables

## Troubleshooting

### Connection Issues

If you can't connect to Archon MCP server:

```bash
# Check if server is running
curl http://localhost:8051/health

# Verify environment variables
echo $ARCHON_SERVER_URL

# Check server logs
npm start 2>&1 | tee server.log
```

### Type Errors

```bash
# Run type checking
npm run type-check

# Rebuild
npm run build
```

### Example Failures

```bash
# Run individual examples for debugging
npm run example:simple
npm run example:batched
npm run example:complex
```

## Development

### Project Structure

```
.claude/servers/archon/
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript configuration
├── README.md            # This file
├── src/
│   ├── server.ts        # Main UTCP server
│   ├── config.ts        # Configuration management
│   └── types.ts         # TypeScript type definitions
└── examples/
    ├── simple.ts        # Simple operation examples
    ├── batched.ts       # Batched operation examples
    └── complex.ts       # Complex workflow examples
```

### Building

```bash
# Compile TypeScript
npm run build

# Output will be in dist/
ls dist/
```

### Adding New Examples

Create a new file in `examples/` and add a script to `package.json`:

```json
{
  "scripts": {
    "example:myexample": "tsx examples/myexample.ts"
  }
}
```

## License

MIT

## Support

For issues or questions:

1. Check the examples in `examples/`
2. Review Archon MCP server documentation
3. Verify server connectivity with health check
4. Check server logs for errors

## Contributing

Contributions welcome! Please ensure:

- TypeScript compiles without errors (`npm run type-check`)
- Examples run successfully
- Types are properly defined
- Documentation is updated

---

**Built with ❤️ using UTCP Code-Mode and Archon MCP Server**
