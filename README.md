# Agentic Codebase RAG

**Live demo:** https://agentic-codebase-rag-sh9a-alpha.vercel.app/
**API:** https://agentic-codebase-rag.onrender.com

> Note: the backend runs on Render's free tier, which sleeps after
> inactivity. The first request after idle can take 30-60s to wake up —
> that's expected, not a bug.

Ask any GitHub repository a question in plain English and get an answer that
traces through **actual function calls across files** — not just top-k
vector similarity over disconnected text chunks.

> "Why does `find_best_app` fail when the module has multiple Flask
> instances?" gets answered by an agent that reads `find_best_app`, notices
> it calls `_called_with_wrong_args`, follows that call into the dependency
> graph, retrieves *that* function too, and only then writes an answer —
> citing exact files and line numbers for every claim.

A full multi-page product — a landing page, a "how it works" walkthrough,
and a live workspace where you index any public repo and compare
**agentic, graph-aware retrieval** against **plain baseline RAG** side by
side, with token/latency stats for both.

---

## Why this isn't "just another RAG chatbot"

Most RAG projects stop at: chunk text → embed → cosine similarity → stuff
into a prompt. That works for static documents. It breaks for code, because:

- **A function split across a fixed-size chunk boundary loses its meaning.**
  This project chunks on AST boundaries (function/class/method) using
  tree-sitter, so every chunk is a complete, semantically meaningful unit.
- **Code has explicit structure — call relationships — that plain
  similarity search ignores.** A question like "why does X fail" often
  needs the answer to trace through 2-3 function calls across different
  files. This project builds a real dependency graph (NetworkX) from
  parsed function calls and lets the retrieval agent *traverse* it,
  iteratively pulling in dependencies the initial vector search missed.
- **RAG systems fail silently, and most projects never check.** This one
  scores every answer for faithfulness (LLM-as-judge) *and* runs a
  deterministic check that every cited chunk ID actually exists in the
  retrieved context — catching hallucinated citations the LLM judge alone
  can miss. Low-scoring answers trigger one automatic retry with wider
  retrieval.
- **Provably better than baseline, not just claimed.** A dedicated compare
  mode runs the same question through both the agentic pipeline and a
  plain top-k baseline side by side — chunks used, LLM calls, tokens, and
  latency shown for each — so the value of graph expansion is
  demonstrable, not asserted.

---

## Product structure

| Page | Route | Purpose |
|---|---|---|
| Landing | `/` | Hero, feature highlights, CTA |
| How it works | `/how-it-works` | Full pipeline walkthrough, step by step |
| Workspace | `/app` | Index a repo, ask questions, toggle compare mode, view reasoning traces |

---

## Architecture

```
                    ┌─────────────────┐
   GitHub repo URL  │   1. INGESTION   │
   ───────────────▶ │  clone (shallow) │
                    │  discover files  │
                    └────────┬─────────┘
                             ▼
                    ┌─────────────────┐
                    │   2. CHUNKING    │   tree-sitter AST parse
                    │  functions/      │   → one chunk per function/
                    │  classes/methods │     class/method, with exact
                    └────────┬─────────┘     file + line-range metadata
                             ▼
              ┌──────────────┴──────────────┐
              ▼                              ▼
    ┌───────────────────┐        ┌──────────────────────┐
    │  3a. CALL GRAPH    │        │   3b. EMBEDDING       │
    │  extract calls per │        │  sentence-transformers│
    │  chunk → resolve   │        │  (local, free) → Chroma│
    │  to chunk IDs via  │        │  vector index          │
    │  same-file +       │        └───────────┬───────────┘
    │  name matching     │                    │
    │  → NetworkX DiGraph│                    │
    └─────────┬──────────┘                    │
              │                               │
              └───────────────┬───────────────┘
                               ▼
                    ┌─────────────────────┐
   User question     │  4. AGENT LOOP       │
   ───────────────▶  │  • vector-retrieve   │
                     │    top-k chunks      │
                     │  • check call graph  │
                     │    for missing deps  │
                     │  • pull in deps,     │
                     │    repeat (≤2 hops)  │
                     │  • generate cited    │
                     │    answer (GPT-4o-mini)│
                     └──────────┬───────────┘
                                ▼
                    ┌─────────────────────┐
                    │  5. EVAL LOOP         │
                    │  • LLM-judge          │
                    │    faithfulness score │
                    │  • deterministic      │
                    │    citation-ID check  │
                    │  • 1 retry if score   │
                    │    < 0.4              │
                    └──────────┬───────────┘
                                ▼
                     Cited answer + reasoning
                     trace + eval scores
                     (also: /query_compare runs
                     the same question through a
                     plain baseline RAG in parallel)
```

