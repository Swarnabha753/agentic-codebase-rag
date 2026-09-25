"""
FastAPI wrapper exposing the ingestion + agent pipeline as an HTTP API.

Endpoints:
  POST /index  — clone + chunk + graph + embed a repo (run once per repo)
  POST /query  — ask a question against an already-indexed repo
"""
import hashlib
import os
import shutil

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.ingestion.calls import extract_calls_from_source
from app.ingestion.chunker import chunk_repo
from app.ingestion.clone import _force_remove_readonly, clone_repo, discover_source_files, cleanup_repo
from app.indexing.graph import build_call_graph
from app.indexing.vectorstore import get_chroma_client, get_or_create_collection, index_chunks
from app.agent.rag_agent import run_agent, run_baseline

app = FastAPI(title="Agentic Codebase RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://agentic-codebase-rag-sh9a-alpha.vercel.app", "http://localhost:5173"],  # fine for a portfolio project; tighten for real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

# in-memory cache: repo_url -> (chroma collection, call graph)
# a real production system would persist this; in-memory is fine for a demo
_INDEXED_REPOS: dict[str, dict] = {}


class IndexRequest(BaseModel):
    repo_url: str


class QueryRequest(BaseModel):
    repo_url: str
    question: str


def _repo_key(repo_url: str) -> str:
    return hashlib.sha256(repo_url.encode()).hexdigest()[:16]


@app.post("/index")
def index_repo(req: IndexRequest):
    key = _repo_key(req.repo_url)
    if key in _INDEXED_REPOS:
        return {"status": "already_indexed", "repo_url": req.repo_url}

    from app.ingestion.clone import _force_remove_readonly
    clone_dir = f"tmp_repos/{key}"
    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir, onexc=_force_remove_readonly)
        
    try:
        path = clone_repo(req.repo_url, clone_dir)
        files = discover_source_files(path)
        if not files:
            raise HTTPException(status_code=400, detail="No supported source files (Python/JS/TS) found in repo")

        chunks = chunk_repo(files)
        for c in chunks:
            c.calls = extract_calls_from_source(c.source, c.language)

        graph = build_call_graph(chunks)

        client = get_chroma_client(f".chroma/{key}")
        collection = get_or_create_collection(client, key)
        index_chunks(collection, chunks)

        _INDEXED_REPOS[key] = {"collection": collection, "graph": graph, "repo_url": req.repo_url}
        cleanup_repo(path)

        lang_counts = {}
        for f in files:
            lang_counts[f.language] = lang_counts.get(f.language, 0) + 1

        return {
            "status": "indexed",
            "repo_url": req.repo_url,
            "file_count": len(files),
            "chunk_count": len(chunks),
            "graph_edges": graph.number_of_edges(),
            "languages": lang_counts,
        }

        return {"status": "indexed", "repo_url": req.repo_url, "chunk_count": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
def query_repo(req: QueryRequest):
    key = _repo_key(req.repo_url)
    if key not in _INDEXED_REPOS:
        raise HTTPException(status_code=400, detail="Repo not indexed yet — call /index first")

    entry = _INDEXED_REPOS[key]
    result = run_agent(entry["collection"], entry["graph"], req.question)
    return result

@app.post("/query_compare")
def query_compare(req: QueryRequest):
    key = _repo_key(req.repo_url)
    if key not in _INDEXED_REPOS:
        raise HTTPException(status_code=400, detail="Repo not indexed yet — call /index first")

    entry = _INDEXED_REPOS[key]
    agentic_result = run_agent(entry["collection"], entry["graph"], req.question)
    baseline_result = run_baseline(entry["collection"], req.question)

    return {"agentic": agentic_result, "baseline": baseline_result}


@app.get("/health")
def health():
    return {"status": "ok"}