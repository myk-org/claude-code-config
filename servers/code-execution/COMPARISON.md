# Archon UTCP vs CLI: Detailed Comparison

This document provides a detailed comparison between the UTCP code-mode approach and the traditional CLI wrapper approach for accessing Archon.

## Architecture Comparison

### CLI Wrapper Architecture (archon_query.py)

```
┌──────────────┐
│ Claude Code  │
│  Session     │
└──────┬───────┘
       │
       │ Bash tool invoke
       │ python archon_query.py find_tasks --status todo
       │
┌──────▼───────────┐
│  archon_query.py │ ← Python script
│  (CLI wrapper)   │
└──────┬───────────┘
       │
       │ HTTP request
       │
┌──────▼───────────┐
│  Archon MCP      │
│  Server          │
│  :8051           │
└──────────────────┘
```

**Characteristics:**
- ✅ Simple, straightforward
- ✅ Easy to debug
- ✅ Works in any shell environment
- ❌ One operation per invocation
- ❌ No batching capability
- ❌ High latency for multiple operations
- ❌ Limited conditional logic

### UTCP Code-Mode Architecture

```
┌────────────────────────────────┐
│   Your Application             │
│   (TypeScript)                 │
└────────┬───────────────────────┘
         │
         │ callToolChain(typescript_code)
         │
┌────────▼────────────────────────┐
│  UTCP Code-Mode Server          │
│  • Sandboxed TypeScript runtime │
│  • Batches operations           │
│  • Conditional logic            │
│  • Data transformation          │
└────────┬────────────────────────┘
         │
         │ MCP Protocol (HTTP)
         │
┌────────▼────────────────────────┐
│  Archon MCP Server              │
│  :8051                          │
└─────────────────────────────────┘
```

**Characteristics:**
- ✅ Batch multiple operations
- ✅ Conditional logic in sandbox
- ✅ Complex data transformations
- ✅ Minimal network latency
- ✅ Full TypeScript capabilities
- ⚠️ More complex setup
- ⚠️ Requires Node.js

## Performance Comparison

### Scenario 1: Dashboard Data (Health + Tasks + Projects)

**CLI Approach:**
```bash
# 3 separate invocations = 3 network round-trips
time python archon_query.py health_check
# ~300ms

time python archon_query.py find_tasks --status todo
# ~300ms

time python archon_query.py list_projects
# ~300ms

# TOTAL: ~900ms
```

**UTCP Approach:**
```typescript
const start = Date.now();
const { result } = await client.callToolChain(`
  const health = await archon.health_check();
  const tasks = await archon.find_tasks({ status: "todo" });
  const projects = await archon.list_projects({});
  return { health, tasks, projects };
`);
console.log(`Time: ${Date.now() - start}ms`);
// TOTAL: ~300ms
```

**Performance Gain: 3x faster ⚡**

---

### Scenario 2: Multi-Project Task Analysis

**CLI Approach:**
```bash
# Get all projects first
python archon_query.py list_projects > projects.json

# For each project, get tasks (sequential)
for project_id in $(jq -r '.projects[].project_id' projects.json); do
  python archon_query.py find_tasks --project-id "$project_id"
done

# Process results separately
python process_results.py

# TOTAL: ~300ms + (N × 300ms) + 100ms
# For 5 projects: ~1,900ms
```

**UTCP Approach:**
```typescript
const { result } = await client.callToolChain(`
  const projects = await archon.list_projects({});

  const analysis = [];
  for (const project of projects.projects.slice(0, 5)) {
    const tasks = await archon.find_tasks({ project_id: project.project_id });
    analysis.push({
      name: project.name,
      total: tasks.tasks.length,
      by_status: {
        todo: tasks.tasks.filter(t => t.status === 'todo').length,
        doing: tasks.tasks.filter(t => t.status === 'doing').length
      }
    });
  }
  return analysis;
`);

// TOTAL: ~600ms (batched execution)
```

**Performance Gain: 3-4x faster ⚡**

---

### Scenario 3: Conditional Search with Fallback

