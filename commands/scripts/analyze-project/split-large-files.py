#!/usr/bin/env python3
"""
Split large source files by top-level definitions.

For files too large to analyze in one pass, splits them into smaller chunks
where each chunk contains one or more top-level definitions (classes, functions).

Uses tree-sitter for robust parsing across multiple languages.

REQUIREMENTS:
  - Python 3.12 (tree-sitter-languages not yet compatible with 3.13+)
  - tree-sitter==0.21.3 (compatibility with tree-sitter-languages)
  - tree-sitter-languages

Usage:
  uv run --python 3.12 --with "tree-sitter==0.21.3" --with tree-sitter-languages \\
    split-large-files.py <file> --output-dir <dir>
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Check Python version early
if sys.version_info >= (3, 13):
    print(
        "❌ Error: Python 3.13+ not supported by tree-sitter-languages.\n"
        "   Use: uv run --python 3.12 --with 'tree-sitter==0.21.3' "
        "--with tree-sitter-languages split-large-files.py ...",
        file=sys.stderr,
    )
    sys.exit(2)

try:
    from tree_sitter_languages import get_language, get_parser
except ImportError:
    print(
        "❌ Error: tree-sitter-languages not installed.\n"
        "   Use: uv run --python 3.12 --with 'tree-sitter==0.21.3' "
        "--with tree-sitter-languages split-large-files.py ...",
        file=sys.stderr,
    )
    sys.exit(2)


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


# Language mapping: file extension -> (tree-sitter language name, display name)
# Note: Swift removed due to missing symbols in tree-sitter-languages
LANGUAGE_MAP = {
    ".py": ("python", "Python"),
    ".js": ("javascript", "JavaScript"),
    ".jsx": ("javascript", "JavaScript"),
    ".ts": ("typescript", "TypeScript"),
    ".tsx": ("tsx", "TypeScript"),
    ".go": ("go", "Go"),
    ".java": ("java", "Java"),
    ".kt": ("kotlin", "Kotlin"),
    ".rb": ("ruby", "Ruby"),
    ".php": ("php", "PHP"),
    ".c": ("c", "C"),
    ".cpp": ("cpp", "C++"),
    ".cc": ("cpp", "C++"),
    ".h": ("c", "C/C++ Header"),
    ".hpp": ("cpp", "C++ Header"),
    ".cs": ("c_sharp", "C#"),
    ".rs": ("rust", "Rust"),
}


# Node types for top-level definitions per language
DEFINITION_NODES = {
    "python": ["class_definition", "function_definition", "decorated_definition"],
    "javascript": [
        "class_declaration",
        "function_declaration",
        "lexical_declaration",  # const/let
        "variable_declaration",  # var
        "export_statement",
    ],
    "typescript": [
        "class_declaration",
        "function_declaration",
        "lexical_declaration",
        "variable_declaration",
        "export_statement",
        "interface_declaration",
        "type_alias_declaration",
    ],
    "tsx": [
        "class_declaration",
        "function_declaration",
        "lexical_declaration",
        "variable_declaration",
        "export_statement",
        "interface_declaration",
        "type_alias_declaration",
    ],
    "go": [
        "function_declaration",
        "method_declaration",
        "type_declaration",
        "const_declaration",
        "var_declaration",
    ],
    "java": [
        "class_declaration",
        "interface_declaration",
        "method_declaration",
        "field_declaration",
        "enum_declaration",
    ],
    "kotlin": [
        "class_declaration",
        "function_declaration",
        "object_declaration",
        "property_declaration",
    ],
    "ruby": [
        "class",
        "module",
        "method",
    ],
    "php": [
        "class_declaration",
        "function_definition",
        "trait_declaration",
        "interface_declaration",
    ],
    "c": [
        "function_definition",
        "struct_specifier",
        "enum_specifier",
        "type_definition",
    ],
    "cpp": [
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "enum_specifier",
        "namespace_definition",
    ],
    "c_sharp": [
        "class_declaration",
        "interface_declaration",
        "method_declaration",
        "struct_declaration",
        "enum_declaration",
    ],
    "rust": [
        "function_item",
        "struct_item",
        "enum_item",
        "trait_item",
        "impl_item",
        "mod_item",
    ],
}


# Node types for import statements per language
IMPORT_NODES = {
    "python": ["import_statement", "import_from_statement"],
    "javascript": ["import_statement", "export_statement"],
    "typescript": ["import_statement", "export_statement"],
    "tsx": ["import_statement", "export_statement"],
    "go": ["import_declaration"],
    "java": ["import_declaration"],
    "kotlin": ["import_header"],
    "ruby": ["method_call"],  # require statements
    "php": ["namespace_use_declaration"],
    "c": ["preproc_include"],
    "cpp": ["preproc_include", "using_declaration"],
    "c_sharp": ["using_directive"],
    "rust": ["use_declaration"],
}


def detect_language(file_path: Path) -> tuple[str, str] | None:
    """
    Detect language from file extension.

    Returns:
        tuple: (tree-sitter language name, display name) or None if unsupported
    """
    ext = file_path.suffix.lower()
    return LANGUAGE_MAP.get(ext)


def get_node_name(node: Any, source_bytes: bytes) -> str:
    """
    Extract the name/identifier from a tree-sitter node.

    Looks for common name fields like 'name', 'declarator', 'pattern', etc.
    Falls back to checking for identifier child nodes (Python classes/functions).
    Handles decorated definitions by recursively extracting from wrapped node.
    """
    # Special case: Python decorated_definition - extract name from wrapped definition
    if node.type == "decorated_definition":
        # Find the wrapped definition (class_definition or function_definition)
        for child in node.children:
            if child.type in ("class_definition", "function_definition"):
                return get_node_name(child, source_bytes)

    # Method 1: Try field-based access (works for many languages)
    name_node = node.child_by_field_name("name")
    if name_node:
        return source_bytes[name_node.start_byte:name_node.end_byte].decode(
            "utf-8", errors="replace"
        ).strip()

    # Method 2: Try declarator field (for C/C++)
    declarator = node.child_by_field_name("declarator")
    if declarator:
        # Might be nested (function_declarator -> identifier)
        inner_name = declarator.child_by_field_name("name")
        if inner_name:
            return source_bytes[inner_name.start_byte:inner_name.end_byte].decode(
                "utf-8", errors="replace"
            ).strip()
        # Or direct identifier
        if declarator.type == "identifier":
            return source_bytes[declarator.start_byte:declarator.end_byte].decode(
                "utf-8", errors="replace"
            ).strip()

    # Method 3: Try pattern field (for variable declarations)
    pattern = node.child_by_field_name("pattern")
    if pattern and pattern.type == "identifier":
        return source_bytes[pattern.start_byte:pattern.end_byte].decode(
            "utf-8", errors="replace"
        ).strip()

    # Method 4: Look for identifier among direct children (Python classes/functions)
    for child in node.children:
        if child.type == "identifier":
            return source_bytes[child.start_byte:child.end_byte].decode(
                "utf-8", errors="replace"
            ).strip()

    # Method 5: Look for property_identifier (JavaScript/TypeScript methods)
    for child in node.children:
        if child.type == "property_identifier":
            return source_bytes[child.start_byte:child.end_byte].decode(
                "utf-8", errors="replace"
            ).strip()

    # Fallback: use node type and line number
    return f"{node.type}_{node.start_point[0]}"


def is_import_or_export(node: Any, lang: str) -> bool:
    """Check if node is an import/export statement."""
    import_types = IMPORT_NODES.get(lang, [])

    # Direct type match
    if node.type in import_types:
        return True

    # For Ruby, check if it's a require/require_relative call
    if lang == "ruby" and node.type == "method_call":
        method_name_node = node.child_by_field_name("method")
        if method_name_node:
            method_name = method_name_node.text.decode("utf-8", errors="replace")
            return method_name in ("require", "require_relative")

    return False


def extract_imports(tree: Any, source_bytes: bytes, lang: str) -> str:
    """Extract all import/export statements from the tree."""
    import_lines: list[str] = []

    def traverse(node: Any) -> None:
        if is_import_or_export(node, lang):
            import_text = source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
            import_lines.append(import_text)

        # Only traverse top-level for imports
        if node.parent is None or node.parent.type in ("program", "module"):
            for child in node.children:
                traverse(child)

    traverse(tree.root_node)
    return "\n".join(import_lines) if import_lines else ""


def is_definition_node(node: Any, lang: str) -> bool:
    """Check if node is a top-level definition."""
    def_types = DEFINITION_NODES.get(lang, [])

    # Direct type match
    if node.type in def_types:
        return True

    # For JavaScript/TypeScript, check if lexical_declaration contains a function
    if lang in ("javascript", "typescript", "tsx") and node.type in (
        "lexical_declaration",
        "variable_declaration",
    ):
        # Check if it contains a function or class expression
        for child in node.children:
            if child.type in (
                "variable_declarator",
            ):
                for grandchild in child.children:
                    if grandchild.type in (
                        "arrow_function",
                        "function_expression",
                        "class",
                    ):
                        return True

    return False


def extract_definitions(tree: Any, source_bytes: bytes, lang: str) -> list[Definition]:
    """
    Extract top-level definitions from tree-sitter parse tree.

    Returns:
        list[Definition]: Top-level definitions with name, location, and content
    """
    definitions: list[Definition] = []
    source_lines = source_bytes.decode("utf-8", errors="replace").split("\n")

    # Get root node
    root = tree.root_node

    # Traverse only direct children of root (top-level definitions)
    for node in root.children:
        # Skip import/export statements (handled separately)
        if is_import_or_export(node, lang):
            continue

        # Check if this is a definition node
        if not is_definition_node(node, lang):
            continue

        # Extract name
        name = get_node_name(node, source_bytes)

        # Get location
        start_line = node.start_point[0]
        end_line = node.end_point[0] + 1  # Make it exclusive

        # Extract content
        content = source_bytes[node.start_byte : node.end_byte].decode(
            "utf-8", errors="replace"
        )

        definitions.append(
            Definition(
                name=name,
                start_line=start_line,
                end_line=end_line,
                content=content,
            )
        )

    return definitions


def parse_file_with_treesitter(
    file_path: Path,
) -> tuple[list[Definition], str, str]:
    """
    Parse source file using tree-sitter.

    Returns:
        tuple: (list of definitions, imports string, language display name)

    Raises:
        SystemExit(1): If language not supported by tree-sitter
        SystemExit(2): If tree-sitter initialization or parsing fails
    """
    lang_info = detect_language(file_path)
    if not lang_info:
        print(
            f"❌ Error: Language not supported for {file_path.suffix}\n"
            f"   Supported extensions: {', '.join(sorted(LANGUAGE_MAP.keys()))}",
            file=sys.stderr,
        )
        sys.exit(1)

    ts_lang_name, display_name = lang_info

    # Get parser for this language
    try:
        parser = get_parser(ts_lang_name)
    except Exception as e:
        print(
            f"❌ Error: Failed to initialize tree-sitter parser for {ts_lang_name}: {e}\n"
            f"   This is a script error. Check tree-sitter-languages installation.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Read file content
    try:
        content = file_path.read_bytes()
    except Exception as e:
        print(f"❌ Error: Cannot read {file_path}: {e}", file=sys.stderr)
        sys.exit(2)

    # Parse the file
    try:
        tree = parser.parse(content)
    except Exception as e:
        print(
            f"❌ Error: Tree-sitter parsing failed for {file_path}: {e}\n"
            f"   This is a script error. File may be corrupted or parser incompatible.",
            file=sys.stderr,
        )
        sys.exit(2)

    # Extract imports and definitions
    imports = extract_imports(tree, content, ts_lang_name)
    definitions = extract_definitions(tree, content, ts_lang_name)

    return definitions, imports, display_name


def parse_file(file_path: Path) -> tuple[list[Definition], str, str]:
    """
    Parse source file and extract top-level definitions using tree-sitter.

    Returns:
        tuple: (list of definitions, imports string, language)

    Raises:
        SystemExit(1): If language not supported
        SystemExit(2): If parsing fails
    """
    return parse_file_with_treesitter(file_path)


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
    relative_path: str | None = None,
) -> ChunkManifest:
    """
    Write chunks to output directory and create manifest.

    Args:
        chunks: List of definition chunks
        imports: Import statements to include in each chunk
        file_path: Absolute path to original file
        output_dir: Directory to write chunks
        max_tokens: Maximum tokens per chunk
        relative_path: Relative path from project root (for naming)

    Returns:
        ChunkManifest with metadata about all chunks
    """
    # Use relative_path for naming if provided, otherwise fall back to file_path.stem
    if relative_path:
        safe_prefix = relative_path.replace("/", "__").replace("\\", "__")
    else:
        safe_prefix = file_path.stem

    extension = file_path.suffix

    lang_info = detect_language(file_path)
    language = lang_info[1] if lang_info else "Unknown"

    chunk_infos: list[ChunkInfo] = []
    total_tokens = 0

    for idx, chunk_defs in enumerate(chunks, start=1):
        chunk_filename = f"{safe_prefix}_chunk_{idx}{extension}"
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


def write_manifest(manifest: ChunkManifest, output_dir: Path, safe_prefix: str) -> Path:
    """
    Write manifest JSON file.

    Args:
        manifest: Chunk manifest data
        output_dir: Directory to write manifest
        safe_prefix: Safe filename prefix (path with / replaced by __)

    Returns:
        Path to created manifest file
    """
    manifest_path = output_dir / f"{safe_prefix}.chunks.json"

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
        description="Split large source files by top-level definitions using tree-sitter"
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
    parser.add_argument(
        "--relative-path",
        type=str,
        help="Relative path from project root (for naming chunks and manifest)",
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
    manifest = write_chunks(
        chunks, imports, file_path, output_dir, max_tokens, args.relative_path
    )

    # Determine safe prefix for manifest
    if args.relative_path:
        safe_prefix = args.relative_path.replace("/", "__").replace("\\", "__")
    else:
        safe_prefix = file_path.stem

    manifest_path = write_manifest(manifest, output_dir, safe_prefix)

    # Print summary
    print_summary(manifest, manifest_path)


if __name__ == "__main__":
    main()
