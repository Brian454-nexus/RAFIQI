"""Document ingestion for Rafiqi's RAG pipeline.

This module is responsible only for loading and chunking source documents
and writing them into the shared Chroma vector store. Querying is handled
by `rag.retriever`.
"""

from __future__ import annotations

import os

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)

from rag.retriever import get_vectorstore

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)


def load_document(file_path: str) -> None:
    """Load and index a document into Rafiqi's shared vector store."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
    elif ext == ".txt":
        loader = TextLoader(file_path)
    elif ext == ".docx":
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    docs = loader.load()
    chunks = splitter.split_documents(docs)

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)
    print(f"Loaded {len(chunks)} chunks from {file_path}")