**CLI Approach:**
```bash
# Primary search
python archon_query.py rag_search --query "React hooks useState" --min-score 0.7 > results.json

# Check if enough results (requires separate script)
count=$(jq '.total_results' results.json)

if [ "$count" -lt 3 ]; then
  # Fallback search
  python archon_query.py rag_search --query "React hooks" --min-score 0.5 > results.json
fi

# Process results
python format_results.py results.json

# TOTAL: 300ms + 50ms + (conditional: 300ms) + 100ms = ~750ms
```

**UTCP Approach:**
```typescript
const { result } = await client.callToolChain(`
  // Primary search
  let results = await archon.rag_search_knowledge_base({
    query: "React hooks useState",
    limit: 5,
    min_score: 0.7
  });

  // Conditional fallback (no network round-trip!)
  if (results.results.length < 3) {
    results = await archon.rag_search_knowledge_base({
      query: "React hooks",
      limit: 5,
      min_score: 0.5
    });
  }

  // Process in place
  return {
    found: results.results.length,
    top: results.results.map(r => ({
      score: r.score,
      preview: r.content.substring(0, 100)
    }))
  };
`);

// TOTAL: ~300-600ms (conditional logic in sandbox)
```

**Performance Gain: 1.5-2x faster ⚡**

## Capability Comparison

| Capability | CLI Wrapper | UTCP Code-Mode |
|-----------|-------------|----------------|
| **Single Operations** | ✅ Excellent | ✅ Excellent |
| **Batched Operations** | ❌ Not supported | ✅ Native |
| **Conditional Logic** | ⚠️ Via shell scripts | ✅ Full TypeScript |
| **Data Transformation** | ⚠️ External tools (jq) | ✅ Native JavaScript |
| **Type Safety** | ⚠️ Python hints only | ✅ Full TypeScript |
| **Parallel Execution** | ⚠️ Manual with `&` | ✅ Promise.all |
| **Error Handling** | ⚠️ Shell exit codes | ✅ Try/catch blocks |
| **Debugging** | ✅ Simple stdout | ⚠️ Requires debug tools |
| **Interactive Use** | ✅ Very easy | ⚠️ Requires code |
| **Automation** | ⚠️ Shell scripts | ✅ Excellent |
| **Complex Workflows** | ❌ Difficult | ✅ Excellent |
| **Setup Complexity** | ✅ Minimal (just Python) | ⚠️ Requires Node.js |

## Code Complexity Comparison

### Example: Task Priority Analysis

**CLI Approach (~40 lines across 3 files):**

```bash
# get_tasks.sh
#!/bin/bash
python archon_query.py find_tasks --status todo > tasks.json
```

```python
# analyze_priorities.py
import json
import sys

with open('tasks.json') as f:
    data = json.load(f)

tasks = data['tasks']
critical = [t for t in tasks if t['priority'] >= 90]
high = [t for t in tasks if 70 <= t['priority'] < 90]
medium = [t for t in tasks if 40 <= t['priority'] < 70]
low = [t for t in tasks if t['priority'] < 40]

result = {
    'distribution': {
        'critical': len(critical),
        'high': len(high),
        'medium': len(medium),
        'low': len(low)
    }
}

print(json.dumps(result, indent=2))
```

```bash
# run_analysis.sh
#!/bin/bash
./get_tasks.sh
python analyze_priorities.py
```

**UTCP Approach (~15 lines, single file):**

```typescript
const { result } = await client.callToolChain(`
  const tasks = await archon.find_tasks({ status: "todo" });

  const critical = tasks.tasks.filter(t => t.priority >= 90);
  const high = tasks.tasks.filter(t => t.priority >= 70 && t.priority < 90);
  const medium = tasks.tasks.filter(t => t.priority >= 40 && t.priority < 70);
  const low = tasks.tasks.filter(t => t.priority < 40);

  return {
    distribution: {
      critical: critical.length,
      high: high.length,
      medium: medium.length,
      low: low.length
    }
  };
`);
```

**Simplicity: UTCP wins - 62% less code, single file**

## Use Case Recommendations

### Use CLI Wrapper When:

