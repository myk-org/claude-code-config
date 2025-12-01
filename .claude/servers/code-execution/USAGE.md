# How to Use UTCP Code-Mode with Claude Code

## ✅ Setup Complete!

The Archon UTCP Code-Mode MCP server is now configured in your Claude Code.

## How It Works

```
User: "Get all high priority tasks and generate a summary report"
  ↓
Claude Code calls MCP tool: call_tool_chain
  ↓
@utcp/code-mode-mcp executes TypeScript:
  const tasks = await archon.find_tasks({ status: 'todo' });
  const highPri = tasks.tasks.filter(t => t.priority > 80);
  return { count: highPri.length, tasks: highPri.map(t => t.title) };
  ↓
Results back to Claude
  ↓
Claude writes the summary report
```

## Available Tool

Claude Code now has access to **`call_tool_chain`** which executes TypeScript code with `archon.*` functions available.

### All Archon Functions Available

The TypeScript code can call any Archon MCP tool:
- `archon.health_check()`
- `archon.find_tasks({ status, project_id, limit, ... })`
- `archon.get_task({ task_id })`
- `archon.create_task({ project_id, title, description, ... })`
- `archon.update_task({ task_id, status, assignee, ... })`
- `archon.delete_task({ task_id })`
- `archon.list_projects({ limit, ... })`
- `archon.get_project({ project_id })`
- `archon.project_status({ project_id })`
- `archon.rag_search_knowledge_base({ query, limit, ... })`
- `archon.rag_search_code_examples({ query, limit })`
- `archon.rag_get_sources()`
- And all other tools exposed by Archon MCP

## Example Usage

### Simple Query
```
You: "Show me my TODO tasks"

Claude writes and executes:
const tasks = await archon.find_tasks({ status: 'todo' });
return tasks;
```

### Batched Operations
```
You: "Get project status and all todo tasks for that project"

Claude writes and executes:
const project = await archon.get_project({ project_id: 'proj-id' });
const tasks = await archon.find_tasks({
  project_id: project.id,
  status: 'todo'
});
return { project, tasks };
```

### Complex Workflow
```
You: "Find high priority tasks, search for related docs, and create a summary"

Claude writes and executes:
const tasks = await archon.find_tasks({ status: 'todo' });
const urgent = tasks.tasks.filter(t => t.priority > 80);

const searches = await Promise.all(
  urgent.map(task =>
    archon.rag_search_knowledge_base({
      query: task.title,
      limit: 3
    })
  )
);

return {
  urgentCount: urgent.length,
  tasks: urgent.map((task, i) => ({
    title: task.title,
    relatedDocs: searches[i].results.length
  }))
};
```

## Restart Required

**IMPORTANT:** Restart Claude Code to load the new MCP server:

```bash
# If running in terminal
Ctrl+C and restart: claude

# Changes take effect on next launch
```

## Verification

After restart, check that the MCP server loaded:

```bash
claude

# In Claude Code:
/mcp
# You should see "archon-codemode" in the list
```

## Benefits Over CLI Approach

### CLI Skill (Current)
- Sequential operations: call → wait → call → wait
- Each operation is a separate Bash command
- Context grows with each call
- Good for: Simple, single operations

### UTCP Code-Mode (New)
- Batched operations: single code block, multiple calls
- In-sandbox data processing before returning to Claude
- Claude can write complex business logic in TypeScript
- Good for: Complex workflows, data transformation, multi-step operations

## Both Work Together!

You can use both:
- **CLI Skill**: Quick single operations via `archon skill`
- **UTCP Code-Mode**: Complex batched workflows when Claude needs to write TypeScript

Claude will choose the best approach based on the task.
