"""Search Hacker News via the public Algolia API (no auth)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from langchain.tools import tool

from tools.json_result import json_result


@tool
def search_hackernews(query: str, max_results: int = 20) -> str:
    """Search recent Hacker News stories (public Algolia API, no credentials).

    For daily zeitgeist scans use several niche queries with max_results ~20.

    Args:
        query: Search keywords from focus.md niches.
        max_results: Max hits to return (default 20, capped at 30).
    """
    limit = min(max(max_results, 1), 30)
    params = urllib.parse.urlencode(
        {
            "query": query,
            "tags": "story",
            "hitsPerPage": str(limit),
        }
    )
    url = f"https://hn.algolia.com/api/v1/search_by_date?{params}"

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            if response.status != 200:
                return json_result({"error": f"Hacker News search failed ({response.status})"})
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return json_result({"error": f"Hacker News search failed ({exc.code})"})
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return json_result({"error": str(exc)})

    hits = []
    for hit in (body.get("hits") or [])[:limit]:
        object_id = hit.get("objectID")
        hn_url = f"https://news.ycombinator.com/item?id={object_id}"
        story_text = hit.get("story_text") or ""
        hits.append(
            {
                "id": object_id,
                "title": hit.get("title"),
                "url": hit.get("url") or hn_url,
                "hnUrl": hn_url,
                "author": hit.get("author"),
                "points": hit.get("points"),
                "comments": hit.get("num_comments"),
                "createdAt": hit.get("created_at"),
                "snippet": story_text[:240] if story_text else None,
            }
        )

    return json_result({"query": query, "count": len(hits), "hits": hits})
