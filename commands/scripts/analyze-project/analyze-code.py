#!/usr/bin/env python3
"""
Tree-sitter-based code analysis script.

Extracts structured code data (classes, functions, imports, etc.) from source files
using tree-sitter parsers instead of AI-based analysis.

Supported languages:
    - Python (.py): classes, functions, imports, exports, docstrings, decorators
    - JavaScript/TypeScript (.js, .jsx, .ts, .tsx): classes, functions, imports
    - Go (.go): (partial support)
    - Java (.java): (partial support)
    - Kotlin (.kt): (partial support)
    - Bash (.sh, .bash): (partial support)
    - Markdown (.md): headings, links, code blocks

Usage:
    uv run --python 3.12 --with "tree-sitter==0.21.3" --with tree-sitter-languages analyze-code.py <file_path> [--output analysis.json]
    uv run --python 3.12 --with "tree-sitter==0.21.3" --with tree-sitter-languages analyze-code.py --batch <batch_file> [--output analysis.json]

Note: Requires Python 3.12 (NOT 3.13+) due to tree-sitter-languages wheel availability.
      Python 3.13+ is not supported by tree-sitter-languages.

Exit codes:
    0 - Success
    1 - Usage error
    2 - Script error
"""

import sys

# CRITICAL: Python 3.13+ is not supported by tree-sitter-languages
if sys.version_info >= (3, 13):
    print("❌ Error: Python 3.13+ is not supported by tree-sitter-languages.", file=sys.stderr)
    print('   Run with: uv run --python 3.12 --with "tree-sitter==0.21.3" --with tree-sitter-languages analyze-code.py ...', file=sys.stderr)
    sys.exit(2)

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from tree_sitter_languages import get_language, get_parser
except ImportError:
    print("ERROR: tree-sitter-languages not available", file=sys.stderr)
    print('Run: uv run --python 3.12 --with "tree-sitter==0.21.3" --with tree-sitter-languages analyze-code.py', file=sys.stderr)
    sys.exit(2)


# Language mapping
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".sh": "bash",
    ".bash": "bash",
    ".md": "markdown",
}


def detect_language(file_path: Path) -> str | None:
    """Detect language from file extension."""
    suffix = file_path.suffix.lower()
    return LANGUAGE_MAP.get(suffix)


