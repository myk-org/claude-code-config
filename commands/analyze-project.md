---
name: analyze-project
description: Analyze codebase and store entities, relationships, and context in graphiti-memory
skipConfirmation: true
---

# Analyze Project Command

Analyzes a codebase and stores all entities, relationships, and context in the graphiti-memory MCP server.

## 🚨 CRITICAL: 100% DELEGATION ARCHITECTURE

**THE ORCHESTRATOR DOES NOTHING EXCEPT:**
1. Call Task tool to delegate to agents
2. Display agent responses to user
3. Move to next phase

**THE ORCHESTRATOR NEVER:**
- Uses Glob, Grep, Read, or any file tools
- Runs bash commands (except Task delegation)
- Processes data or lists
- Does any logic or calculations
- Calls MCP tools directly

**Each invocation is INDEPENDENT:**
- Treat every `/analyze-project` call as a fresh session
- Do NOT rely on state from previous invocations
- All state is managed by agents and stored in temp files

---

## Usage

- `/analyze-project` - Analyze current project (incremental if exists)
- `/analyze-project --full` - Force full re-analysis
- `/analyze-project --name custom-name` - Use custom group_id

---

## Storage Locations

**Persistent files** (survive reboots, project-specific):
- Location: `${PWD}/.analyze-project/`
- Contains: `previous_hashes.json`, `project_info.json`
- Should be added to `.gitignore`

**Temporary files** (session-only, discarded):
- Location: `/tmp/claude/analyze-project/`
- Contains: batch analysis files, intermediate data
- Automatically cleaned up by system

---

## Prerequisites Check

**DELEGATE to graphiti-memory-manager:**

```
Check if the graphiti-memory server is available by calling get_status.

If the call succeeds and returns status: "ok", respond with:
✅ graphiti-memory server is available

If the call fails or returns an error, respond with:
❌ graphiti-memory server is not available
```

**Display agent response.**

**If NOT available, display error and STOP:**

```
❌ ERROR: graphiti-memory MCP server is not available

This command requires the graphiti-memory MCP server to be configured and running.

To set up graphiti-memory:
1. Ensure the MCP server is configured in your ~/.claude.json
2. Verify the server is running and connected to the database
3. Check the server logs for any connection errors

Run this command again once graphiti-memory is properly configured.
```

---

## Phase 1: Project Initialization

Display: `🔍 Phase 1: Initializing project analysis...`

**DELEGATE to bash-expert:**

```
Initialize project analysis with the following steps:

1. Parse arguments from: ${ARGUMENTS}
   - Check for --full flag (sets IS_FULL_ANALYSIS=true)
   - Check for --name <custom-name> (sets CUSTOM_NAME)

2. Determine project name:
   - If CUSTOM_NAME is set, use it as PROJECT_NAME
   - Otherwise, use $(basename "$PWD") as PROJECT_NAME

3. Set GROUP_ID="${PROJECT_NAME}"

4. Detect project type by checking for configuration files:
   - Python: pyproject.toml, setup.py, requirements.txt
   - Node.js: package.json
   - Go: go.mod
   - Java: pom.xml, build.gradle
   - Rust: Cargo.toml

5. Detect framework from dependencies:
   - Python: FastAPI, Flask, Django
   - Node.js: React, Vue, Angular, Express
   - Java: Maven, Gradle

6. Create directories:
   - mkdir -p "${PWD}/.analyze-project"  (persistent)
   - mkdir -p /tmp/claude/analyze-project       (temporary)

7. Write project info to ${PWD}/.analyze-project/project_info.json:
   {
     "project_name": "...",
     "group_id": "...",
     "working_dir": "$PWD",
     "is_full_analysis": true/false,
     "project_type": "...",
     "language": "...",
     "framework": "..."
   }

8. Return a brief summary:
   🏷️  Project: <project_name>
   📂 Working directory: <pwd>
   🔧 Type: <project_type> (<language>)
   📦 Framework: <framework>
   🔄 Mode: <Full Analysis / Incremental Analysis>
```

**Display agent response.**

---

## Phase 2: Check Previous Analysis