### Component breakdown

| Layer | Tech | What it does |
|---|---|---|
| Ingestion | `GitPython` | Shallow-clones any public repo, walks for `.py`/`.js`/`.ts`/`.tsx` files, skips `node_modules`/`.git`/build dirs |
| Chunking | `tree-sitter` + per-language grammars | Parses each file's AST, extracts function/class/method-level chunks (not fixed-size text splits) with exact line ranges |
| Call extraction | `tree-sitter` (per-chunk re-parse) | Walks each chunk's own AST subtree to find every function/method it calls |
| Call graph | `NetworkX` | Resolves raw call names → actual chunk IDs (same-file match first, then repo-wide name match capped at ≤3 candidates to avoid noise from common names like `get`/`__init__`) → directed graph |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Local, free, no API key needed — each chunk embedded as `{kind} {name} in {file} (lines X-Y)\n\n{source}` for better natural-language query matching |
| Vector store | `ChromaDB` (persistent, local) | Stores embeddings + metadata, supports `get()` by ID for graph-driven chunk fetches |
| Agent | Custom iterative Python loop | Retrieve → check graph for missing dependencies of retrieved chunks → fetch them → repeat (capped at 2 iterations, 8 new chunks/iteration to prevent expansion blowup) |
| Answer generation | OpenAI `gpt-4o-mini` | Synthesizes a cited answer from all gathered context |
| Eval — faithfulness | `gpt-4o-mini` as judge | Scores whether the answer's claims trace back to retrieved context |
| Eval — citation accuracy | Regex + set lookup (no LLM call) | Deterministically checks every `[chunk_id]` citation in the answer actually exists in retrieved context — catches hallucinated citations the LLM judge can miss |
| Baseline mode | Same LLM, no graph | Plain top-k RAG for direct side-by-side comparison |
| Retry logic | Explicit `retry_count` param | Exactly one retry with wider top-k if faithfulness < 0.4 — capped via an explicit counter (not inferred from mutable trace state, which caused an infinite-retry bug during development — see "Bugs found" below) |
| API | `FastAPI` | `/index`, `/query`, `/query_compare` (agentic vs. baseline side-by-side), `/health` |
| Frontend | `React Router` + `Vite` | Landing, how-it-works, and workspace pages; chat-style history, circular faithfulness/relevance score rings, citation pills, visual reasoning-trace timeline, baseline-vs-agentic comparison view |

---

## Baseline vs. agentic comparison

The `/query_compare` endpoint runs the same question through both:
- **Baseline** — plain top-k vector retrieval, no graph expansion (the "naive RAG" every tutorial stops at)
- **Agentic** — the full graph-aware iterative pipeline above

