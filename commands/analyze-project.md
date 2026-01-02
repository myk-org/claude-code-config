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

- `/analyze-project` - Analyze current project (smart: full if no previous data, incremental otherwise)
- `/analyze-project --full` - Force full re-analysis

---

## Storage Locations

**Persistent files** (survive reboots, project-specific):
- Location: `${PWD}/.analyze-project/`
- Contains: `previous_hashes.json`, `project_info.json`
- Should be added to `.gitignore`

**Temporary files** (session-only, discarded):
- Location: `/tmp/claude/analyze-project/${PROJECT_HASH}/` (where PROJECT_HASH is first 8 chars of sha256 of working directory)
- Contains: batch analysis files, intermediate data
- Automatically cleaned up by system
- Each project gets its own temp directory to prevent conflicts when analyzing multiple projects simultaneously

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
Run the init-analysis.sh script to initialize project analysis:

~/.claude/commands/scripts/analyze-project/init-analysis.sh ${ARGUMENTS}

The script will:
1. Parse --full and --name flags from arguments
2. Detect project type, language, and framework
3. Create .analyze-project/ and /tmp/claude/analyze-project/ directories
4. Write project_info.json

Display the script output directly to the user.
```

**Display agent response.**

---

## Phase 2: Check Previous Analysis

Display: `🔍 Phase 2: Checking for previous analysis...`

**DELEGATE to graphiti-memory-manager:**

```
Check for previous analysis of the project.

1. Read project info from ${PWD}/.analyze-project/project_info.json
2. Extract GROUP_ID, PROJECT_NAME, IS_FULL_ANALYSIS, and FULL_ANALYSIS_REASON
3. Call search_nodes with:
   - query: "project metadata ${PROJECT_NAME}"
   - group_ids: ["${GROUP_ID}"]
   - max_nodes: 5

4. If nodes are found, respond with:
   📋 FOUND: Previous analysis exists (X nodes found)

5. If no nodes are found, respond with:
   📋 NOT_FOUND: No previous analysis exists

6. Read analysis mode from project_info.json (already set by init-analysis.sh):
   - Read is_full_analysis and full_analysis_reason fields
   - If full_analysis_reason == "user_flag":
     → Display "Will perform full re-analysis (--full flag)"
   - If full_analysis_reason == "no_hashes":
     → Display "Will perform full analysis (no previous hashes)"
   - If full_analysis_reason == "incremental":
     → Display "Will perform incremental update"

Note: The analysis mode is determined by init-analysis.sh based on --full flag
and presence of previous_hashes.json. Phase 2 just reports it.
```

**Display agent response.**

---

## Phase 3: File Discovery

Display: `🔍 Phase 3: Discovering source files...`

**DELEGATE to bash-expert:**

```
Discover source files using the find-source-files.sh script:

1. Read project_info.json from ${PWD}/.analyze-project/ to get project_type and temp_dir
2. Run the script (it will automatically use the project-specific temp directory):
   ~/.claude/commands/scripts/analyze-project/find-source-files.sh "$PWD"

3. The script outputs the file count to stdout
4. Return summary:
   ✅ Found: <count> source files
   📄 File list: ${TEMP_DIR}/all_files.txt
```

**Display agent response.**

---

## Phase 4: Calculate Changes (Incremental Mode)

Display: `🔍 Phase 4: Calculating changes...`

**DELEGATE to bash-expert:**

```
Calculate file changes using the helper scripts:

1. Read project_info.json from ${PWD}/.analyze-project/ to get IS_FULL_ANALYSIS flag and TEMP_DIR

2. If IS_FULL_ANALYSIS is true:
   - Copy all_files.txt to files_to_analyze.txt:
     cp "${TEMP_DIR}/all_files.txt" "${TEMP_DIR}/files_to_analyze.txt"
   - Return: "Full analysis mode: all files will be analyzed"
   - SKIP remaining steps

3. Calculate hashes for all files (script will automatically use project-specific temp dir):
   ~/.claude/commands/scripts/analyze-project/calculate-hashes.sh

4. Compare with previous hashes (script will automatically use project-specific temp dir):
   ~/.claude/commands/scripts/analyze-project/compare-hashes.sh

