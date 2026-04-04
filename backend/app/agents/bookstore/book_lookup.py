import logging
import re
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]")


def _has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text))


async def verify_book_title(title: str, author: str | None = None) -> dict | None:
    """Search OpenLibrary to verify/correct a book title.

    Returns {"title": corrected_title, "author": author_name} or None if not found.
    Prefers Russian title when the input is in Russian.
    """
    query = title
    if author:
        query += f" {author}"

    url = f"https://openlibrary.org/search.json?q={quote(query)}&limit=5&language=rus"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"OpenLibrary lookup failed for '{query}': {e}")
        return None

    docs = data.get("docs", [])
    if not docs:
        return None

    input_is_cyrillic = _has_cyrillic(title)

    # If input is Russian, try to find a result with a Cyrillic title
    if input_is_cyrillic:
        for doc in docs:
            doc_title = doc.get("title", "")
            if _has_cyrillic(doc_title):
                return {
                    "title": doc_title,
                    "author": doc.get("author_name", [None])[0],
                }
        # No Cyrillic title found — keep original title, just grab author
        return {
            "title": title,
            "author": docs[0].get("author_name", [None])[0],
        }

    best = docs[0]
    return {
        "title": best.get("title", title),
        "author": best.get("author_name", [None])[0],
    }
