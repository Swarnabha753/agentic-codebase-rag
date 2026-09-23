"""
Embeds each CodeChunk and stores it in a local Chroma collection.

Uses a local sentence-transformers model (all-MiniLM-L6-v2) by default so the
project runs fully offline with no API key/billing dependency. This is a
deliberate trade-off worth stating in interviews: MiniLM is smaller/faster
than OpenAI's text-embedding-3-small and slightly less accurate on semantic
similarity, but it removes an external dependency and cost from the demo.
Swapping to OpenAI embeddings later is a one-line change if higher retrieval
quality is needed.
"""
import chromadb
from chromadb.utils import embedding_functions

from app.ingestion.chunker import CodeChunk

_EMBED_MODEL_NAME = "all-MiniLM-L6-v2"


def get_chroma_client(persist_dir: str = ".chroma"):
    return chromadb.PersistentClient(path=persist_dir)


def get_or_create_collection(client, collection_name: str):
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=_EMBED_MODEL_NAME)
    return client.get_or_create_collection(name=collection_name, embedding_function=embed_fn)


def _chunk_to_document(chunk: CodeChunk) -> str:
    header = f"{chunk.kind} {chunk.name} in {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})"
    return f"{header}\n\n{chunk.source}"


def index_chunks(collection, chunks: list[CodeChunk], batch_size: int = 100):
    total = len(chunks)
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        collection.upsert(
            ids=[c.id for c in batch],
            documents=[_chunk_to_document(c) for c in batch],
            metadatas=[{
                "file_path": c.file_path,
                "kind": c.kind,
                "name": c.name,
                "start_line": c.start_line,
                "end_line": c.end_line,
            } for c in batch],
        )
        print(f"[index] embedded {min(i + batch_size, total)}/{total} chunks")


def query_chunks(collection, query_text: str, top_k: int = 5) -> list[dict]:
    results = collection.query(query_texts=[query_text], n_results=top_k)
    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return hits