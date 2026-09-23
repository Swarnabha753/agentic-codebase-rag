"""
Extracts the names of functions/methods called *within* each chunk's body.
This populates CodeChunk.calls, which graph.py later uses to build the
cross-file dependency graph that drives the agent's iterative retrieval.

We deliberately extract raw call names (not fully resolved symbols) here.
Resolution against imports happens in graph.py, since it needs the whole
repo's chunk index to disambiguate "which file does `run` belong to".
"""
from app.ingestion.parsers import get_parser

CALL_NODE_TYPES = {
    "python": "call",
    "javascript": "call_expression",
    "typescript": "call_expression",
}


def _extract_call_name(call_node, source_bytes: bytes) -> str | None:
    """Given a call node, pull the callee name (handles `foo()` and `obj.foo()`)."""
    func_node = call_node.child_by_field_name("function")
    if func_node is None:
        return None

    if func_node.type in ("identifier",):
        return source_bytes[func_node.start_byte:func_node.end_byte].decode("utf-8", errors="ignore")

    if func_node.type in ("attribute", "member_expression"):
        # obj.method(...) -> we want "method" (the attribute/property name)
        attr_node = func_node.child_by_field_name("attribute") or func_node.child_by_field_name("property")
        if attr_node is not None:
            return source_bytes[attr_node.start_byte:attr_node.end_byte].decode("utf-8", errors="ignore")

    return None


def extract_calls_from_source(snippet: str, language: str) -> list[str]:
    """Parses a chunk's own source snippet in isolation and returns called names."""
    parser = get_parser(language)
    source_bytes = snippet.encode("utf-8")
    tree = parser.parse(source_bytes)
    call_type = CALL_NODE_TYPES[language]

    calls: set[str] = set()

    def walk(node):
        if node.type == call_type:
            name = _extract_call_name(node, source_bytes)
            if name:
                calls.add(name)
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return sorted(calls)