Display: `🔍 Phase 2: Checking for previous analysis...`

**DELEGATE to graphiti-memory-manager:**

```
Check for previous analysis of the project.

1. Read project info from ${PWD}/.analyze-project/project_info.json
2. Extract GROUP_ID and PROJECT_NAME
3. Call search_nodes with:
   - query: "project metadata ${PROJECT_NAME}"
   - group_ids: ["${GROUP_ID}"]
   - max_nodes: 5

4. If nodes are found, respond with:
   📋 FOUND: Previous analysis exists (X nodes found)

5. If no nodes are found, respond with:
   📋 NOT_FOUND: No previous analysis exists

6. Determine analysis mode:
   - If --full flag was passed (IS_FULL_ANALYSIS=true):
     → Add "Will perform full re-analysis (--full flag)"
   - Else if NO previous analysis found (step 5 returned NOT_FOUND):
     → Set IS_FULL_ANALYSIS=true in project_info.json
     → Add "Will perform full analysis (no previous data)"
   - Else (previous analysis exists, no --full flag):
     → Add "Will perform incremental update"
```

**Display agent response.**

---

## Phase 3: File Discovery

Display: `🔍 Phase 3: Discovering source files...`

**DELEGATE to bash-expert:**

```
Discover source files for analysis:

1. Read project_info.json from ${PWD}/.analyze-project/
2. Determine file patterns based on project_type:
   - Python: **/*.py
   - Node.js: **/*.{js,ts,jsx,tsx,mjs,cjs}
   - Go: **/*.go
   - Java: **/*.java
   - Rust: **/*.rs
   - Unknown: **/*.{py,js,ts,go,java,rs,c,cpp,h,hpp}

3. Find all matching files recursively from current directory

4. Apply smart filtering (EXCLUDE):
   - node_modules/, vendor/, __pycache__/, .git/, .venv/, venv/, .tox/
   - dist/, build/, target/, .gradle/, out/, .next/, .nuxt/, .cache/
   - *.pyc, *.pyo, .eggs/, *.egg-info/
   - .mypy_cache/, .pytest_cache/, coverage/, .coverage
   - tmp/, temp/

5. Write filtered file list to /tmp/claude/analyze-project/all_files.txt

6. Count total files

7. Return summary:
   ✅ Found: <count> source files
   📄 File list: /tmp/claude/analyze-project/all_files.txt
```

**Display agent response.**

---

## Phase 4: Calculate Changes (Incremental Mode)

Display: `🔍 Phase 4: Calculating changes...`

**DELEGATE to bash-expert:**

```
Calculate file changes for incremental analysis:

1. Read project_info.json from ${PWD}/.analyze-project/
2. Check IS_FULL_ANALYSIS flag
3. If IS_FULL_ANALYSIS is true:
   - Copy all_files.txt to files_to_analyze.txt
   - Return: "Full analysis mode: all files will be analyzed"
   - SKIP remaining steps

4. For incremental mode, read all_files.txt
5. Calculate SHA256 hash for each file:
   sha256sum "$file" | cut -d' ' -f1

6. Write current hashes to ${PWD}/.analyze-project/current_hashes.json:
   {
     "path/to/file.py": "sha256hash",
     ...
   }

7. Check if ${PWD}/.analyze-project/previous_hashes.json exists:
   - If NOT exists: This is first analysis, analyze all files
   - If exists: Compare hashes to find changed files

8. If previous_hashes.json exists, compare:
   - New files: in current, not in previous
   - Changed files: different hash
   - Deleted files: in previous, not in current
   - Unchanged files: same hash

9. Write new + changed files to /tmp/claude/analyze-project/files_to_analyze.txt

10. Return summary:
    📊 Change Summary:
       New files: <count>
       Changed files: <count>
       Deleted files: <count>
       Unchanged files: <count>
       Files to analyze: <count>

11. If 0 files to analyze, add:
    ✅ No changes detected - project is up to date!
```

**Display agent response.**

**If 0 files to analyze, STOP HERE with success message.**

---

## Phase 5: Code Analysis

Display: `🔍 Phase 5: Analyzing code...`

