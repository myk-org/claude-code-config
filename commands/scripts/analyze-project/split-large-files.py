#!/usr/bin/env python3
"""
Split large source files by top-level definitions.

For files too large to analyze in one pass, splits them into smaller chunks
where each chunk contains one or more top-level definitions (classes, functions).
"""

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def estimate_tokens(content: str) -> int:
    """Estimate tokens from content length. Rule: ~4 chars/bytes per token."""
    return len(content) // 4


@dataclass
class Definition:
    """A top-level definition in source code."""

    name: str
    start_line: int
    end_line: int
    content: str

    @property
    def tokens(self) -> int:
        """Estimate token count for this definition."""
        return estimate_tokens(self.content)


@dataclass
class ChunkInfo:
    """Information about a single chunk."""

    chunk_file: str
    definitions: list[str]
    tokens: int
    oversized: bool = False


@dataclass
class ChunkManifest:
    """Manifest of all created chunks."""

    original_file: str
    language: str
    total_tokens: int
    chunks: list[ChunkInfo]


def detect_language(file_path: Path) -> str:
    """Detect language from file extension."""
    ext = file_path.suffix.lower()

    lang_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".go": "Go",
        ".java": "Java",
        ".kt": "Kotlin",
        ".rb": "Ruby",
        ".php": "PHP",
        ".c": "C",
        ".cpp": "C++",
        ".cc": "C++",
        ".h": "C/C++ Header",
        ".hpp": "C++ Header",
        ".cs": "C#",
        ".rs": "Rust",
        ".swift": "Swift",
        ".m": "Objective-C",
    }

    return lang_map.get(ext, "Unknown")


def extract_imports_python(content: str) -> str:
    """Extract all import statements from Python source."""
    try:
        tree = ast.parse(content)
        import_lines = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Get line number and extract from source
                start_line = node.lineno - 1
                end_line = node.end_lineno if node.end_lineno else start_line + 1
                lines = content.split("\n")
                import_lines.extend(lines[start_line:end_line])

        return "\n".join(import_lines) if import_lines else ""

    except SyntaxError:
        # If parsing fails, try simple regex
        import_pattern = re.compile(r"^(import\s+.+|from\s+.+import\s+.+)", re.MULTILINE)
        imports = import_pattern.findall(content)
        return "\n".join(imports)


def parse_python(content: str) -> tuple[list[Definition], str]:
    """
    Parse Python source and extract top-level definitions.

    Returns:
        tuple: (list of definitions, imports string)
    """
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(
            f"⚠️  Warning: Python parsing failed: {e}, falling back to line split",
            file=sys.stderr,
        )
        return [], ""

    definitions: list[Definition] = []
    lines = content.split("\n")
    imports = extract_imports_python(content)

    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            start_line = node.lineno - 1
            end_line = node.end_lineno if node.end_lineno else len(lines)

            # Extract content including decorators
            if hasattr(node, "decorator_list") and node.decorator_list:
                first_decorator = node.decorator_list[0]
                start_line = first_decorator.lineno - 1

            def_content = "\n".join(lines[start_line:end_line])

            definitions.append(
                Definition(
                    name=name,
                    start_line=start_line,
                    end_line=end_line,
                    content=def_content,
                )
            )

    return definitions, imports


def parse_javascript_typescript(content: str) -> tuple[list[Definition], str]:
    """
    Parse JavaScript/TypeScript using regex patterns.

    Returns:
        tuple: (list of definitions, imports string)
    """
    lines = content.split("\n")
    definitions: list[Definition] = []

    # Extract imports (both ES6 and CommonJS)
    import_pattern = re.compile(
        r"^(import\s+.+from\s+.+|const\s+.+\s*=\s*require\(.+\)|export\s+.+from\s+.+)",
        re.MULTILINE,
    )
    imports = "\n".join(import_pattern.findall(content))

    # Patterns for top-level definitions
    patterns = [
        # export function/class
        (r"^export\s+(async\s+)?function\s+(\w+)", "function"),
        (r"^export\s+class\s+(\w+)", "class"),
        # function/class declarations
        (r"^(async\s+)?function\s+(\w+)", "function"),
        (r"^class\s+(\w+)", "class"),
        # const/let/var with function/class
        (
            r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?.*\)?\s*=>",
            "arrow_function",
        ),
        (r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*class", "class_expr"),
    ]

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        for pattern, def_type in patterns:
            match = re.match(pattern, line)
            if match:
                # Extract name from match groups
                name = match.group(2) if match.lastindex >= 2 else match.group(1)

                # Find the end of this definition (simple heuristic: next top-level def or EOF)
                start_line = i
                brace_count = 0
                in_definition = False

                j = i
                while j < len(lines):
                    current_line = lines[j]

                    # Track braces
                    brace_count += current_line.count("{") - current_line.count("}")

                    if "{" in current_line:
                        in_definition = True

                    # End when braces balance after opening
                    if in_definition and brace_count == 0 and "{" in lines[start_line:j]:
                        end_line = j + 1
                        break

                    j += 1
                else:
                    end_line = len(lines)

                def_content = "\n".join(lines[start_line:end_line])

                definitions.append(
                    Definition(
                        name=name,
                        start_line=start_line,
                        end_line=end_line,
                        content=def_content,
                    )
                )

                i = end_line - 1
                break
        i += 1

    return definitions, imports


