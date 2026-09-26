"""
Embeds each CodeChunk and stores it in a local Chroma collection.

Uses OpenAI's embedding API (text-embedding-3-small) rather than a local
sentence-transformers model. This trade-off exists specifically for the
deployed environment: the local model (~90MB + torch, several hundred MB
of RAM at runtime) doesn't fit in Render's free-tier 512MB memory limit,
so the API-based approach is used instead — a few cents of API cost per
index in exchange for a much smaller memory footprint.
"""
import os
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

from app.ingestion.chunker import CodeChunk

load_dotenv()
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_EMBED_MODEL = "text-embedding-3-small"


class OpenAIEmbeddingFunction:
    """Chroma-compatible embedding function backed by the OpenAI API."""
    def __call__(self, input):
        response = _client.embeddings.create(model=_EMBED_MODEL, input=input)
        return [d.embedding for d in response.data]

    def name(self) -> str:
        return "openai-text-embedding-3-small"


def get_chroma_client(persist_dir: str = ".chroma"):
    return chromadb.PersistentClient(path=persist_dir)


def get_or_create_collection(client, collection_name: str):
    return client.get_or_create_collection(name=collection_name, embedding_function=OpenAIEmbeddingFunction())


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