def get_node_text(node: Any, source_code: bytes) -> str:
    """Extract text from a tree-sitter node."""
    return source_code[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def find_docstring(node: Any, source_code: bytes) -> str:
    """Find docstring for a Python function/class."""
    # Look for first string literal in body
    for child in node.children:
        if child.type == "block":
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for expr in stmt.children:
                        if expr.type == "string":
                            text = get_node_text(expr, source_code)
                            # Remove quotes and clean up
                            text = text.strip('"""').strip("'''").strip('"').strip("'")
                            return text.strip()
    return ""


def extract_decorators(node: Any, source_code: bytes) -> list[str]:
    """Extract decorators from a Python function/class."""
    decorators = []

    # If this is a decorated_definition, decorators are children
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type == "decorator":
                decorators.append(get_node_text(child, source_code))
    # Otherwise, decorators appear as previous siblings
    elif node.parent:
        for sibling in node.parent.children:
            if sibling.type == "decorator":
                decorators.append(get_node_text(sibling, source_code))
            elif sibling == node:
                break
    return decorators


def extract_type_annotation(node: Any, source_code: bytes) -> str:
    """Extract type annotation from a parameter or return type."""
    for child in node.children:
        if child.type == "type":
            return get_node_text(child, source_code)
    return ""


def extract_python_imports(tree: Any, source_code: bytes, project_root: Path, file_path: Path) -> dict[str, list[str]]:
    """Extract imports from Python code."""
    internal = []
    external = []

    def traverse(node: Any) -> None:
        if node.type == "import_statement":
            # import module
            for child in node.children:
                if child.type == "dotted_name":
                    module = get_node_text(child, source_code)
                    if is_internal_import(module, project_root, file_path):
                        internal.append(module)
                    else:
                        external.append(module)

        elif node.type == "import_from_statement":
            # from module import ...
            module = None
            for child in node.children:
                if child.type == "dotted_name" or child.type == "relative_import":
                    module = get_node_text(child, source_code)
                    break

            if module:
                if module.startswith(".") or is_internal_import(module, project_root, file_path):
                    internal.append(module)
                else:
                    external.append(module)

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return {"internal": sorted(set(internal)), "external": sorted(set(external))}


def extract_python_functions(tree: Any, source_code: bytes) -> list[dict[str, Any]]:
    """Extract module-level functions from Python code."""
    functions = []

    def traverse(node: Any, depth: int = 0) -> None:
        # Only extract module-level functions (depth 1)
        if node.type == "function_definition" and depth == 1:
            func_data = {
                "name": "",
                "parameters": [],
                "return_type": "",
                "docstring": "",
                "decorators": [],
                "is_async": False,
            }

            # Check if async
            for child in node.children:
                if child.type == "async" or get_node_text(child, source_code) == "async":
                    func_data["is_async"] = True

            # Extract decorators
            func_data["decorators"] = extract_decorators(node, source_code)

            # Extract function details
            for child in node.children:
                if child.type == "identifier":
                    func_data["name"] = get_node_text(child, source_code)

                elif child.type == "parameters":
                    params = []
                    for param in child.children:
                        if param.type == "identifier":
                            params.append(get_node_text(param, source_code))
                        elif param.type == "typed_parameter" or param.type == "default_parameter":
                            params.append(get_node_text(param, source_code))
                    func_data["parameters"] = params

                elif child.type == "type":
                    func_data["return_type"] = get_node_text(child, source_code)

            # Extract docstring
            func_data["docstring"] = find_docstring(node, source_code)

            if func_data["name"]:
                functions.append(func_data)

        # Traverse children (skip class bodies to avoid extracting methods)
        if node.type != "class_definition":
            for child in node.children:
                traverse(child, depth + 1)

    traverse(tree.root_node)
    return functions


def extract_python_classes(tree: Any, source_code: bytes) -> list[dict[str, Any]]:
    """Extract classes from Python code."""
    classes = []

    def traverse(node: Any) -> None:
        if node.type == "class_definition":
            class_data = {
                "name": "",
                "docstring": "",
                "decorators": [],
                "inherits": [],
                "methods": [],
            }

            # Extract decorators
            class_data["decorators"] = extract_decorators(node, source_code)

            # Extract class details
            for child in node.children:
                if child.type == "identifier":
                    class_data["name"] = get_node_text(child, source_code)

                elif child.type == "argument_list":
                    # Base classes
                    for arg in child.children:
                        if arg.type == "identifier" or arg.type == "attribute":
                            base = get_node_text(arg, source_code)
                            if base not in ["(", ")", ","]:
                                class_data["inherits"].append(base)

                elif child.type == "block":
                    # Extract methods
                    for stmt in child.children:
                        # Handle both decorated and undecorated methods
                        method_node = stmt
                        if stmt.type == "decorated_definition":
                            # Find the function_definition child
                            for dec_child in stmt.children:
                                if dec_child.type == "function_definition":
                                    method_node = dec_child
                                    break

                        if method_node.type == "function_definition":
                            method_data = {
                                "name": "",
                                "parameters": [],
                                "return_type": "",
                                "docstring": "",
                                "decorators": [],
                                "is_async": False,
                            }

                            # Check if async
                            for m_child in method_node.children:
                                if m_child.type == "async" or get_node_text(m_child, source_code) == "async":
                                    method_data["is_async"] = True

                            # Extract decorators (from the original stmt node which may be decorated_definition)
                            method_data["decorators"] = extract_decorators(stmt, source_code)

                            # Extract method details
                            for m_child in method_node.children:
                                if m_child.type == "identifier":
                                    method_data["name"] = get_node_text(m_child, source_code)

                                elif m_child.type == "parameters":
                                    params = []
                                    for param in m_child.children:
                                        if param.type == "identifier":
                                            params.append(get_node_text(param, source_code))
                                        elif param.type == "typed_parameter" or param.type == "default_parameter":
                                            params.append(get_node_text(param, source_code))
                                    method_data["parameters"] = params

                                elif m_child.type == "type":
                                    method_data["return_type"] = get_node_text(m_child, source_code)

                            # Extract docstring
                            method_data["docstring"] = find_docstring(method_node, source_code)

                            if method_data["name"]:
                                class_data["methods"].append(method_data)

            # Extract class docstring
            class_data["docstring"] = find_docstring(node, source_code)

            if class_data["name"]:
                classes.append(class_data)

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return classes


def extract_python_exports(tree: Any, source_code: bytes, functions: list[dict], classes: list[dict]) -> list[str]:
    """Extract exported names from Python code."""
    exports = []

    # Check for __all__
    def traverse(node: Any) -> None:
        if node.type == "assignment":
            var_name = None
            for child in node.children:
                if child.type == "identifier":
                    var_name = get_node_text(child, source_code)
                elif child.type == "list" and var_name == "__all__":
                    for item in child.children:
                        if item.type == "string":
                            text = get_node_text(item, source_code).strip('"').strip("'")
                            exports.append(text)

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)

    # If no __all__, export all public functions and classes
    if not exports:
        for func in functions:
            if not func["name"].startswith("_"):
                exports.append(func["name"])
        for cls in classes:
            if not cls["name"].startswith("_"):
                exports.append(cls["name"])

    return sorted(set(exports))