def parse_go(content: str) -> tuple[list[Definition], str]:
    """
    Parse Go source using regex patterns.

    Returns:
        tuple: (list of definitions, imports string)
    """
    lines = content.split("\n")
    definitions: list[Definition] = []

    # Extract imports
    import_pattern = re.compile(r"^import\s+\(.*?\)", re.MULTILINE | re.DOTALL)
    import_single = re.compile(r'^import\s+".*?"', re.MULTILINE)

    imports_multi = import_pattern.findall(content)
    imports_single_list = import_single.findall(content)
    imports = "\n".join(imports_multi + imports_single_list)

    # Patterns for top-level definitions
    patterns = [
        (r"^func\s+(?:\([^)]+\)\s+)?(\w+)", "function"),  # Functions and methods
        (r"^type\s+(\w+)\s+struct", "struct"),
        (r"^type\s+(\w+)\s+interface", "interface"),
    ]

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        for pattern, def_type in patterns:
            match = re.match(pattern, line)
            if match:
                name = match.group(1)
                start_line = i

                # Find end of definition
                brace_count = 0
                in_definition = False

                j = i
                while j < len(lines):
                    current_line = lines[j]

                    brace_count += current_line.count("{") - current_line.count("}")

                    if "{" in current_line:
                        in_definition = True

                    if in_definition and brace_count == 0:
                        end_line = j + 1
                        break

                    j += 1
                else:
                    end_line = len(lines)

                def_content = "\n".join(lines[start_line:end_line])

                definitions.append(
                    Definition(
                        name=name,
                        start_line=start_line,
                        end_line=end_line,
                        content=def_content,
                    )
                )

                i = end_line - 1
                break
        i += 1

    return definitions, imports


def parse_file(file_path: Path) -> tuple[list[Definition], str, str]:
    """
    Parse source file and extract top-level definitions.

    Returns:
        tuple: (list of definitions, imports string, language)
    """
    language = detect_language(file_path)

    try:
        content = file_path.read_text()
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}", file=sys.stderr)
        sys.exit(2)

    if language == "Python":
        definitions, imports = parse_python(content)
    elif language in ("JavaScript", "TypeScript"):
        definitions, imports = parse_javascript_typescript(content)
    elif language == "Go":
        definitions, imports = parse_go(content)
    else:
        # Fallback: split by line count
        print(
            f"⚠️  Warning: No parser for {language}, falling back to line split",
            file=sys.stderr,
        )
        definitions, imports = fallback_split(content)

    return definitions, imports, language


def fallback_split(content: str, lines_per_chunk: int = 200) -> tuple[list[Definition], str]:
    """
    Fallback: split content by line count.

    Returns:
        tuple: (list of definitions, empty imports)
    """
    lines = content.split("\n")
    definitions: list[Definition] = []

    for i in range(0, len(lines), lines_per_chunk):
        chunk_lines = lines[i : i + lines_per_chunk]
        chunk_content = "\n".join(chunk_lines)

        definitions.append(
            Definition(
                name=f"lines_{i + 1}_{i + len(chunk_lines)}",
                start_line=i,
                end_line=i + len(chunk_lines),
                content=chunk_content,
            )
        )

    return definitions, ""


