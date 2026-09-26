"""
Pure-Python vector store — no compiled/native dependencies (no ChromaDB,
no hnswlib). This exists specifically because ChromaDB's native HNSW index
(hnswlib) crashes with SIGILL (illegal instruction) on Render's free-tier
CPUs — a real, confirmed production constraint, not a made-up one. Cosine
similarity here is computed in plain Python; for repo sizes this project
targets (a few thousand chunks), this is fast enough and removes an entire
class of native-crash risk.
"""
import json
import math
import os
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

from app.ingestion.chunker import CodeChunk

load_dotenv()
_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_EMBED_MODEL = "text-embedding-3-small"


class SimpleVectorCollection:
    """In-memory vector store: id -> {embedding, document, metadata}."""
    def __init__(self, name: str, persist_dir: str = ".vectorstore"):
        self.name = name
        self.persist_path = os.path.join(persist_dir, f"{name}.json")
        os.makedirs(persist_dir, exist_ok=True)
        self._data: dict[str, dict] = {}
        if os.path.exists(self.persist_path):
            with open(self.persist_path, "r") as f:
                self._data = json.load(f)

    def _save(self):
        with open(self.persist_path, "w") as f:
            json.dump(self._data, f)

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict]):
        embeddings = _embed_texts(documents)
        for id_, doc, meta, emb in zip(ids, documents, metadatas, embeddings):
            self._data[id_] = {"embedding": emb, "document": doc, "metadata": meta}
        self._save()

    def query(self, query_texts: list[str], n_results: int = 5) -> dict:
        query_embedding = _embed_texts(query_texts)[0]
        scored = []
        for id_, entry in self._data.items():
            sim = _cosine_similarity(query_embedding, entry["embedding"])
            scored.append((sim, id_))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_results]

        return {
            "ids": [[id_ for _, id_ in top]],
            "documents": [[self._data[id_]["document"] for _, id_ in top]],
            "metadatas": [[self._data[id_]["metadata"] for _, id_ in top]],
            "distances": [[1 - sim for sim, _ in top]],  # convert similarity -> distance-like scale
        }

    def get(self, ids: list[str]) -> dict:
        found = [(id_, self._data[id_]) for id_ in ids if id_ in self._data]
        return {
            "ids": [id_ for id_, _ in found],
            "documents": [entry["document"] for _, entry in found],
            "metadatas": [entry["metadata"] for _, entry in found],
        }


def _truncate_for_embedding(text: str, max_chars: int = 24000) -> str:
    """
    Rough truncation to stay under OpenAI's 8192-token embedding limit.
    ~4 chars/token is a safe average for code+English text, so 24000 chars
    stays comfortably under the limit without needing a real tokenizer.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def _embed_texts(texts: list[str]) -> list[list[float]]:
    safe_texts = [_truncate_for_embedding(t) for t in texts]
    response = _client.embeddings.create(model=_EMBED_MODEL, input=safe_texts)
    return [d.embedding for d in response.data]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_chroma_client(persist_dir: str = ".vectorstore"):
    """Kept for API compatibility with existing call sites — returns the persist dir."""
    return persist_dir


def get_or_create_collection(persist_dir: str, collection_name: str) -> SimpleVectorCollection:
    return SimpleVectorCollection(collection_name, persist_dir)


def _chunk_to_document(chunk: CodeChunk) -> str:
    header = f"{chunk.kind} {chunk.name} in {chunk.file_path} (lines {chunk.start_line}-{chunk.end_line})"
    return f"{header}\n\n{chunk.source}"


def index_chunks(collection: SimpleVectorCollection, chunks: list[CodeChunk], batch_size: int = 100):
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


def query_chunks(collection: SimpleVectorCollection, query_text: str, top_k: int = 5) -> list[dict]:
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