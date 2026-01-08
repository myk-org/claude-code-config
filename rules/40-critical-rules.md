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

---

## External Git Repository Exploration

**When exploring external Git repositories, clone locally first.**

Clone to `/tmp/claude/` and explore using Read/Glob/Grep - NOT via WebFetch.

### Clone the Bare Minimum

- ✅ Use `--depth 1` for shallow clone (no history)
- ✅ Use sparse checkout if only specific directories are needed
- ✅ Delete the clone when done if not needed

### Examples

✅ **Correct:**
```bash
# Shallow clone to temp directory
git clone --depth 1 https://github.com/org/repo.git /tmp/claude/repo

# Sparse checkout for specific directory only
git clone --depth 1 --filter=blob:none --sparse https://github.com/org/repo.git /tmp/claude/repo
cd /tmp/claude/repo && git sparse-checkout set src/utils

# Clean up when done
rm -rf /tmp/claude/repo
```

❌ **Wrong:**
```bash
# Full clone with history
git clone https://github.com/org/repo.git /tmp/claude/repo

# Using WebFetch to browse repository files
WebFetch(https://github.com/org/repo/blob/main/src/file.py)
```

Local exploration is faster, more reliable, and provides full file access without web scraping limitations.
