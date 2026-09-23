# Agentic Codebase RAG

Ask questions about any GitHub repo and get answers that trace through
function calls across files — not just top-k vector similarity.

## Status: Week 1, Day 1-2 complete

Built and tested so far (all verified against the real `pallets/flask` repo):

- `app/ingestion/clone.py` — shallow-clones a GitHub repo, walks it for
  supported source files (Python, JS/TS), skips `node_modules`/`.git`/etc.
- `app/ingestion/chunker.py` — parses each file with tree-sitter and extracts
  **function/class/method-level chunks** (not naive fixed-size text splits),
  each with file path, line range, and source.
- `app/ingestion/calls.py` — parses each chunk's own body to extract the
  names of functions/methods it calls. This is the raw signal that Week 2's
  call-graph builder will resolve into real cross-file edges.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Important:** `tree-sitter` must stay below version `0.22` — newer versions
changed the `Language()` constructor signature and break `tree-sitter-languages`
1.10.2. This is pinned in `requirements.txt`; don't `pip install -U` blindly.

## Try it

```python
from app.ingestion.clone import clone_repo, discover_source_files, cleanup_repo
from app.ingestion.chunker import chunk_repo
from app.ingestion.calls import extract_calls_from_source

path = clone_repo("https://github.com/pallets/flask.git", "tmp_repo")
files = discover_source_files(path)
chunks = chunk_repo(files)

for c in chunks:
    c.calls = extract_calls_from_source(c.source, c.language)

print(chunks[0].id, chunks[0].calls)

cleanup_repo(path)  # tmp_repo/ is gitignored — clean up after yourself
```

## Roadmap

- [ ] Resolve raw call names -> actual chunk IDs across files -> NetworkX call graph
- [ ] Embedding pipeline (OpenAI `text-embedding-3-small`) + Chroma vector index
- [ ] LangGraph agent: iterative graph-aware retrieval (the core differentiator)
- [ ] Lightweight eval loop (faithfulness/relevance scoring, retry on low score)
- [ ] React frontend: chat + file-tree viewer with highlighted citations
- [ ] Deploy (Vercel + Render/Railway)

See project chat history for the full week-by-week plan and interview
talking points for each component.