**DELEGATE to appropriate language expert (determine from project_info.json):**
- Python → `python-expert`
- JavaScript/TypeScript → `frontend-expert`
- Go → `go-expert`
- Java → `java-expert`
- Unknown → `general-purpose`

**Process in batches of 50 files. For each batch:**

```
Analyze source files batch ${BATCH_NUM} of ${TOTAL_BATCHES}.

1. Read /tmp/claude/analyze-project/files_to_analyze.txt (lines ${START} to ${END})
2. For each file, extract structured data:

   a. Imports: All import statements (internal and external modules)
   b. Exports: All exported symbols (functions, classes, constants)
   c. Classes:
      - Name
      - Methods (name, parameters, return type, docstring)
      - Decorators/annotations
      - Inheritance (base classes)
      - Docstring/description
   d. Functions:
      - Name
      - Parameters with types
      - Return type
      - Docstring/description
      - Decorators/annotations
   e. Dependencies: External libraries used
   f. Purpose: Brief description of what the file does

3. Write analysis results to /tmp/claude/analyze-project/analysis_batch_${BATCH_NUM}.json

4. Format as JSON array with one object per file:
   [
     {
       "file": "relative/path/to/file.py",
       "language": "Python",
       "purpose": "Brief description",
       "imports": {
         "internal": ["module1", "module2"],
         "external": ["requests", "fastapi"]
       },
       "exports": ["function_name", "ClassName"],
       "classes": [
         {
           "name": "ClassName",
           "docstring": "Class description",
           "decorators": ["@dataclass"],
           "inherits": ["BaseClass"],
           "methods": [...]
         }
       ],
       "functions": [
         {
           "name": "function_name",
           "parameters": ["param1: str", "param2: int = 0"],
           "return_type": "str",
           "docstring": "Function description",
           "decorators": ["@app.get('/endpoint')"],
           "is_async": false
         }
       ],
       "dependencies": ["requests", "fastapi"]
     }
   ]

5. Return summary:
   [Batch ${BATCH_NUM}/${TOTAL_BATCHES}] Analyzed: <count> files
   Classes: <count>
   Functions: <count>
```

**Display batch progress after each delegation.**

**Display final summary:**
```
✅ Code analysis complete: <total_files> files analyzed
```

---

## Phase 6: Relationship Mapping

Display: `🔍 Phase 6: Mapping relationships...`

**DELEGATE to general-purpose agent:**

```
Build relationship maps from code analysis results.

1. Read all analysis batch files from /tmp/claude/analyze-project/analysis_batch_*.json
2. Merge into single array of all file analysis data

3. Extract relationships:

   a. Import dependencies:
      - For each internal import: {source: file, target: imported_module, type: "imports"}
      - For each external dependency: {source: file, target: external_lib, type: "depends_on"}

   b. Class inheritance:
      - For each class with base classes: {source: class_name, target: base_class, type: "inherits_from"}

   c. API endpoints (scan function decorators):
      - FastAPI: @app.get('/path'), @app.post('/path'), etc.
      - Flask: @app.route('/path')
      - Express: app.get('/path', ...)
      - For each endpoint: {source: path, target: function_name, type: "api_endpoint", method: "GET/POST/etc"}

   d. Test mappings:
      - Identify test files (contains test_, .test., or .spec.)
      - Infer source file from test file name
      - Create: {source: test_file, target: source_file, type: "tests"}

4. Write all relationships to /tmp/claude/analyze-project/relationships.json

5. Calculate statistics and return summary:
   ✅ Relationship mapping complete:
      Import relationships: <count> files
      Class hierarchies: <count> classes
      API endpoints: <count> endpoints
      Test mappings: <count> test files
```

**Display agent response.**

---

## Phase 7: Store in Memory

Display: `🔍 Phase 7: Storing analysis in graphiti-memory...`

### 7.1: Store Project Metadata

**DELEGATE to graphiti-memory-manager:**

