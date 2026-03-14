"""Web search utilities for Rafiqi.

This module centralizes web search so it can be reused by tools/agents.
"""

from __future__ import annotations

from typing import List

from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for up‑to‑date information using DuckDuckGo.

    Returns a human‑readable text summary of the top results.
    """
    query = (query or "").strip()
    if not query:
        return "No query provided."

    snippets: List[str] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            title = r.get("title") or ""
            href = r.get("href") or ""
            body = r.get("body") or ""
            snippets.append(f"{title}\n{href}\n{body}")

    if not snippets:
        return "No web results found."

    return "\n\n".join(snippets)