def is_internal_import(module: str, project_root: Path, file_path: Path) -> bool:
    """Determine if an import is internal to the project."""
    if module.startswith("."):
        return True

    # Check if module path exists in project
    module_path = module.split(".")[0]
    potential_paths = [
        project_root / module_path,
        project_root / f"{module_path}.py",
        project_root / "src" / module_path,
        project_root / "src" / f"{module_path}.py",
    ]

    return any(p.exists() for p in potential_paths)


def extract_javascript_imports(tree: Any, source_code: bytes, project_root: Path, file_path: Path) -> dict[str, list[str]]:
    """Extract imports from JavaScript/TypeScript code."""
    internal = []
    external = []

    def traverse(node: Any) -> None:
        if node.type == "import_statement":
            # import ... from "module"
            for child in node.children:
                if child.type == "string":
                    module = get_node_text(child, source_code).strip('"').strip("'")
                    if module.startswith(".") or module.startswith("/"):
                        internal.append(module)
                    else:
                        external.append(module)

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return {"internal": sorted(set(internal)), "external": sorted(set(external))}


def extract_javascript_functions(tree: Any, source_code: bytes) -> list[dict[str, Any]]:
    """Extract functions from JavaScript/TypeScript code."""
    functions = []

    def traverse(node: Any, depth: int = 0) -> None:
        if depth == 1 and node.type in ["function_declaration", "arrow_function", "function"]:
            func_data = {
                "name": "",
                "parameters": [],
                "return_type": "",
                "docstring": "",
                "decorators": [],
                "is_async": False,
            }

            # Check if async
            for child in node.children:
                if get_node_text(child, source_code) == "async":
                    func_data["is_async"] = True

            # Extract function details
            for child in node.children:
                if child.type == "identifier":
                    func_data["name"] = get_node_text(child, source_code)
                elif child.type == "formal_parameters":
                    params = []
                    for param in child.children:
                        if param.type == "identifier" or param.type == "required_parameter":
                            params.append(get_node_text(param, source_code))
                    func_data["parameters"] = params

            if func_data["name"]:
                functions.append(func_data)

        if node.type != "class_declaration":
            for child in node.children:
                traverse(child, depth + 1)

    traverse(tree.root_node)
    return functions


def extract_javascript_classes(tree: Any, source_code: bytes) -> list[dict[str, Any]]:
    """Extract classes from JavaScript/TypeScript code."""
    classes = []

    def traverse(node: Any) -> None:
        if node.type == "class_declaration":
            class_data = {
                "name": "",
                "docstring": "",
                "decorators": [],
                "inherits": [],
                "methods": [],
            }

            # Extract class details
            for child in node.children:
                if child.type == "identifier":
                    class_data["name"] = get_node_text(child, source_code)
                elif child.type == "class_heritage":
                    for heritage in child.children:
                        if heritage.type == "identifier":
                            class_data["inherits"].append(get_node_text(heritage, source_code))
                elif child.type == "class_body":
                    # Extract methods
                    for member in child.children:
                        if member.type == "method_definition":
                            method_data = {
                                "name": "",
                                "parameters": [],
                                "return_type": "",
                                "docstring": "",
                                "decorators": [],
                                "is_async": False,
                            }

                            for m_child in member.children:
                                if m_child.type == "property_identifier":
                                    method_data["name"] = get_node_text(m_child, source_code)
                                elif m_child.type == "formal_parameters":
                                    params = []
                                    for param in m_child.children:
                                        if param.type == "identifier" or param.type == "required_parameter":
                                            params.append(get_node_text(param, source_code))
                                    method_data["parameters"] = params

                            if method_data["name"]:
                                class_data["methods"].append(method_data)

            if class_data["name"]:
                classes.append(class_data)

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return classes


def extract_markdown_headings(tree: Any, source_code: bytes) -> list[dict[str, Any]]:
    """Extract headings from Markdown."""
    headings = []

    def traverse(node: Any) -> None:
        if node.type == "atx_heading":
            heading_data = {"level": 0, "text": ""}

            # Determine heading level (h1, h2, h3, etc.)
            for child in node.children:
                if child.type.startswith("atx_h"):
                    level_str = child.type.replace("atx_h", "").replace("_marker", "")
                    heading_data["level"] = int(level_str)
                elif child.type == "heading_content":
                    heading_data["text"] = get_node_text(child, source_code).strip()

            if heading_data["text"]:
                headings.append(heading_data)

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return headings