```
Store project metadata episode.

1. Read project_info.json from ${PWD}/.analyze-project/
2. Read analysis statistics from all analysis_batch_*.json files
3. Count total classes, functions, files, API endpoints

4. Prepare JSON:
   {
     "type": "project",
     "name": "${PROJECT_NAME}",
     "path": "${WORKING_DIR}",
     "language": "${LANGUAGE}",
     "framework": "${FRAMEWORK}",
     "projectType": "${PROJECT_TYPE}",
     "total_files": <count>,
     "total_classes": <count>,
     "total_functions": <count>,
     "total_api_endpoints": <count>,
     "analyzed_at": "${ISO_TIMESTAMP}"
   }

5. Call add_memory with:
   - name: "${PROJECT_NAME}"
   - episode_body: <JSON string (properly escaped)>
   - group_id: "${GROUP_ID}"
   - source: "json"
   - source_description: "Project metadata"

6. Return:
   ✅ Stored project metadata
```

**Display agent response.**

### 7.2: Store File Episodes

**DELEGATE to graphiti-memory-manager:**

```
Store file episodes for all analyzed files.

1. Read all analysis_batch_*.json files from /tmp/claude/analyze-project/
2. Read current_hashes.json from ${PWD}/.analyze-project/ for file hashes
3. For each analyzed file, prepare episode JSON:
   {
     "type": "file",
     "path": "${FILE_PATH}",
     "language": "${LANGUAGE}",
     "purpose": "${PURPOSE}",
     "imports": {...},
     "exports": [...],
     "classes": ["ClassName1", "ClassName2"],
     "functions": ["function1", "function2"],
     "dependencies": [...],
     "file_hash": "${SHA256_HASH}"
   }

4. Process in batches of 20 files
5. For each batch, call add_memory:
   - name: "file:${FILE_PATH}"
   - episode_body: <JSON string (properly escaped)>
   - group_id: "${GROUP_ID}"
   - source: "json"
   - source_description: "Source file: ${FILE_PATH}"

6. Track progress and return final summary:
   ✅ Stored <count> file episodes
```

**Display agent response.**

### 7.3: Store Class Episodes

**DELEGATE to graphiti-memory-manager:**

```
Store class episodes for all classes found in analysis.

1. Read all analysis_batch_*.json files from /tmp/claude/analyze-project/
2. Extract all classes from all files
3. For each class, prepare episode JSON:
   {
     "type": "class",
     "name": "${CLASS_NAME}",
     "file": "${FILE_PATH}",
     "docstring": "${DOCSTRING}",
     "methods": [...],
     "inherits": [...],
     "decorators": [...],
     "dependencies": [...]
   }

4. Process in batches of 30 classes
5. For each batch, call add_memory:
   - name: "class:${CLASS_NAME}"
   - episode_body: <JSON string (properly escaped)>
   - group_id: "${GROUP_ID}"
   - source: "json"
   - source_description: "Class definition: ${CLASS_NAME}"

6. Return final summary:
   ✅ Stored <count> class episodes
```

**Display agent response.**

### 7.4: Store Relationship Episodes

**DELEGATE to graphiti-memory-manager:**

```
Store relationship episodes from the relationship mapping.

1. Read relationships.json from /tmp/claude/analyze-project/
2. For each relationship, prepare episode JSON:
   {
     "type": "relationship",
     "source": "${SOURCE}",
     "target": "${TARGET}",
     "relationship_type": "${TYPE}",
     "context": "${CONTEXT}"
   }

3. Process in batches of 50 relationships
4. For each batch, call add_memory:
   - name: "relationship:${SOURCE}→${TARGET}"
   - episode_body: <JSON string (properly escaped)>
   - group_id: "${GROUP_ID}"
   - source: "json"
   - source_description: "${TYPE}: ${SOURCE} → ${TARGET}"

5. Return final summary:
   ✅ Stored <count> relationship episodes
```

**Display agent response.**

### 7.5: Store File Hash Metadata

**DELEGATE to graphiti-memory-manager:**

