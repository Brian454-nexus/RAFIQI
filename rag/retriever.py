"""RAG retriever utilities built on top of Chroma.

This module centralizes vector store and retriever creation so that
ingestion and querying use the exact same configuration.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

DB_DIR = Path("data/chroma_db")
COLLECTION_NAME = "documents"
EMBED_MODEL_NAME = "nomic-embed-text"


DB_DIR.mkdir(parents=True, exist_ok=True)

_embeddings = OllamaEmbeddings(model=EMBED_MODEL_NAME)


def get_vectorstore() -> Chroma:
    """Return a Chroma vector store pointing at the shared documents collection."""
    return Chroma(
        persist_directory=str(DB_DIR),
        collection_name=COLLECTION_NAME,
        embedding_function=_embeddings,
    )


def get_retriever(k: int = 3):
    """Return a LangChain retriever wrapping the shared vector store."""
    return get_vectorstore().as_retriever(search_kwargs={"k": k})


def retrieve_documents(question: str, k: int = 3) -> List[Document]:
    """Return the top-k relevant documents for a given question."""
    if not question:
        return []
    retriever = get_retriever(k=k)
    return retriever.get_relevant_documents(question)


def retrieve_context(question: str, k: int = 3) -> str:
    """Convenience helper returning concatenated context text for a question."""
    docs = retrieve_documents(question, k=k)
    return "\n\n".join(d.page_content for d in docs)