✅ **Quick ad-hoc queries**
```bash
# Fast one-liners
python archon_query.py health_check
python archon_query.py find_tasks --status doing
```

✅ **Interactive exploration**
```bash
# Exploring the API
python archon_query.py --help
python archon_query.py rag_search --query "testing" --limit 5
```

✅ **Simple automation**
```bash
# Basic cron jobs
0 9 * * * python archon_query.py find_tasks --status todo | mail -s "Daily Tasks" user@example.com
```

✅ **No Node.js available**
```bash
# Python-only environments
python archon_query.py list_projects
```

### Use UTCP Code-Mode When:

✅ **Building applications**
```typescript
// Complex application logic
const dashboard = await buildDashboard();
const insights = await analyzeProjects();
const recommendations = await generateRecommendations();
```

✅ **Performance-critical workflows**
```typescript
// Minimize latency with batching
const { result } = await client.callToolChain(`
  // 10 operations in one batch
  const [op1, op2, op3, ...] = await Promise.all([...]);
  return processResults([op1, op2, op3, ...]);
`);
```

✅ **Complex data processing**
```typescript
// Advanced transformations
const { result } = await client.callToolChain(`
  const data = await fetchData();
  const processed = data.map(transform).filter(validate).reduce(aggregate);
  return generateInsights(processed);
`);
```

✅ **Conditional workflows**
```typescript
// Decision logic without round-trips
const { result } = await client.callToolChain(`
  const metrics = await getMetrics();
  if (metrics.critical > threshold) {
    return await triggerAlert();
  } else {
    return await normalFlow();
  }
`);
```

## Migration Guide

### From CLI to UTCP

**CLI Version:**
```bash
python archon_query.py find_tasks --status todo
```

**UTCP Version:**
```typescript
const { result } = await client.callToolChain(`
  const tasks = await archon.find_tasks({ status: "todo" });
  return tasks;
`);
```

**CLI Script:**
```bash
#!/bin/bash
HEALTH=$(python archon_query.py health_check)
TASKS=$(python archon_query.py find_tasks --status todo)
echo "Health: $HEALTH"
echo "Tasks: $TASKS"
```

**UTCP Equivalent:**
```typescript
const { result } = await client.callToolChain(`
  const health = await archon.health_check();
  const tasks = await archon.find_tasks({ status: "todo" });

  return {
    health: health.health.status,
    taskCount: tasks.tasks.length
  };
`);

console.log(`Health: ${result.health}`);
console.log(`Tasks: ${result.taskCount}`);
```

## Hybrid Approach: Best of Both Worlds

You can use both approaches based on the situation:

```bash
# Use CLI for quick checks
alias archon-health="python /path/to/archon_query.py health_check"
alias archon-todo="python /path/to/archon_query.py find_tasks --status todo"

# Use UTCP for complex workflows
node my-workflow.js  # Uses UTCP code-mode
```

**Example Workflow:**

1. **Explore with CLI**: Quick investigation
   ```bash
   python archon_query.py rag_search --query "authentication"
   ```

2. **Build with UTCP**: Production automation
   ```typescript
   // Production monitoring dashboard
   const dashboard = await buildProductionDashboard();
   ```

3. **Debug with CLI**: Fast troubleshooting
   ```bash
   python archon_query.py get_task --task-id task-123
   ```

## Summary

| Aspect | CLI Winner | UTCP Winner |
|--------|-----------|-------------|
| Simplicity | ✅ | |
| Performance | | ✅ |
| Batching | | ✅ |
| Conditional Logic | | ✅ |
| Data Processing | | ✅ |
| Type Safety | | ✅ |
| Quick Queries | ✅ | |
| Interactive Use | ✅ | |
| Complex Workflows | | ✅ |
| Automation | | ✅ |
| Setup Time | ✅ | |
| Debugging | ✅ | |

**Bottom Line:**
- **CLI**: Perfect for interactive exploration and simple queries
- **UTCP**: Perfect for production automation and complex workflows
- **Both**: Use the right tool for the right job!

---

**Recommendation**: Start with CLI for exploration, migrate to UTCP for automation and performance-critical workflows.