This exists specifically to make the project's value *demonstrable*, not just
claimed. In testing against real multi-hop questions (e.g. "why does X fail
when Y happens"), the agentic path retrieves the actual dependency chain the
baseline misses, producing a materially more complete answer — at the cost
of more LLM calls, tokens, and latency, which the UI shows transparently for
both sides.

---

## Bugs found and fixed during development

Documented here because being able to walk through a real debugging story is
more valuable in an interview than claiming nothing went wrong:

1. **Duplicate chunk IDs.** Nested functions with the same name (a common
   pattern — decorators define an inner function literally called
   `wrapper`) collided in Chroma because chunk IDs were `file::name` only.
   Fixed by including the line number in the ID.
2. **Call-graph noise.** Resolving every call to *any* repo-wide function
   with that name (e.g. `get`, `__init__`) created thousands of nonsense
   edges, causing the agent to pull in irrelevant chunks from unrelated
   files during graph expansion. Fixed by only trusting repo-wide name
   matches when there are ≤3 candidates, and capping how many chunks one
   expansion iteration can add.
3. **Infinite retry loop.** The retry-on-low-faithfulness logic inferred
   "have we already retried?" from scanning trace contents — but each
   recursive call built a fresh trace, so the check never saw prior
   attempts and retried repeatedly. Fixed by passing an explicit
   `retry_count` parameter instead of inferring state from mutable data.
4. **Windows `PermissionError` on cleanup.** `shutil.rmtree` failed deleting
   cloned repos because git marks some `.git/objects/pack` files read-only,
   which Windows' default deletion refuses to remove (not an issue on
   Linux/Mac). Fixed with a custom `onexc` handler that clears the
   read-only bit and retries.
5. **LLM-as-judge noise.** Faithfulness scoring sometimes rated clearly
   correct, well-cited answers as `0.0`. Addressed by adding the
   deterministic citation-accuracy check as a second, non-LLM signal rather
   than trusting the judge alone.
6. **`openai`/`httpx` version mismatch on deployment.** A fresh install on
   Render resolved an `openai` version incompatible with the installed
   `httpx` (a breaking API change in `httpx`'s `Client.__init__`). Fixed by
   pinning both `openai==1.54.4` and `httpx==0.27.2` explicitly instead of
   leaving them unpinned.

---

## What I'd improve with more time

- **Call resolution is name-based, not a full type-checker.** It handles
  the common case well (same-file calls, unambiguous cross-file names) but
  can't resolve calls behind runtime polymorphism. A production version
  would integrate per-language static analysis (e.g. `jedi` for Python).
- **In-memory index storage** — indexed repos are lost on server restart.
  A production version would persist the repo→collection mapping (e.g.
  SQLite) alongside Chroma's existing on-disk persistence.
- **No repo-size cap yet** — a very large monorepo would take a long time
  to embed synchronously. A production version would embed asynchronously
  with a job queue and progress polling.
- **Free-tier hosting trade-offs** — Render's free tier sleeps after
  inactivity and has tight memory for the local embedding model. A
  production deployment would use a paid tier or swap to an API-based
  embedding call to cut memory footprint.

---

## Setup

### Backend
```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:
```
OPENAI_API_KEY=your-key-here
```

Run:
```bash
python -m uvicorn app.api.main:app --port 8000
```
(without `--reload` — the reloader restarts the process when `/index`
writes temp files, which wipes the in-memory index)

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, index a public repo (e.g.
`https://github.com/pallets/flask.git`), then ask a question.

**Windows note:** this project uses `tree-sitter-python`,
`tree-sitter-javascript`, `tree-sitter-typescript` directly instead of the
unmaintained `tree-sitter-languages` package, which lacks Python 3.12+
wheels.

---

## Deployment

- **Backend** deployed on Render (free tier) — root directory `backend`,
  build command `pip install -r requirements.txt`, start command
  `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`.
- **Frontend** deployed on Vercel — root directory `frontend`, Vite preset
  auto-detected, `VITE_API_BASE` environment variable pointed at the Render
  backend URL.
- CORS on the backend is locked to the deployed frontend origin rather than
  left wide open, once the real Vercel URL was known.

---

## Project structure
```
codebase-rag/
├── backend/
│   ├── app/
│   │   ├── ingestion/      # clone.py, chunker.py, calls.py, parsers.py
│   │   ├── indexing/       # graph.py, vectorstore.py
│   │   ├── agent/          # rag_agent.py (run_agent + run_baseline)
│   │   ├── eval/           # faithfulness.py, citation_check.py
│   │   └── api/            # main.py (FastAPI app)
│   └── requirements.txt
└── frontend/
    └── src/
        ├── pages/          # Landing.jsx, HowItWorks.jsx, Workspace.jsx
        ├── components/     # Navbar.jsx
        ├── App.jsx         # router shell
        └── App.css
```

## License
MIT