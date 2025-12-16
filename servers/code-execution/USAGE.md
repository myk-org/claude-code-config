# How to Use UTCP Code-Mode

## Overview

The UTCP Code-Mode server enables batched TypeScript code execution with MCP server tools available as async functions.

## How It Works

```
Your Application
  ↓
Calls: client.callToolChain(typescript_code)
  ↓
UTCP Code-Mode Server executes TypeScript:
  const items = await myserver.list_items({ status: 'active' });
  const filtered = items.filter(i => i.priority > 80);
  return { count: filtered.length, items: filtered.map(i => i.title) };
  ↓
Results returned to your application
  ↓
Process the results
```

## Available Functionality

The server provides **`callToolChain`** which executes TypeScript code with your configured MCP server tools available as async functions.

### MCP Server Functions

The TypeScript code can call any tool exposed by your configured MCP servers. Function names correspond to the tool names provided by your MCP server. For example:

- `myserver.health_check()`
- `myserver.list_items({ status, limit, ... })`
- `myserver.get_item({ id })`
- `myserver.create_item({ title, description, ... })`
- `myserver.update_item({ id, status, ... })`
- And any other tools your MCP server exposes

## Example Usage

### Simple Query
```typescript
const { result } = await client.callToolChain(`
  const items = await myserver.list_items({ status: 'active' });
  return items;
`);
```

### Batched Operations
```typescript
const { result } = await client.callToolChain(`
  const project = await myserver.get_project({ id: 'proj-id' });
  const items = await myserver.list_items({
    project_id: project.id,
    status: 'active'
  });
  return { project, items };
`);
```

### Complex Workflow
```typescript
const { result } = await client.callToolChain(`
  const items = await myserver.list_items({ status: 'pending' });
  const urgent = items.filter(i => i.priority > 80);

  const details = await Promise.all(
    urgent.map(item =>
      myserver.get_item_details({
        id: item.id,
        include_metadata: true
      })
    )
  );

  return {
    urgentCount: urgent.length,
    items: urgent.map((item, i) => ({
      title: item.title,
      details: details[i]
    }))
  };
`);
```

## Benefits Over Traditional Approach

### Traditional CLI/Direct Tools
- Sequential operations: call → wait → call → wait
- Each operation is a separate invocation
- Must process data client-side
- Good for: Simple, single operations

### UTCP Code-Mode
- Batched operations: single code block, multiple calls
- In-sandbox data processing before returning
- Complex business logic in TypeScript
- Good for: Complex workflows, data transformation, multi-step operations

## Hybrid Approach

You can combine both approaches:
- **Direct tools**: Quick single operations
- **UTCP Code-Mode**: Complex batched workflows and data processing

Choose the best approach based on your task requirements.
