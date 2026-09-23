"""
Builds a directed call graph across the whole repo from CodeChunk.calls.
"""
import networkx as nx

from app.ingestion.chunker import CodeChunk


def build_call_graph(chunks: list[CodeChunk]) -> nx.DiGraph:
    graph = nx.DiGraph()
    by_name: dict[str, list[CodeChunk]] = {}
    by_file_and_name: dict[tuple[str, str], CodeChunk] = {}

    for c in chunks:
        graph.add_node(c.id, file_path=c.file_path, kind=c.kind, name=c.name)
        leaf_name = c.name.split(".")[-1]
        by_name.setdefault(leaf_name, []).append(c)
        by_file_and_name[(c.file_path, leaf_name)] = c

    unresolved = 0
    resolved = 0

    for c in chunks:
        for called_name in c.calls:
            same_file_match = by_file_and_name.get((c.file_path, called_name))
            if same_file_match and same_file_match.id != c.id:
                graph.add_edge(c.id, same_file_match.id, via="same_file")
                resolved += 1
                continue

            candidates = by_name.get(called_name)
            # skip ambiguous/common names — linking to every "get" or "__init__" in the
            # repo adds noise, not signal. Only trust repo-wide name matches when there's
            # a small number of candidates (likely a real, specific function name).
            if candidates and len(candidates) <= 3:
                for cand in candidates:
                    if cand.id != c.id:
                        graph.add_edge(c.id, cand.id, via="name_match")
                resolved += 1
            else:
                unresolved += 1

    print(f"[graph] {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges "
          f"({resolved} calls resolved, {unresolved} unresolved e.g. builtins/stdlib)")
    return graph


def get_dependencies(graph: nx.DiGraph, chunk_id: str, max_hops: int = 1) -> list[str]:
    if chunk_id not in graph:
        return []
    reachable = nx.single_source_shortest_path_length(graph, chunk_id, cutoff=max_hops)
    return [node for node in reachable if node != chunk_id]