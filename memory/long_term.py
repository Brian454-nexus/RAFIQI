from __future__ import annotations

"""Long-term vector memory backed by ChromaDB.

This module stores semantically searchable memories using a local
Chroma persistent database plus a SentenceTransformer embedder.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions

DEFAULT_DB_PATH = Path("data/chroma_db")
COLLECTION_NAME = "rafiqi_memory"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


DEFAULT_DB_PATH.mkdir(parents=True, exist_ok=True)

_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL_NAME
)

client = chromadb.PersistentClient(path=str(DEFAULT_DB_PATH))
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=_embedding_fn,
)


def save_memory(text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Save a piece of information to long-term memory and return its id."""
    timestamp = datetime.now()
    memory_id = f"mem_{timestamp.timestamp()}"

    meta = metadata.copy() if metadata else {}
    meta.setdefault("timestamp", timestamp.isoformat())

    collection.add(
        documents=[text],
        metadatas=[meta],
        ids=[memory_id],
    )
    print(f"Saved to memory ({memory_id}): {text[:80]}...")
    return memory_id


def recall(
    query: str,
    n_results: int = 3,
) -> List[Dict[str, Any]]:
    """Search memory for relevant information.

    Returns a list of dicts: {"text", "metadata", "score"}.
    """
    if not query:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=max(1, n_results),
    )

    documents = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []

    memories: List[Dict[str, Any]] = []
    for doc, meta, distance in zip(documents, metadatas, distances):
        memories.append(
            {
                "text": doc,
                "metadata": meta,
                "score": float(distance),
            }
        )

    return memories


def recall_texts(query: str, n_results: int = 3) -> List[str]:
    """Convenience wrapper returning just the memory texts."""
    return [m["text"] for m in recall(query, n_results=n_results)]