def extract_markdown_links(tree: Any, source_code: bytes) -> list[dict[str, str]]:
    """Extract links from Markdown."""
    links = []

    def traverse(node: Any) -> None:
        if node.type == "link":
            link_data = {"text": "", "url": ""}

            for child in node.children:
                if child.type == "link_text":
                    link_data["text"] = get_node_text(child, source_code)
                elif child.type == "link_destination":
                    link_data["url"] = get_node_text(child, source_code)

            if link_data["url"]:
                links.append(link_data)

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return links


def extract_markdown_code_blocks(tree: Any, source_code: bytes) -> list[dict[str, Any]]:
    """Extract code blocks from Markdown."""
    code_blocks = []

    def traverse(node: Any) -> None:
        if node.type == "fenced_code_block":
            code_data = {"language": "", "code": ""}

            for child in node.children:
                if child.type == "info_string":
                    code_data["language"] = get_node_text(child, source_code).strip()
                elif child.type == "code_fence_content":
                    code_data["code"] = get_node_text(child, source_code).strip()

            if code_data["code"]:
                code_blocks.append(code_data)

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return code_blocks


def analyze_file(file_path: Path, project_root: Path) -> dict[str, Any] | None:
    """Analyze a single file and extract structured data."""
    language = detect_language(file_path)
    if not language:
        return None

    try:
        # Use tree_sitter_languages.get_parser()
        parser = get_parser(language)
        source_code = file_path.read_bytes()
        tree = parser.parse(source_code)

        # Initialize result
        try:
            relative_path = file_path.relative_to(project_root)
        except ValueError:
            # File is not under project root, use absolute path
            relative_path = file_path

        result = {
            "file": str(relative_path),
            "language": language.capitalize(),
            "purpose": "",
            "imports": {"internal": [], "external": []},
            "exports": [],
            "classes": [],
            "functions": [],
            "dependencies": [],
        }

        # Extract based on language
        if language == "python":
            result["imports"] = extract_python_imports(tree, source_code, project_root, file_path)
            result["functions"] = extract_python_functions(tree, source_code)
            result["classes"] = extract_python_classes(tree, source_code)
            result["exports"] = extract_python_exports(tree, source_code, result["functions"], result["classes"])
            result["dependencies"] = sorted(set(result["imports"]["external"]))

        elif language in ["javascript", "typescript", "tsx"]:
            result["imports"] = extract_javascript_imports(tree, source_code, project_root, file_path)
            result["functions"] = extract_javascript_functions(tree, source_code)
            result["classes"] = extract_javascript_classes(tree, source_code)
            result["dependencies"] = sorted(set(result["imports"]["external"]))

        elif language == "markdown":
            # For Markdown, we extract different data structure
            result["headings"] = extract_markdown_headings(tree, source_code)
            result["links"] = extract_markdown_links(tree, source_code)
            result["code_blocks"] = extract_markdown_code_blocks(tree, source_code)
            # Extract external links as dependencies
            result["dependencies"] = sorted(set([link["url"] for link in result["links"] if link["url"].startswith("http")]))

        # TODO: Add support for Go, Java, etc.

        return result

    except Exception as e:
        print(f"ERROR analyzing {file_path}: {e}", file=sys.stderr)
        return None


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Tree-sitter-based code analysis")
    parser.add_argument("file_or_batch", help="File path or batch file (with --batch)")
    parser.add_argument("--batch", action="store_true", help="Process batch file")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    # Determine project root (go up until we find .git)
    project_root = Path.cwd()
    while not (project_root / ".git").exists() and project_root != project_root.parent:
        project_root = project_root.parent

    results = []

    if args.batch:
        # Process batch file
        batch_file = Path(args.file_or_batch)
        if not batch_file.exists():
            print(f"ERROR: Batch file not found: {batch_file}", file=sys.stderr)
            return 1

        with batch_file.open() as f:
            for line in f:
                file_path = Path(line.strip())
                if file_path.exists():
                    result = analyze_file(file_path, project_root)
                    if result:
                        results.append(result)
    else:
        # Process single file
        file_path = Path(args.file_or_batch)
        if not file_path.exists():
            print(f"ERROR: File not found: {file_path}", file=sys.stderr)
            return 1

        result = analyze_file(file_path, project_root)
        if result:
            results.append(result)

    # Output results
    if args.output:
        output_file = Path(args.output)
        with output_file.open("w") as f:
            json.dump(results if args.batch else results[0], f, indent=2)
    else:
        print(json.dumps(results if args.batch else results[0], indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
