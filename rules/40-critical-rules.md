# Critical Rules

## Parallel Execution (MANDATORY)

**Before EVERY response:** Can operations run in parallel?
- **YES** → Execute ALL in ONE message
- **NO** → PROVE dependency

### Examples

❌ **WRONG:** Agent1 → wait → Agent2 → wait → Agent3
✅ **RIGHT:** Agent1 + Agent2 + Agent3 in ONE message

Always maximize parallelism. Only execute sequentially when there's a proven dependency between operations.

---

## Temp Files

**ALL temp files MUST go to `/tmp/claude/`** - NEVER create temp files in project directory.

This keeps the project directory clean and prevents accidental commits of temporary files.

---

## Python Execution with uv

**MANDATORY** - When running arbitrary Python files:
- ✅ **ONLY** use `uv run --with <package>` syntax
- ❌ **FORBIDDEN** - `uv run pip install` - NEVER use this

### Examples

✅ **Correct:**
```bash
uv run --with requests script.py
uv run --with requests --with pandas script.py
```

❌ **Wrong:**
```bash
uv run pip install requests
```

The `--with` syntax ensures dependencies are managed per-execution without modifying the environment.
