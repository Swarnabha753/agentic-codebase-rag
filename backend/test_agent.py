from app.ingestion.clone import clone_repo, discover_source_files, cleanup_repo
from app.ingestion.chunker import chunk_repo
from app.ingestion.calls import extract_calls_from_source
from app.indexing.graph import build_call_graph
from app.indexing.vectorstore import get_chroma_client, get_or_create_collection, index_chunks
from app.agent.rag_agent import run_agent
import shutil, os

if os.path.exists("tmp_repo"):
    shutil.rmtree("tmp_repo")

path = clone_repo("https://github.com/pallets/flask.git", "tmp_repo")
files = discover_source_files(path)
chunks = chunk_repo(files)
for c in chunks:
    c.calls = extract_calls_from_source(c.source, c.language)

graph = build_call_graph(chunks)

client = get_chroma_client(".chroma")
collection = get_or_create_collection(client, "flask_demo")
index_chunks(collection, chunks)

question = "How does Flask verify a session cookie hasn't been tampered with?"
result = run_agent(collection, graph, question)

print("\n=== ANSWER ===")
print(result["answer"])
print("\n=== TRACE ===")
for step in result["trace"]:
    print(step)

cleanup_repo(path)