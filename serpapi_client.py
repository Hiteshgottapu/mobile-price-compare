# serpapi_client.py
"""
Small SerpApi Google Shopping wrapper for mobile-price-compare.

Features:
- Reads API key from SERPAPI_KEY environment variable (do NOT hardcode keys).
- Simple function `search_shopping(query, country="in", no_cache=False)` that returns a
  list of offers: dicts with at least `title`, `source`, `price`, `link`, `raw`.
- Optional integration with product_cache.py if that module exists: it will save/read
  cached search results keyed by `query::gl=<country>`.
- Handles HTTP errors and returns an empty list on failure (caller should inspect/log).

Usage:
    from serpapi_client import search_shopping
    offers = search_shopping("iPhone 14 128GB", country="in", no_cache=False)
"""

import os
import time
import json
from typing import List, Dict, Any, Optional
import requests

SERPAPI_BASE = "https://serpapi.com/search"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")  # MUST be set in environment
DEFAULT_TIMEOUT = 30

# Try to import optional cache module (product_cache.py) if present.
try:
    import product_cache  # type: ignore
    HAVE_CACHE = True
except Exception:
    HAVE_CACHE = False


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    """Return cached payload (dict) or None. Uses product_cache.get_offers if available."""
    if not HAVE_CACHE:
        return None
    try:
        # product_cache.get_offers returns list-of-offers or None (we stored list)
        val = product_cache.get_offers(key)
        if val:
            return {"offers": val, "cached_at": True}
    except Exception:
        # ignore cache errors
        return None
    return None


def _cache_set(key: str, payload: Dict[str, Any]) -> None:
    """Save payload into cache using product_cache.save_offers (stores list under key)."""
    if not HAVE_CACHE:
        return
    try:
        offers = payload.get("offers") or []
        # save_offers expects (query, offers_list)
        product_cache.save_offers(key, offers)
    except Exception:
        pass


def _parse_serpapi_shopping(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse SerpApi response and extract a normalized list of offers.
    Each offer: {title, source, price, link, raw}
    """
    offers = []
    # SerpApi commonly returns results under "shopping_results"
    raw_list = data.get("shopping_results") or data.get("shopping_offers") or data.get("shopping_results", [])
    # Some variants might put offers under "inline_shopping_results" etc. Be tolerant:
    if not raw_list and isinstance(data, dict):
        for k in ("shopping_results", "shopping_offers", "inline_shopping_results", "product_results"):
            if data.get(k):
                raw_list = data.get(k)
                break

    for it in (raw_list or []):
        # tolerant field extraction
        title = it.get("title") or it.get("name") or it.get("product_title") or ""
        source = it.get("source") or it.get("merchant") or it.get("store") or ""
        # price may appear as "price" (string), or "extracted_price", or nested dicts
        price = it.get("price") or it.get("extracted_price") or it.get("price_string") or ""
        link = it.get("link") or it.get("product_link") or it.get("click") or ""
        offers.append({
            "title": title,
            "source": source,
            "price": price,
            "link": link,
            "raw": it
        })
    return offers


def search_shopping(query: str, country: str = "in", no_cache: bool = False) -> List[Dict[str, Any]]:
    """
    Query SerpApi Google Shopping for `query` and return a list of offers.
    - query: search query string (e.g., "iPhone 14 128GB")
    - country: two-letter country code used in SerpApi 'gl' parameter (default 'in')
    - no_cache: when True, forces live fetch (SerpApi `no_cache=true`) and doesn't read cache.

    Returns: list of offers (each a dict). On error returns [].
    """
    if not query or not isinstance(query, str):
        return []

    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY environment variable not set. Set it before calling search_shopping().")

    cache_key = f"{query}::gl={country}"

    # Try cache if available and allowed
    if not no_cache:
        cached = _cache_get(cache_key)
        if cached and isinstance(cached.get("offers"), list):
            return cached["offers"]

    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": country,
        "hl": "en",
        "api_key": SERPAPI_KEY,
    }
    if no_cache:
        params["no_cache"] = "true"

    try:
        resp = requests.get(SERPAPI_BASE, params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        offers = _parse_serpapi_shopping(data)
        # Save into cache (best-effort) when we got results
        if offers:
            _cache_set(cache_key, {"offers": offers, "fetched_at": int(time.time())})
        return offers
    except requests.HTTPError as he:
        # If rate-limited or unauthorized, surface but return empty list
        # Caller can inspect logs/exceptions if needed
        # You can add logging here instead of print
        print(f"[serpapi_client] HTTP error for query={query}: {he}")
        try:
            # try to parse any error JSON for debugging
            print(resp.text[:1000])
        except Exception:
            pass
        return []
    except Exception as e:
        print(f"[serpapi_client] Unexpected error for query={query}: {e}")
        return []


# CLI quick test (useful during development)
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test SerpApi shopping search")
    parser.add_argument("query", nargs="+", help="Search query (e.g. 'iPhone 14 128GB')")
    parser.add_argument("--country", default="in", help="Country code (gl param), default 'in'")
    parser.add_argument("--no-cache", action="store_true", help="Force live fetch (no cache)")
    args = parser.parse_args()
    q = " ".join(args.query)
    res = search_shopping(q, country=args.country, no_cache=args.no_cache)
    print(json.dumps(res[:50], indent=2, ensure_ascii=False))