5. The compare script outputs JSON summary. Parse and display:
   📊 Change Summary:
      New files: <new_files>
      Changed files: <changed_files>
      Deleted files: <deleted_files>
      Unchanged files: <unchanged_files>
      Files to analyze: <files_to_analyze>

6. If files_to_analyze is 0, add:
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

**Process in batches of 8 files. For each batch:**

```
Analyze source files batch ${BATCH_NUM} of ${TOTAL_BATCHES}.

**IMPORTANT: All temp files MUST go to ${TEMP_DIR}/**
If you create any helper scripts or intermediate files, use ${TEMP_DIR}/ (from project_info.json), NOT /tmp/claude/.

1. Read ${TEMP_DIR}/files_to_analyze.txt (lines ${START} to ${END})
   (Get TEMP_DIR from project_info.json)
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

3. Write analysis results to ${TEMP_DIR}/analysis_batch_${BATCH_NUM}.json
   (Get TEMP_DIR from project_info.json)

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
**IMPORTANT: All temp files MUST go to ${TEMP_DIR}/**
If you create any helper scripts or intermediate files, use ${TEMP_DIR}/ (from project_info.json), NOT /tmp/claude/.

Build relationship maps from code analysis results.

1. First, validate all analysis batches:
   uv run ~/.claude/commands/scripts/analyze-project/validate-analysis.py

   If validation fails (exit code 2), STOP and report the errors to the user.

2. Merge all analysis batches:
   uv run ~/.claude/commands/scripts/analyze-project/merge-analysis.py

3. Read the merged analysis from ${TEMP_DIR}/all_analysis.json

4. Extract relationships:

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

5. Write all relationships to ${TEMP_DIR}/relationships.json

6. Calculate statistics and return summary:
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
2. Read statistics from ${TEMP_DIR}/analysis_stats.json (already calculated by merge-analysis.py)
   - The stats file contains: total_files, total_classes, total_functions, by_language, api_endpoints

3. Prepare JSON:
   {
     "type": "project",
     "name": "${PROJECT_NAME}",
     "path": "${WORKING_DIR}",
     "language": "${LANGUAGE}",
     "framework": "${FRAMEWORK}",
     "projectType": "${PROJECT_TYPE}",
     "total_files": <from stats>,
     "total_classes": <from stats>,
     "total_functions": <from stats>,
     "total_api_endpoints": <from stats.api_endpoints count>,
     "analyzed_at": "${ISO_TIMESTAMP}"
   }

4. Call add_memory with:
   - name: "${PROJECT_NAME}"
   - episode_body: <JSON string (properly escaped)>
   - group_id: "${GROUP_ID}"
   - source: "json"
   - source_description: "Project metadata"

5. Return:
   ✅ Stored project metadata
```

**Display agent response.**

### 7.2: Store File Episodes

**DELEGATE to bash-expert:**

```
Run the prepare-episodes script to create batches:

uv run ~/.claude/commands/scripts/analyze-project/prepare-episodes.py files

Display the script output directly to the user.
```

**Display agent response.**

**For each batch file listed in the manifest, DELEGATE to graphiti-memory-manager:**

```
Store file episodes from batch ${BATCH_NUM} of ${TOTAL_BATCHES}.

1. Read ${TEMP_DIR}/episodes_files_batch_${BATCH_NUM}.json
2. For each episode in the batch, call add_memory with:
   - name: episode.name
   - episode_body: episode.episode_body
   - group_id: episode.group_id
   - source: episode.source
   - source_description: episode.source_description

3. Return: ✅ Batch ${BATCH_NUM}: Stored X episodes
```

**IMPORTANT: Spawn batch agents in parallel where possible to speed up processing.**

**After all batches complete, display summary:**
```
✅ Stored <total> file episodes across <batch_count> batches
```

### 7.3: Store Class Episodes

**DELEGATE to bash-expert:**

```
Run the prepare-episodes script to create batches:

uv run ~/.claude/commands/scripts/analyze-project/prepare-episodes.py classes

Display the script output directly to the user.
```

**Display agent response.**

**For each batch file listed in the manifest, DELEGATE to graphiti-memory-manager:**

