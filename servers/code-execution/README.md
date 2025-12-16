# UTCP Code-Mode Server

A UTCP (Universal Tool Calling Protocol) code-mode server that provides direct, batched access to MCP servers through TypeScript code execution. Configure any MCP server integration and execute complex workflows with batching and conditional logic.

## What is UTCP Code-Mode?

UTCP code-mode is a powerful protocol that allows you to:

1. **Execute TypeScript code in a sandboxed environment** with MCP tools available as async functions
2. **Batch multiple operations** into a single execution, reducing network latency
3. **Apply conditional logic** based on API responses without round-trips
4. **Transform and process data** server-side before returning results

### UTCP vs Traditional CLI Approach

| Feature | UTCP Code-Mode | CLI Wrapper |
|---------|----------------|-------------|
| **Batching** | ✅ Multiple operations in one call | ❌ One operation per invocation |
| **Conditional Logic** | ✅ Execute logic in sandbox | ❌ Requires multiple calls |
| **Data Processing** | ✅ Transform data server-side | ❌ Must process client-side |
| **Network Efficiency** | ✅ Minimal round-trips | ❌ One round-trip per operation |
| **Complex Workflows** | ✅ Full TypeScript capabilities | ⚠️ Limited to script logic |
| **Type Safety** | ✅ Full TypeScript types | ⚠️ Limited type safety |

### Example: The Power of Batching

**Traditional CLI (3 separate calls):**
```bash
mcp-tool health_check
mcp-tool list_items --status active
mcp-tool list_projects
```
Result: 3 network round-trips, ~600-900ms total

**UTCP Code-Mode (1 batched call):**
```typescript
const { result } = await client.callToolChain(`
  const health = await mcp.health_check();
  const items = await mcp.list_items({ status: "active" });
  const projects = await mcp.list_projects({});

  return { health, itemCount: items.length, projects };
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
│  • Provides MCP tools as async functions                    │
│  • Handles batching and orchestration                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          │ MCP Protocol
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Your MCP Server(s)                          │
│  • Configure any MCP server                                 │
│  • Multiple servers supported                               │
│  • Tools available as async functions                       │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Node.js 18.0.0 or higher
- npm, yarn, or pnpm
- One or more MCP servers to connect to

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

### MCP Server Configuration

Create JSON configuration files in the `configs/` directory. Each file defines one or more MCP server connections:

```json
{
  "manual_call_templates": [
    {
      "name": "myserver",
      "call_template_type": "mcp",
      "config": {
        "mcpServers": {
          "myserver": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-fetch", "http://localhost:8051"],
            "env": {
              "MCP_SERVER_URL": "http://localhost:8051"
            }
          }
        }
      }
    }
  ]
}
```

The server automatically loads all `.json` files from the `configs/` directory at startup. See `configs/example.json.example` for a complete example.

## Usage

### Starting the Server

```bash
# Start the server
npm start

# Or in development mode with watch
npm run dev
```

### Programmatic Usage

```typescript
import { CodeModeUtcpClient } from '@utcp/code-mode';

// Create and configure client
const client = await CodeModeUtcpClient.create();

// Register your MCP server
await client.registerManual({
  name: 'myserver',
  call_template_type: 'mcp',
  config: {
    mcpServers: {
      myserver: {
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-fetch', 'http://localhost:8051'],
        env: {
          MCP_SERVER_URL: 'http://localhost:8051'
        }
      }
    }
  }
});

// Execute TypeScript code with MCP tools
const { result } = await client.callToolChain(`
  // Call MCP server tools as async functions
  const health = await myserver.health_check();
  const items = await myserver.list_items({ status: "active", limit: 10 });

  // Process and transform data
  return {
    healthy: health.success,
    totalItems: items.length,
    activeItems: items.filter(i => i.status === "active").length
  };
`);

console.log(result);
```

## Using MCP Tools

All MCP server tools registered through configuration files are available as async functions within the code-mode sandbox. The function names correspond to the tool names exposed by your MCP server.

### Example: Calling MCP Tools

```typescript
// If you registered an MCP server named 'myserver', its tools are available:
const { result } = await client.callToolChain(`
  // Health check (if your MCP server provides this)
  const health = await myserver.health_check();

  // List items (example tool)
  const items = await myserver.list_items({
    status: "active",
    limit: 20
  });

  // Get specific item
  const item = await myserver.get_item({ id: "item-123" });

  // Process data before returning
  return {
    healthy: health.success,
    totalItems: items.length,
    item: item
  };
`);
```

### Multiple MCP Servers

You can register and use multiple MCP servers in the same code execution:

```typescript
const { result } = await client.callToolChain(`
  // Call tools from different MCP servers
  const data1 = await server1.get_data();
  const data2 = await server2.fetch_info();

  // Combine and process results
  return {
    combined: [...data1, ...data2],
    total: data1.length + data2.length
  };
`);
```

## Example Use Cases

### 1. Batching Multiple Operations

```typescript
const { result } = await client.callToolChain(`
  // Execute multiple operations in parallel
  const [status, items, projects] = await Promise.all([
    myserver.get_status(),
    myserver.list_items({ status: "active" }),
    myserver.list_projects({ limit: 10 })
  ]);

  // Process and aggregate results
  return {
    system: {
      healthy: status.success,
      uptime: status.uptime
    },
    statistics: {
      totalItems: items.length,
      activeItems: items.filter(i => i.active).length,
      totalProjects: projects.length
    }
  };
`);
```

### 2. Conditional Logic and Data Processing

