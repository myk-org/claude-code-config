#!/usr/bin/env bash
# detect-project.sh - Detect project type, language, and framework
# Usage: detect-project.sh [working_dir]
# Output: Writes to ${WORKING_DIR}/.analyze-project/project_info.json
# Exit codes: 0=success, 1=usage error, 2=script error

set -euo pipefail
trap 'echo "ERROR: Script failed at line $LINENO" >&2; exit 2' ERR

WORKING_DIR="${1:-$PWD}"
cd "$WORKING_DIR"

# Initialize arrays
declare -a PROJECT_TYPES=()
declare -a LANGUAGES=()
declare -a FRAMEWORKS=()

# Detect Python
if [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]] || [[ -f "requirements.txt" ]]; then
    PROJECT_TYPES+=("python")
    LANGUAGES+=("Python")

    # Detect Python framework
    if [[ -f "pyproject.toml" ]]; then
        if grep -qi "fastapi" pyproject.toml 2>/dev/null; then
            FRAMEWORKS+=("FastAPI")
        elif grep -qi "flask" pyproject.toml 2>/dev/null; then
            FRAMEWORKS+=("Flask")
        elif grep -qi "django" pyproject.toml 2>/dev/null; then
            FRAMEWORKS+=("Django")
        fi
    elif [[ -f "requirements.txt" ]]; then
        if grep -qi "fastapi" requirements.txt 2>/dev/null; then
            FRAMEWORKS+=("FastAPI")
        elif grep -qi "flask" requirements.txt 2>/dev/null; then
            FRAMEWORKS+=("Flask")
        elif grep -qi "django" requirements.txt 2>/dev/null; then
            FRAMEWORKS+=("Django")
        fi
    fi
fi

# Detect Node.js/TypeScript
if [[ -f "package.json" ]]; then
    if [[ -f "tsconfig.json" ]]; then
        PROJECT_TYPES+=("typescript")
        LANGUAGES+=("TypeScript")
    else
        PROJECT_TYPES+=("nodejs")
        LANGUAGES+=("JavaScript")
    fi

    # Detect Node.js framework
    if grep -q '"react"' package.json 2>/dev/null || grep -q '"next"' package.json 2>/dev/null; then
        FRAMEWORKS+=("React")
    elif grep -q '"vue"' package.json 2>/dev/null || grep -q '"nuxt"' package.json 2>/dev/null; then
        FRAMEWORKS+=("Vue")
    elif grep -q '"@angular/core"' package.json 2>/dev/null; then
        FRAMEWORKS+=("Angular")
    elif grep -q '"express"' package.json 2>/dev/null; then
        FRAMEWORKS+=("Express")
    fi
fi

# Detect Go
if [[ -f "go.mod" ]]; then
    PROJECT_TYPES+=("go")
    LANGUAGES+=("Go")
fi

# Detect Java
if [[ -f "pom.xml" ]]; then
    PROJECT_TYPES+=("java")
    LANGUAGES+=("Java")
    FRAMEWORKS+=("Maven")
elif [[ -f "build.gradle" ]] || [[ -f "build.gradle.kts" ]]; then
    PROJECT_TYPES+=("java")
    LANGUAGES+=("Java")
    FRAMEWORKS+=("Gradle")
fi

# Detect Rust
if [[ -f "Cargo.toml" ]]; then
    PROJECT_TYPES+=("rust")
    LANGUAGES+=("Rust")
fi

# Scan common subdirectories for additional project types (monorepo support)
SUBDIRS=("frontend" "backend" "client" "server" "web" "app" "packages" "apps" "src")