```
Store class episodes from batch ${BATCH_NUM} of ${TOTAL_BATCHES}.

1. Read ${TEMP_DIR}/episodes_classes_batch_${BATCH_NUM}.json
2. For each episode in the batch, call add_memory with:
   - name: episode.name
   - episode_body: episode.episode_body
   - group_id: episode.group_id
   - source: episode.source
   - source_description: episode.source_description

3. Return: ✅ Batch ${BATCH_NUM}: Stored X episodes
```

**IMPORTANT: Spawn batch agents in parallel where possible to speed up processing.**

**After all batches complete, display summary:**
```
✅ Stored <total> class episodes across <batch_count> batches
```

### 7.4: Store Relationship Episodes

**DELEGATE to bash-expert:**

```
Run the prepare-episodes script to create batches:

uv run ~/.claude/commands/scripts/analyze-project/prepare-episodes.py relationships

Display the script output directly to the user.
```

**Display agent response.**

**For each batch file listed in the manifest, DELEGATE to graphiti-memory-manager:**

```
Store relationship episodes from batch ${BATCH_NUM} of ${TOTAL_BATCHES}.

1. Read ${TEMP_DIR}/episodes_relationships_batch_${BATCH_NUM}.json
2. For each episode in the batch, call add_memory with:
   - name: episode.name
   - episode_body: episode.episode_body
   - group_id: episode.group_id
   - source: episode.source
   - source_description: episode.source_description

3. Return: ✅ Batch ${BATCH_NUM}: Stored X episodes
```

**IMPORTANT: Spawn batch agents in parallel where possible to speed up processing.**

**After all batches complete, display summary:**
```
✅ Stored <total> relationship episodes across <batch_count> batches
```

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

4. Read TEMP_DIR from project_info.json
5. Read ${TEMP_DIR}/relationships.json to extract API endpoints (if any)

6. Generate final summary with all statistics and example queries

7. Return formatted summary:

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

### 8.2: Cleanup Temp Files

**DELEGATE to bash-expert:**

```
Run the cleanup script:
~/.claude/commands/scripts/analyze-project/cleanup.sh

Display the script output.
```

**Display agent response.**

**Display cleanup notice:**

```
💡 Storage locations:
   Persistent: ${PWD}/.analyze-project/ (hashes, project info)
   Temporary:  Cleaned up automatically after analysis

   Add .analyze-project/ to your .gitignore if not already present.
```

---

## Error Handling

**Script Exit Codes:**
- `0` = Success
- `1` = Usage error (wrong arguments) - display help, do NOT create issue
- `2` = Script logic error (bug) - ask user about creating issue

**If a script exits with code 2 (script bug):**

1. Display the error to the user:
```
❌ Script error detected in <script_name>

Error output:
<error_output>
```

2. Analyze the error and suggest a fix if the pattern is recognizable

3. Ask the user if they want to create a GitHub issue:
```
Would you like me to create a GitHub issue to track this bug?
- Yes, create an issue
- No, I'll handle it manually
```

4. If user agrees, create the issue with comprehensive details:

```bash
gh issue create \
  --repo myk-org/claude-code-config \
  --title "🐛 analyze-project: <script_name> failed at line <line_number>" \
  --body "$(cat <<'EOF'
## Script Failure

**Script:** `<script_name>`
**Exit Code:** 2
**Failed at:** Line <line_number>
**Working Directory:** `${PWD}`

## Error Output
```
<full_error_output>
```

## Context
- Project: `<project_name>`
- Phase: <phase_number>
- Project Type: `<project_type>`

## Suggested Fix
<if recognizable error pattern, suggest what might fix it>
<otherwise: "Requires investigation">

## Steps to Reproduce
1. Navigate to a similar project directory
2. Run `/analyze-project`
3. Observe the error at phase <phase_number>

## Diagnostic Info
<any additional context that would help debug>

---
*Auto-generated by /analyze-project command*
EOF
)"
```

5. Display the issue URL to the user

**If exit code is 1 (usage error):**
- Display the error message with correct usage
- Do NOT offer to create issue (it's user error, not a bug)
- Continue if possible, or provide instructions

**If any agent returns an error:**
1. Display the error message to user
2. Attempt to continue with remaining phases if possible
3. Display partial results if some phases completed

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