```typescript
const { result } = await client.callToolChain(`
  const items = await myserver.list_items({ status: "pending" });

  // Group by priority level
  const critical = items.filter(i => i.priority >= 90);
  const high = items.filter(i => i.priority >= 70 && i.priority < 90);
  const medium = items.filter(i => i.priority >= 40 && i.priority < 70);
  const low = items.filter(i => i.priority < 40);

  // Check for stale items (older than 7 days with high priority)
  const now = Date.now();
  const stale = items.filter(i => {
    const age = (now - new Date(i.created_at).getTime()) / (1000 * 60 * 60 * 24);
    return age > 7 && i.priority > 50;
  });

  return {
    distribution: {
      critical: critical.length,
      high: high.length,
      medium: medium.length,
      low: low.length
    },
    alerts: stale.length > 0 ? [
      { level: 'WARNING', message: \`\${stale.length} stale items need attention\` }
    ] : [],
    topPriority: critical.slice(0, 5).map(i => ({
      id: i.id,
      title: i.title,
      priority: i.priority
    }))
  };
`);
```

### 3. Parallel Searches with Aggregation

```typescript
const { result } = await client.callToolChain(`
  // Search multiple categories in parallel
  const [results1, results2, results3] = await Promise.all([
    myserver.search({ query: "category1", limit: 5 }),
    myserver.search({ query: "category2", limit: 5 }),
    myserver.search({ query: "category3", limit: 5 })
  ]);

  // Aggregate and rank all results
  const allResults = [
    ...results1.map(r => ({ ...r, category: 'category1' })),
    ...results2.map(r => ({ ...r, category: 'category2' })),
    ...results3.map(r => ({ ...r, category: 'category3' }))
  ];

  // Sort by relevance score
  allResults.sort((a, b) => b.score - a.score);

  return {
    total_results: allResults.length,
    by_category: {
      category1: results1.length,
      category2: results2.length,
      category3: results3.length
    },
    top_results: allResults.slice(0, 10)
  };
`);
```

### 4. Complex Multi-Step Workflows

```typescript
const { result } = await client.callToolChain(`
  const projects = await myserver.list_projects({});

  const projectMetrics = [];
  for (const project of projects) {
    const items = await myserver.list_items({ project_id: project.id });

    // Calculate completion metrics
    const total = items.length;
    const completed = items.filter(i => i.status === 'done').length;
    const pending = items.filter(i => i.status === 'pending').length;

    const completionRate = total > 0 ? (completed / total * 100).toFixed(1) : 0;

    // Calculate health score
    let score = 100;
    if (pending / total > 0.7) score -= 30;
    if (completionRate < 20) score -= 20;

    projectMetrics.push({
      name: project.name,
      id: project.id,
      health_score: Math.max(0, score),
      metrics: {
        total_items: total,
        completion_rate: completionRate + '%',
        pending_count: pending
      },
      status: score >= 70 ? 'Healthy' : score >= 40 ? 'Fair' : 'Needs Attention'
    });
  }

  // Sort by health score
  projectMetrics.sort((a, b) => b.health_score - a.health_score);

  return {
    total_projects: projectMetrics.length,
    average_health: (projectMetrics.reduce((sum, p) => sum + p.health_score, 0) / projectMetrics.length).toFixed(1),
    projects: projectMetrics
  };
`);
```

## When to Use UTCP Code-Mode

### Use UTCP Code-Mode When:

✅ You need to **batch multiple operations** together
✅ You need **conditional logic** based on API responses
✅ You need **data transformation** or aggregation
✅ You need **complex workflows** with multiple decision points
✅ You're building **automated systems** or **integrations**
✅ **Performance is critical** (minimize round-trips)

### Use Traditional CLI/Direct Tools When:

✅ You need **interactive CLI operations**
✅ You want **simple, one-off queries**
✅ You prefer **simpler scripting** environments
✅ You need **command-line arguments** parsing
✅ You want **human-readable output** formatting

### Hybrid Approach:

You can use both! Traditional tools are great for ad-hoc queries and exploration, while UTCP code-mode excels at automated workflows and complex data operations.

## TypeScript Types

Define your own TypeScript types for MCP server responses. See `src/types.ts` for type definition patterns. You can create interfaces for your MCP server's data structures to get full type safety.

## Error Handling

UTCP code-mode provides error handling within the sandbox:

```typescript
const { result } = await client.callToolChain(`
  try {
    const item = await myserver.get_item({ id: "item-123" });
    return { success: true, item };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      fallback: "Item not found, returning defaults"
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

If you can't connect to your MCP server:

```bash
# Check if your MCP server is running
curl http://localhost:8051/health  # Adjust URL to your server

# Verify configuration files in configs/
ls -la configs/*.json

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

### Configuration Issues

```bash
# Verify config files are valid JSON
for f in configs/*.json; do echo "$f" && cat "$f" | jq .; done
```

## Development

### Project Structure

```
servers/code-execution/
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript configuration
├── README.md            # This file
├── configs/             # MCP server configurations
│   └── *.json          # JSON config files
└── src/
    ├── server.ts        # Main UTCP server
    └── types.ts         # TypeScript type definitions
```

### Building

```bash
# Compile TypeScript
npm run build

# Output will be in dist/
ls dist/
```

### Adding New MCP Servers

Create a new JSON file in `configs/` directory with your MCP server configuration. The server will automatically load it on startup.

## License

MIT

## Support

For issues or questions:

1. Review your MCP server documentation
2. Verify server connectivity with health check
3. Check configuration files in `configs/`
4. Check server logs for errors

## Contributing

Contributions welcome! Please ensure:

- TypeScript compiles without errors (`npm run type-check`)
- Types are properly defined
- Documentation is updated

---

**Built with UTCP Code-Mode**