```
Store file hash metadata for future incremental updates.

1. Read current_hashes.json from ${PWD}/.analyze-project/
2. Read project_info.json from ${PWD}/.analyze-project/ for metadata
3. Prepare metadata JSON:
   {
     "type": "metadata",
     "purpose": "file_hashes",
     "files": {
       "path/to/file1.py": "sha256hash1",
       "path/to/file2.py": "sha256hash2",
       ...
     },
     "last_analyzed": "${ISO_TIMESTAMP}",
     "total_files": <count>
   }

4. Call add_memory with:
   - name: "project-file-hashes"
   - episode_body: <JSON string (properly escaped)>
   - group_id: "${GROUP_ID}"
   - source: "json"
   - source_description: "File hash metadata for incremental updates"

5. Copy ${PWD}/.analyze-project/current_hashes.json to ${PWD}/.analyze-project/previous_hashes.json
   for next incremental run

6. Return:
   ✅ Stored file hash metadata
```

**Display agent response.**

---

## Phase 8: Verification & Summary

Display: `🔍 Phase 8: Verifying storage and generating summary...`

**DELEGATE to graphiti-memory-manager:**

```
Verify storage and provide comprehensive summary.

1. Read project_info.json from ${PWD}/.analyze-project/
2. Extract GROUP_ID and PROJECT_NAME

3. Verify data was stored by calling search_nodes multiple times:

   a. Verify project metadata:
      - query: "project ${PROJECT_NAME} metadata"
      - group_ids: ["${GROUP_ID}"]
      - Report: ✅ Project metadata found OR ❌ Not found

   b. Verify files:
      - query: "source file"
      - group_ids: ["${GROUP_ID}"]
      - max_nodes: 10
      - Report: ✅ File episodes (<count> found)

   c. Verify classes:
      - query: "class definition"
      - group_ids: ["${GROUP_ID}"]
      - max_nodes: 10
      - Report: ✅ Class episodes (<count> found)

   d. Verify relationships:
      - query: "relationship imports depends"
      - group_ids: ["${GROUP_ID}"]
      - max_nodes: 10
      - Report: ✅ Relationships (<count> found)

4. Read relationships.json to extract API endpoints (if any)

5. Generate final summary with all statistics and example queries

6. Return formatted summary:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Analysis Complete - Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Project: ${PROJECT_NAME}
Group ID: ${GROUP_ID}

📈 Statistics:
   Total files analyzed: <count>
   Classes found: <count>
   Functions found: <count>
   Relationships mapped: <count>
   API endpoints: <count>

🔍 Example queries to explore the data:

  Search for authentication-related code:
  Ask: "Search graphiti-memory for authentication login user in project ${PROJECT_NAME}"

  Find API endpoints:
  Ask: "Find all API endpoints in project ${PROJECT_NAME}"

  Explore class relationships:
  Ask: "Show class inheritance in project ${PROJECT_NAME}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Analysis stored successfully!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If API endpoints exist, include top 5 in response:

🌐 API Endpoints:
   GET    /api/users
   POST   /api/users
   GET    /api/users/{id}
   ... and <remaining_count> more
```

**Display agent response as final output.**

**Display cleanup notice:**

```
💡 Storage locations:
   Persistent: ${PWD}/.analyze-project/ (hashes, project info)
   Temporary:  /tmp/claude/analyze-project/ (batch files, can be deleted)

   Add .analyze-project/ to your .gitignore if not already present.
```

---

## Error Handling

**If any agent returns an error:**
1. Display the error message to user
2. Log to /tmp/claude/analyze-project/errors.log
3. Continue with remaining steps when possible
4. Display partial results if some phases completed successfully

**This ensures partial progress is saved even if some operations fail.**

---

## Architecture Summary

**This command uses 100% delegation:**
- Prerequisites: graphiti-memory-manager checks server
- Phase 1: bash-expert initializes project
- Phase 2: graphiti-memory-manager checks previous analysis
- Phase 3: bash-expert discovers files
- Phase 4: bash-expert calculates changes
- Phase 5: language-expert analyzes code (batched)
- Phase 6: general-purpose maps relationships
- Phase 7: graphiti-memory-manager stores all data (batched)
- Phase 8: graphiti-memory-manager verifies and summarizes

**The orchestrator only:**
- Displays phase transitions
- Delegates to agents using Task tool
- Displays agent responses
- NO file operations, NO bash commands, NO MCP calls, NO logic
