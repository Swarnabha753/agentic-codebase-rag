from app.ingestion.clone import clone_repo, discover_source_files, cleanup_repo
from app.ingestion.chunker import chunk_repo
from app.indexing.vectorstore import get_chroma_client, get_or_create_collection, index_chunks, query_chunks

path = clone_repo("https://github.com/pallets/flask.git", "tmp_repo")
files = discover_source_files(path)
chunks = chunk_repo(files)

client = get_chroma_client(".chroma")
collection = get_or_create_collection(client, "flask_demo")
index_chunks(collection, chunks)

print()
print("Query: how does session cookie signing work")
hits = query_chunks(collection, "how does session cookie signing work", top_k=3)
for h in hits:
    print(f"  {h['id']}  (distance={h['distance']:.3f})")

cleanup_repo(path)