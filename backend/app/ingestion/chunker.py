"""
AST-based chunking using tree-sitter.

Why not fixed-size text chunking (the naive RAG approach)?
- A 500-char chunk can cut a function in half, destroying its meaning for retrieval.
- Code has natural semantic units: functions, methods, classes. We chunk on those boundaries.
- Each chunk carries structured metadata (name, file, line range) that we later use
  to build the call graph — fixed-size text chunks can't support that.
"""
from dataclasses import dataclass, field

from app.ingestion.clone import SourceFile
from app.ingestion.parsers import get_parser

# node types per language that represent a "chunkable" unit
CHUNK_NODE_TYPES = {
    "python": {"function_definition", "class_definition"},
    "javascript": {"function_declaration", "class_declaration", "method_definition", "arrow_function"},
    "typescript": {"function_declaration", "class_declaration", "method_definition", "arrow_function"},
}

# node types that represent import/require statements (used later for the call graph)
IMPORT_NODE_TYPES = {
    "python": {"import_statement", "import_from_statement"},
    "javascript": {"import_statement"},
    "typescript": {"import_statement"},
}


@dataclass
class CodeChunk:
    id: str  # unique id, e.g. "src/flask/app.py::Flask.run"
    file_path: str
    language: str
    kind: str  # "function" | "class" | "method"
    name: str
    start_line: int
    end_line: int
    source: str
    calls: list[str] = field(default_factory=list)  # names this chunk calls (filled in graph.py)
    imports: list[str] = field(default_factory=list)  # raw import text for this file


def _node_name(node, source_bytes: bytes) -> str:
    """Best-effort extraction of a function/class name from its AST node."""
    for child in node.children:
        if child.type in ("identifier", "property_identifier"):
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="ignore")
    return "<anonymous>"


def chunk_file(source_file: SourceFile) -> list[CodeChunk]:
    """Parses one file and returns its function/class-level chunks."""
    lang = source_file.language
    parser = get_parser(lang)

    with open(source_file.abs_path, "rb") as f:
        source_bytes = f.read()

    tree = parser.parse(source_bytes)
    chunk_types = CHUNK_NODE_TYPES[lang]
    import_types = IMPORT_NODE_TYPES[lang]

    chunks: list[CodeChunk] = []
    imports: list[str] = []

    def walk(node, class_prefix: str | None = None):
        if node.type in import_types:
            imports.append(source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore"))

        if node.type in chunk_types:
            name = _node_name(node, source_bytes)
            qualified_name = f"{class_prefix}.{name}" if class_prefix else name
            kind = "class" if "class" in node.type else ("method" if class_prefix else "function")
            chunk_id = f"{source_file.rel_path}::{qualified_name}:{node.start_point[0] + 1}"
            snippet = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
            chunks.append(CodeChunk(
                id=chunk_id,
                file_path=source_file.rel_path,
                language=lang,
                kind=kind,
                name=qualified_name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                source=snippet,
            ))
            # recurse into class bodies to pick up methods, tagging them with the class name
            next_prefix = qualified_name if kind == "class" else class_prefix
            for child in node.children:
                walk(child, next_prefix)
            return  # don't double-descend into function bodies for nested defs beyond this point

        for child in node.children:
            walk(child, class_prefix)

    walk(tree.root_node)

    # attach the file's import list to every chunk (used by the call graph to resolve cross-file calls)
    for c in chunks:
        c.imports = imports

    return chunks


def chunk_repo(source_files: list[SourceFile]) -> list[CodeChunk]:
    """Chunks every file in the repo, skipping files that fail to parse."""
    all_chunks: list[CodeChunk] = []
    failed = 0
    for sf in source_files:
        try:
            all_chunks.extend(chunk_file(sf))
        except Exception as e:
            failed += 1
            continue
    print(f"[chunker] extracted {len(all_chunks)} chunks from {len(source_files)} files ({failed} failed to parse)")
    return all_chunks
