"""
The core differentiator: instead of plain top-k retrieval, this agent
iteratively expands its context using the call graph before answering.

Loop:
  1. Vector-retrieve top-k chunks for the user's question.
  2. Check the call graph: do any retrieved chunks call functions that
     weren't retrieved? If so, pull those in too (up to max_hops).
  3. Repeat up to max_iterations, then generate a cited answer from
     everything gathered.

This is deliberately a plain Python loop, not a black-box abstraction —
being able to explain exactly what happens at each step is what makes
this defensible in an interview.
"""
import os
import time
from app.eval.citation_check import check_citations

from app.eval.faithfulness import score_faithfulness

from dotenv import load_dotenv
from openai import OpenAI

from app.indexing.graph import get_dependencies
from app.indexing.vectorstore import query_chunks

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def run_agent(collection, graph, question: str, top_k: int = 5, max_hops: int = 1, max_iterations: int = 2, retry_count: int = 0):
    _start_time = time.time()
    _llm_calls = 0
    _tokens_used = 0
    trace = []

    # Step 1: initial vector retrieval
    hits = query_chunks(collection, question, top_k=top_k)
    gathered = {h["id"]: h for h in hits}
    trace.append({
        "step": "initial_retrieval",
        "query": question,
        "found": [h["id"] for h in hits],
    })

    # Step 2: expand via call graph, iteratively
    for i in range(max_iterations):
        new_ids = set()
        for chunk_id in list(gathered.keys()):
            deps = get_dependencies(graph, chunk_id, max_hops=max_hops)
            for dep_id in deps:
                if dep_id not in gathered:
                    new_ids.add(dep_id)

        if not new_ids:
            break  # nothing new to add, stop expanding early

        new_ids = set(list(new_ids)[:8])

        # fetch full documents for the newly discovered dependency chunks
        fetched = collection.get(ids=list(new_ids))
        for j, cid in enumerate(fetched["ids"]):
            gathered[cid] = {
                "id": cid,
                "document": fetched["documents"][j],
                "metadata": fetched["metadatas"][j],
            }

        trace.append({
            "step": f"graph_expansion_iteration_{i + 1}",
            "added": list(new_ids),
        })

    # Step 3: generate a cited answer from everything gathered
    context_blocks = []
    for chunk_id, h in gathered.items():
        meta = h["metadata"]
        context_blocks.append(
            f"[{chunk_id}] ({meta['file_path']} lines {meta['start_line']}-{meta['end_line']})\n{h['document']}"
        )
    context_text = "\n\n---\n\n".join(context_blocks)

    prompt = f"""You are answering a question about a codebase using the retrieved code chunks below.
Cite the exact chunk id (e.g. [path/to/file.py::FunctionName:line]) for every claim you make.
If the retrieved chunks don't fully answer the question, say what's missing.

Question: {question}

Retrieved code chunks:
{context_text}

Answer:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    answer = response.choices[0].message.content
    _llm_calls += 1
    _tokens_used += response.usage.total_tokens

    
    # Step 4: evaluate faithfulness; retry once with wider retrieval if it scores low
    eval_result = score_faithfulness(question, answer, context_text)
    _llm_calls += 1
    trace.append({"step": "eval", **eval_result})

    citation_result = check_citations(answer, list(gathered.keys()))
    trace.append({"step": "citation_check", **citation_result})

    faithfulness = eval_result.get("faithfulness")
    if faithfulness is not None and faithfulness < 0.4 and retry_count < 1:
        trace.append({"step": "retry_triggered", "reason": "low faithfulness score, widening retrieval"})
        retried = run_agent(collection, graph, question, top_k=top_k + 5, max_hops=max_hops,
                             max_iterations=max_iterations, retry_count=retry_count + 1)
        retried["trace"] = trace + retried["trace"]
        return retried

    return {
        "answer": answer,
        "trace": trace,
        "chunks_used": list(gathered.keys()),
        "eval": eval_result,
        "citation_check": citation_result,
        "stats": {
            "llm_calls": _llm_calls,
            "tokens_used": _tokens_used,
            "latency_seconds": round(time.time() - _start_time, 2),
        },
    }

def run_baseline(collection, question: str, top_k: int = 5):
    """Plain top-k vector RAG, no call-graph expansion — the naive-RAG baseline."""
    start = time.time()

    hits = query_chunks(collection, question, top_k=top_k)
    context_blocks = []
    for h in hits:
        meta = h["metadata"]
        context_blocks.append(
            f"[{h['id']}] ({meta['file_path']} lines {meta['start_line']}-{meta['end_line']})\n{h['document']}"
        )
    context_text = "\n\n---\n\n".join(context_blocks)

    prompt = f"""Answer the question using only the retrieved code chunks below.
Cite the exact chunk id for every claim you make.

Question: {question}

Retrieved code chunks:
{context_text}

Answer:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    elapsed = time.time() - start

    return {
        "answer": response.choices[0].message.content,
        "chunks_used": [h["id"] for h in hits],
        "stats": {
            "llm_calls": 1,
            "tokens_used": response.usage.total_tokens,
            "latency_seconds": round(elapsed, 2),
        },
    }