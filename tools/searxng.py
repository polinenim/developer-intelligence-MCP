"""Simple SearXNG search helper.

Uses the SEARXNG_URL environment variable to call a SearXNG instance's
HTTP API and returns a list of search result dicts with `title`, `url`,
and `snippet` when available.
"""
from __future__ import annotations

import os
from typing import List, Dict

import requests


def _searx_base() -> str:
    url = os.environ.get("SEARXNG_URL")
    if not url:
        raise RuntimeError("SEARXNG_URL is not configured in environment")
    return url.rstrip("/")


def search_web(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """Search SearXNG for `query` and return a list of results.

    Each result is a dict with keys: `title`, `url`, `snippet` (may be
    empty string if not present).
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty")

    base = _searx_base()
    api = f"{base}/search"
    params = {"q": query, "format": "json", "categories": "general"}
    resp = requests.get(api, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("results", [])[:limit]:
        title = item.get("title") or ""
        url = item.get("url") or item.get("link") or ""
        snippet = item.get("content") or item.get("snippet") or ""
        results.append({"title": title, "url": url, "snippet": snippet})

    return results