def create_chunks(
    definitions: list[Definition],
    imports: str,
    max_tokens: int,
) -> list[list[Definition]]:
    """
    Group definitions into chunks that fit within max_tokens.

    Each chunk should contain one or more definitions.
    If a single definition exceeds max_tokens, it becomes its own chunk.
    """
    chunks: list[list[Definition]] = []
    current_chunk: list[Definition] = []
    current_tokens = estimate_tokens(imports) if imports else 0

    for definition in definitions:
        def_tokens = definition.tokens

        # Single definition exceeds limit - give it its own chunk
        if def_tokens > max_tokens:
            # Flush current chunk if not empty
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = estimate_tokens(imports) if imports else 0

            # Add oversized definition as its own chunk
            chunks.append([definition])
            continue

        # Check if adding this definition would exceed limit
        if current_tokens + def_tokens > max_tokens and current_chunk:
            # Flush current chunk
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = estimate_tokens(imports) if imports else 0

        # Add definition to current chunk
        current_chunk.append(definition)
        current_tokens += def_tokens

    # Flush final chunk if not empty
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def write_chunks(
    chunks: list[list[Definition]],
    imports: str,
    file_path: Path,
    output_dir: Path,
    max_tokens: int,
) -> ChunkManifest:
    """
    Write chunks to output directory and create manifest.

    Returns:
        ChunkManifest with metadata about all chunks
    """
    original_name = file_path.stem
    extension = file_path.suffix
    language = detect_language(file_path)

    chunk_infos: list[ChunkInfo] = []
    total_tokens = 0

    for idx, chunk_defs in enumerate(chunks, start=1):
        chunk_filename = f"{original_name}_chunk_{idx}{extension}"
        chunk_path = output_dir / chunk_filename

        # Build chunk content
        chunk_lines = [
            f"# Chunk {idx}/{len(chunks)} of {file_path.name}",
            "",
        ]

        if imports:
            chunk_lines.extend([imports, ""])

        for definition in chunk_defs:
            chunk_lines.extend([definition.content, ""])

        chunk_content = "\n".join(chunk_lines)

        # Write chunk file
        chunk_path.write_text(chunk_content)

        # Calculate tokens
        chunk_tokens = estimate_tokens(chunk_content)
        total_tokens += chunk_tokens

        # Check if oversized (single definition exceeds max_tokens)
        oversized = len(chunk_defs) == 1 and chunk_defs[0].tokens > max_tokens

        chunk_infos.append(
            ChunkInfo(
                chunk_file=chunk_filename,
                definitions=[d.name for d in chunk_defs],
                tokens=chunk_tokens,
                oversized=oversized,
            )
        )

    return ChunkManifest(
        original_file=str(file_path),
        language=language,
        total_tokens=total_tokens,
        chunks=chunk_infos,
    )


def write_manifest(manifest: ChunkManifest, output_dir: Path, original_name: str) -> Path:
    """Write manifest JSON file."""
    manifest_path = output_dir / f"{original_name}_chunks.json"

    manifest_dict = {
        "original_file": manifest.original_file,
        "language": manifest.language,
        "total_tokens": manifest.total_tokens,
        "chunks": [
            {
                "chunk_file": c.chunk_file,
                "definitions": c.definitions,
                "tokens": c.tokens,
                "oversized": c.oversized,
            }
            for c in manifest.chunks
        ],
    }

    with open(manifest_path, "w") as f:
        json.dump(manifest_dict, f, indent=2)

    return manifest_path


def print_summary(manifest: ChunkManifest, manifest_path: Path) -> None:
    """Print chunk creation summary."""
    print(
        f"📄 Split {Path(manifest.original_file).name} ({manifest.language}) "
        f"into {len(manifest.chunks)} chunks"
    )
    print(f"📊 Total tokens: ~{manifest.total_tokens:,}")
    print("📦 Chunks:")

    for idx, chunk in enumerate(manifest.chunks, start=1):
        oversized_flag = " ⚠️  oversized" if chunk.oversized else ""
        def_count = len(chunk.definitions)
        def_plural = "definition" if def_count == 1 else "definitions"

        # Truncate definition names if too many
        def_names = chunk.definitions[:3]
        if len(chunk.definitions) > 3:
            def_names.append(f"... +{len(chunk.definitions) - 3} more")

        print(
            f"   Chunk {idx}: {def_count} {def_plural}, "
            f"~{chunk.tokens:,} tokens{oversized_flag}"
        )
        print(f"            {', '.join(def_names)}")

    print(f"📝 Manifest: {manifest_path}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Split large source files by top-level definitions"
    )
    parser.add_argument("file_path", help="Path to source file to split")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for chunk files",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8000,
        help="Maximum tokens per chunk (default: 8000)",
    )

    args = parser.parse_args()

    file_path = Path(args.file_path)
    output_dir = args.output_dir
    max_tokens = args.max_tokens

    # Validate inputs
    if not file_path.exists():
        print(f"❌ Error: {file_path} not found", file=sys.stderr)
        sys.exit(1)

    if not file_path.is_file():
        print(f"❌ Error: {file_path} is not a file", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse file
    definitions, imports, language = parse_file(file_path)

    if not definitions:
        print(
            f"⚠️  Warning: No definitions found in {file_path}, "
            "file may be too simple to split",
            file=sys.stderr,
        )
        sys.exit(0)

    # Create chunks
    chunks = create_chunks(definitions, imports, max_tokens)

    # Write chunks and manifest
    manifest = write_chunks(chunks, imports, file_path, output_dir, max_tokens)
    manifest_path = write_manifest(manifest, output_dir, file_path.stem)

    # Print summary
    print_summary(manifest, manifest_path)


if __name__ == "__main__":
    main()
