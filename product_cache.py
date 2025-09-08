# product_cache.py
"""
SQLite-based cache for product offers.
- Saves search query results (title, source, price, link)
- Each query is cached with timestamp
- Allows retrieval by query keyword
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

DB_PATH = Path(__file__).resolve().parent / "product_cache.db"


def init_db():
    """Initialize the SQLite database (create table if not exists)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS product_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            offers_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def save_offers(query: str, offers: List[Dict[str, Any]]):
    """Save offers for a query into the cache."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO product_cache (query, offers_json, created_at) VALUES (?, ?, ?)",
        (query.strip().lower(), json.dumps(offers, ensure_ascii=False), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_offers(query: str, max_age_minutes: int = 60) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve cached offers for a query if not expired.
    max_age_minutes: how long cache is valid (default 1 hour).
    Returns list of offers or None if not found/expired.
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT offers_json, created_at FROM product_cache WHERE query = ? ORDER BY id DESC LIMIT 1",
        (query.strip().lower(),),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    offers_json, created_at = row
    try:
        created_dt = datetime.fromisoformat(created_at)
    except Exception:
        return None

    if datetime.utcnow() - created_dt > timedelta(minutes=max_age_minutes):
        return None  # cache expired

    try:
        return json.loads(offers_json)
    except Exception:
        return None


def clear_cache():
    """Clear all cache entries."""
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM product_cache")
        conn.commit()
        conn.close()


if __name__ == "__main__":
    # Quick test
    init_db()
    sample_query = "iPhone 14"
    sample_offers = [
        {"title": "iPhone 14 128GB", "source": "Amazon", "price": "₹68,999", "link": "https://amazon.in/"},
        {"title": "iPhone 14 128GB", "source": "Flipkart", "price": "₹67,499", "link": "https://flipkart.com/"},
    ]

    save_offers(sample_query, sample_offers)
    cached = get_offers(sample_query, max_age_minutes=120)
    print("Cached offers:", cached)