for subdir in "${SUBDIRS[@]}"; do
    [[ ! -d "$subdir" ]] && continue

    # Check for Python in subdirectory
    if [[ -f "$subdir/pyproject.toml" ]] || [[ -f "$subdir/setup.py" ]] || [[ -f "$subdir/requirements.txt" ]]; then
        if [[ ! " ${PROJECT_TYPES[*]} " =~ " python " ]]; then
            PROJECT_TYPES+=("python")
            LANGUAGES+=("Python")
            # Check framework
            if [[ -f "$subdir/pyproject.toml" ]] && grep -qi "fastapi" "$subdir/pyproject.toml" 2>/dev/null; then
                [[ ! " ${FRAMEWORKS[*]} " =~ " FastAPI " ]] && FRAMEWORKS+=("FastAPI")
            elif [[ -f "$subdir/pyproject.toml" ]] && grep -qi "flask" "$subdir/pyproject.toml" 2>/dev/null; then
                [[ ! " ${FRAMEWORKS[*]} " =~ " Flask " ]] && FRAMEWORKS+=("Flask")
            elif [[ -f "$subdir/pyproject.toml" ]] && grep -qi "django" "$subdir/pyproject.toml" 2>/dev/null; then
                [[ ! " ${FRAMEWORKS[*]} " =~ " Django " ]] && FRAMEWORKS+=("Django")
            fi
            if [[ -f "$subdir/requirements.txt" ]]; then
                if grep -qi "fastapi" "$subdir/requirements.txt" 2>/dev/null && [[ ! " ${FRAMEWORKS[*]} " =~ " FastAPI " ]]; then
                    FRAMEWORKS+=("FastAPI")
                elif grep -qi "flask" "$subdir/requirements.txt" 2>/dev/null && [[ ! " ${FRAMEWORKS[*]} " =~ " Flask " ]]; then
                    FRAMEWORKS+=("Flask")
                elif grep -qi "django" "$subdir/requirements.txt" 2>/dev/null && [[ ! " ${FRAMEWORKS[*]} " =~ " Django " ]]; then
                    FRAMEWORKS+=("Django")
                fi
            fi
        fi
    fi

    # Check for Node.js/TypeScript in subdirectory
    if [[ -f "$subdir/package.json" ]]; then
        if [[ -f "$subdir/tsconfig.json" ]]; then
            if [[ ! " ${PROJECT_TYPES[*]} " =~ " typescript " ]]; then
                PROJECT_TYPES+=("typescript")
                LANGUAGES+=("TypeScript")
            fi
        else
            if [[ ! " ${PROJECT_TYPES[*]} " =~ " nodejs " ]]; then
                PROJECT_TYPES+=("nodejs")
                LANGUAGES+=("JavaScript")
            fi
        fi
        # Check framework
        if grep -q '"react"' "$subdir/package.json" 2>/dev/null || grep -q '"next"' "$subdir/package.json" 2>/dev/null; then
            [[ ! " ${FRAMEWORKS[*]} " =~ " React " ]] && FRAMEWORKS+=("React")
        elif grep -q '"vue"' "$subdir/package.json" 2>/dev/null || grep -q '"nuxt"' "$subdir/package.json" 2>/dev/null; then
            [[ ! " ${FRAMEWORKS[*]} " =~ " Vue " ]] && FRAMEWORKS+=("Vue")
        elif grep -q '"@angular/core"' "$subdir/package.json" 2>/dev/null; then
            [[ ! " ${FRAMEWORKS[*]} " =~ " Angular " ]] && FRAMEWORKS+=("Angular")
        elif grep -q '"express"' "$subdir/package.json" 2>/dev/null; then
            [[ ! " ${FRAMEWORKS[*]} " =~ " Express " ]] && FRAMEWORKS+=("Express")
        fi
    fi

    # Check for Go in subdirectory
    if [[ -f "$subdir/go.mod" ]]; then
        if [[ ! " ${PROJECT_TYPES[*]} " =~ " go " ]]; then
            PROJECT_TYPES+=("go")
            LANGUAGES+=("Go")
        fi
    fi

    # Check for Java in subdirectory
    if [[ -f "$subdir/pom.xml" ]]; then
        if [[ ! " ${PROJECT_TYPES[*]} " =~ " java " ]]; then
            PROJECT_TYPES+=("java")
            LANGUAGES+=("Java")
            [[ ! " ${FRAMEWORKS[*]} " =~ " Maven " ]] && FRAMEWORKS+=("Maven")
        fi
    elif [[ -f "$subdir/build.gradle" ]] || [[ -f "$subdir/build.gradle.kts" ]]; then
        if [[ ! " ${PROJECT_TYPES[*]} " =~ " java " ]]; then
            PROJECT_TYPES+=("java")
            LANGUAGES+=("Java")
            [[ ! " ${FRAMEWORKS[*]} " =~ " Gradle " ]] && FRAMEWORKS+=("Gradle")
        fi
    fi

    # Check for Rust in subdirectory
    if [[ -f "$subdir/Cargo.toml" ]]; then
        if [[ ! " ${PROJECT_TYPES[*]} " =~ " rust " ]]; then
            PROJECT_TYPES+=("rust")
            LANGUAGES+=("Rust")
        fi
    fi
done

# Handle unknown project
if [[ ${#PROJECT_TYPES[@]} -eq 0 ]]; then
    PROJECT_TYPES+=("unknown")
    LANGUAGES+=("Unknown")
fi

# Determine if mixed project
IS_MIXED=false
if [[ ${#PROJECT_TYPES[@]} -gt 1 ]]; then
    IS_MIXED=true
fi

# Convert arrays to JSON format
join_array() {
    local arr=("$@")
    local result=""
    for item in "${arr[@]}"; do
        [[ -n "$result" ]] && result+=", "
        result+="\"$item\""
    done
    echo "[$result]"
}

# Create output directory
OUTPUT_DIR="$WORKING_DIR/.analyze-project"
mkdir -p "$OUTPUT_DIR"

# For backward compatibility, also provide primary type
PRIMARY_TYPE="${PROJECT_TYPES[0]}"
PRIMARY_LANGUAGE="${LANGUAGES[0]}"
PRIMARY_FRAMEWORK="${FRAMEWORKS[0]:-none}"

# Build JSON content
JSON_CONTENT=$(cat <<EOF
{
  "project_type": "$PRIMARY_TYPE",
  "language": "$PRIMARY_LANGUAGE",
  "framework": "$PRIMARY_FRAMEWORK",
  "is_mixed": $IS_MIXED,
  "all_types": $(join_array "${PROJECT_TYPES[@]}"),
  "all_languages": $(join_array "${LANGUAGES[@]}"),
  "all_frameworks": $(join_array "${FRAMEWORKS[@]:-}"),
  "working_dir": "$WORKING_DIR"
}
EOF
)

# Write to file
echo "$JSON_CONTENT" > "$OUTPUT_DIR/project_info.json"

# Output summary to stdout
echo "🔍 Project Detection Complete"
echo "   Type: $PRIMARY_TYPE ($PRIMARY_LANGUAGE)"
echo "   Framework: $PRIMARY_FRAMEWORK"
echo "   Mixed project: $IS_MIXED"
if [[ "$IS_MIXED" == "true" ]]; then
    echo "   All types: ${PROJECT_TYPES[*]}"
fi
echo "   Output: $OUTPUT_DIR/project_info.json"

exit 0
