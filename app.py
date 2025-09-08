# app.py
"""
Minimal Streamlit app for Mobile Price Compare using SerpApi .
Self-contained: includes a tiny SerpApi client and a simple SQLite cache.
Dependencies:
    pip install streamlit requests pandas rapidfuzz
(rapidfuzz is optional — if missing, the app will fall back to a simple exact/substring clusterer)

Usage:
    1. Set environment variable SERPAPI_KEY to your SerpApi API key.
       On Windows PowerShell:
           setx SERPAPI_KEY "your_key_here"
       On macOS / Linux:
           export SERPAPI_KEY="your_key_here"
    2. Run:
           streamlit run app.py
"""

import os
import time
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import pandas as pd
import streamlit as st

# Optional fuzzy library: rapidfuzz
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except Exception:
    HAS_RAPIDFUZZ = False

# ---------- Config ----------
DB_PATH = Path(__file__).parent / "cache.sqlite"
SERPAPI_URL = "https://serpapi.com/search"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")  # must be set in environment
CACHE_TTL = 60 * 60  # 1 hour cache default

st.set_page_config(page_title="Mobile Price Compare", layout="wide")
st.title("📱 Mobile Price Compare — SerpApi")
# ---------- Custom HTML & CSS ----------
# Enhanced UI: Modern, clean, with subtle animations and branding
# Enhanced UI: Modern, clean, with subtle animations and branding
st.markdown(
    """
    <style>
    body {
        background: linear-gradient(120deg, #f8fafc 0%, #e0e7ef 100%);
        font-family: 'Segoe UI', Arial, sans-serif;
    }
    .main .block-container {
        background: #fff;
        border-radius: 22px;
        box-shadow: 0 8px 36px rgba(30,64,175,0.13);
        padding: 2.7rem 3.2rem;
        margin-top: 2.2rem;
        animation: fadeIn 1.1s;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(30px);}
        to { opacity: 1; transform: translateY(0);}
    }
    h1, h2, h3, h4 {
        color: #1a365d;
        font-family: 'Segoe UI', Arial, sans-serif;
        letter-spacing: 0.5px;
    }
    .stButton > button {
        background: linear-gradient(90deg, #2563eb 0%, #1e40af 100%);
        color: #fff;
        border: none;
        border-radius: 14px;
        padding: 0.8rem 2.4rem;
        font-size: 1.22rem;
        font-weight: 700;
        box-shadow: 0 2px 10px rgba(30,64,175,0.10);
        transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
        cursor: pointer;
        letter-spacing: 0.5px;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #1e40af 0%, #2563eb 100%);
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 4px 16px rgba(30,64,175,0.13);
    }
    .stDataFrame, .stTable {
        background: #f1f5fa;
        border-radius: 14px;
        padding: 0.9rem;
        font-size: 1.09rem;
        border: 1.5px solid #e0e7ef;
        margin-bottom: 0.7rem;
        box-shadow: 0 1px 6px rgba(30,64,175,0.06);
    }
    .stExpanderHeader {
        font-weight: 700;
        color: #2563eb;
        font-size: 1.13rem;
        letter-spacing: 0.2px;
    }
    .stMarkdown a {
        color: #1e40af;
        text-decoration: underline;
        font-weight: 600;
        transition: color 0.15s;
    }
    .stMarkdown a:hover {
        color: #2563eb;
        text-shadow: 0 2px 8px #e0e7ef;
    }
    .stTextInput > div > input {
        border-radius: 12px;
        border: 1.7px solid #2563eb;
        padding: 0.6rem 1.2rem;
        font-size: 1.13rem;
        background: #f8fafc;
        transition: border 0.2s, box-shadow 0.2s;
        box-shadow: 0 1px 4px rgba(30,64,175,0.06);
    }
    .stTextInput > div > input:focus {
        border: 2px solid #1e40af;
        outline: none;
        box-shadow: 0 2px 8px #e0e7ef;
    }
    .stCheckbox > label {
        font-size: 1.09rem;
        color: #1a365d;
        font-weight: 500;
    }
    .stInfo, .stSuccess, .stWarning, .stError {
        border-radius: 12px;
        font-size: 1.08rem;
        padding: 0.8rem 1.2rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 1px 6px rgba(30,64,175,0.06);
    }
    /* Custom badge for branding */
    .mpc-badge {
        display: inline-block;
        background: linear-gradient(90deg, #2563eb 0%, #1e40af 100%);
        color: #fff;
        font-size: 1.02rem;
        font-weight: 600;
        border-radius: 10px;
        padding: 0.28rem 1.05rem;
        margin-bottom: 0.8rem;
        letter-spacing: 0.6px;
        box-shadow: 0 2px 8px rgba(30,64,175,0.08);
        vertical-align: middle;
        animation: badgeFadeIn 1.2s;
    }
    @keyframes badgeFadeIn {
        from { opacity: 0; transform: scale(0.9);}
        to { opacity: 1; transform: scale(1);}
    }
    /* Add a subtle hover effect to expanders */
    .stExpander {
        transition: box-shadow 0.2s;
    }
    .stExpander:hover {
        box-shadow: 0 2px 12px rgba(30,64,175,0.10);
    }
    /* Add a floating effect to the search bar */
    .stTextInput {
        box-shadow: 0 2px 10px rgba(30,64,175,0.07);
        border-radius: 14px;
        margin-bottom: 0.5rem;
    }
    /* Responsive tweaks */
    @media (max-width: 900px) {
        .main .block-container {
            padding: 1.2rem 0.5rem;
        }
        .stDataFrame, .stTable {
            font-size: 0.98rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)
# Add a subtle badge under the title for branding
st.markdown('<div class="mpc-badge">Powered by SerpApi & Google Shopping</div>', unsafe_allow_html=True)

# ---------- Simple SQLite cache ----------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS search_cache (
            query TEXT PRIMARY KEY,
            payload TEXT,
            fetched_at INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS product_cache (
            url TEXT PRIMARY KEY,
            payload TEXT,
            fetched_at INTEGER
        )
        """
    )
    conn.commit()
    conn.close()

def get_search_cache(query: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT fetched_at, payload FROM search_cache WHERE query = ?", (query,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    fetched_at, payload = row
    if int(time.time()) - int(fetched_at) > CACHE_TTL:
        return None
    try:
        return json.loads(payload)
    except Exception:
        return None

def save_search_cache(query: str, payload: Dict[str, Any]):
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "REPLACE INTO search_cache (query, payload, fetched_at) VALUES (?, ?, ?)",
        (query, json.dumps(payload, ensure_ascii=False), int(time.time())),
    )
    conn.commit()
    conn.close()

# ---------- SerpApi wrapper ----------
def search_serpapi(query: str, country: str = "in", no_cache: bool = False) -> List[Dict[str, Any]]:
    """
    Query SerpApi Google Shopping engine and return a list of offers (dicts).
    Each offer will contain at least: title, source, price, link
    """
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY environment variable not set. Set it and restart the app.")

    # Try cache first (unless no_cache requested)
    cache_key = f"{query}::gl={country}"
    if not no_cache:
        cached = get_search_cache(cache_key)
        if cached:
            return cached.get("offers", [])

    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": country,
        "hl": "en",
        "api_key": SERPAPI_KEY,
    }
    if no_cache:
        params["no_cache"] = "true"

    r = requests.get(SERPAPI_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    # SerpApi returns shopping results commonly under 'shopping_results'
    offers_raw = data.get("shopping_results") or data.get("shopping_results", []) or []
    offers = []
    for it in offers_raw:
        # different fields may exist; be tolerant
        title = it.get("title") or it.get("name") or it.get("product_title") or ""
        source = it.get("source") or it.get("merchant") or it.get("store") or ""
        # price sometimes as dict 'price' or 'extracted_price' or string 'price'
        price = it.get("price") or it.get("extracted_price") or it.get("price_string") or it.get("displayed_price") or ""
        link = it.get("link") or it.get("product_link") or it.get("click") or ""
        offers.append({
            "title": title,
            "source": source,
            "price": price,
            "link": link,
            "raw": it
        })

    # Save to cache
    save_search_cache(cache_key, {"offers": offers, "meta": {"serpapi_status": data.get("status")}})
    return offers

# ---------- Normalization & aggregation ----------
def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    # remove punctuation except + and space & numbers
    keep = []
    for ch in s:
        if ch.isalnum() or ch.isspace() or ch == "+":
            keep.append(ch)
        else:
            keep.append(" ")
    cleaned = "".join(keep)
    cleaned = " ".join(cleaned.split())
    return cleaned

def price_to_float(p) -> Optional[float]:
    if p is None:
        return None
    s = str(p)
    # try to extract digits and decimals
    import re
    m = re.search(r"[\d\.,]+", s)
    if not m:
        return None
    num = m.group(0).replace(",", "")
    try:
        return float(num)
    except Exception:
        return None

def cluster_offers(offers: List[Dict[str, Any]], threshold: int = 85) -> List[Dict[str, Any]]:
    """
    Group similar titles into clusters and compute min price per cluster.
    If rapidfuzz is available, use fuzzy token sort ratio, else simple normalized substring grouping.
    Returns list of clusters with keys: canonical, items[], min_price, min_source, min_link
    """
    clusters: List[Dict[str, Any]] = []
    for off in offers:
        title = off.get("title") or ""
        norm = normalize_text(title)
        placed = False
        if HAS_RAPIDFUZZ:
            # compare against cluster canonical_norm
            for c in clusters:
                score = fuzz.token_sort_ratio(norm, c["canonical_norm"])
                if score >= threshold:
                    c["items"].append(off)
                    placed = True
                    break
        else:
            # fallback: substring or equality on normalized strings
            for c in clusters:
                if norm in c["canonical_norm"] or c["canonical_norm"] in norm:
                    c["items"].append(off)
                    placed = True
                    break

        if not placed:
            clusters.append({"canonical": title, "canonical_norm": norm, "items": [off]})

    # compute min price per cluster
    out = []
    for c in clusters:
        min_p = None
        min_src = None
        min_link = None
        rows = []
        for it in c["items"]:
            pr = price_to_float(it.get("price"))
            rows.append({"title": it.get("title"), "source": it.get("source"), "price": pr, "link": it.get("link")})
            if pr is not None and (min_p is None or pr < min_p):
                min_p = pr
                min_src = it.get("source")
                min_link = it.get("link")
        out.append({
            "canonical": c["canonical"],
            "canonical_norm": c["canonical_norm"],
            "min_price": min_p,
            "min_source": min_src,
            "min_link": min_link,
            "items": rows
        })
    # sort with available prices first
    out.sort(key=lambda x: (x["min_price"] is None, x["min_price"] if x["min_price"] is not None else float("inf")))
    return out

# ---------- Streamlit UI ----------

st.markdown("Enter a mobile model below and click **Search**. Results come from Google Shopping via SerpApi.")
col1, col2, col3 = st.columns([6, 2, 2])

with col1:
    query = st.text_input("Mobile model (e.g., iPhone 14 128GB)")

with col2:
    live = st.checkbox("Live (no-cache)", value=False)

with col3:
    search_btn = st.button("Search")

if not SERPAPI_KEY:
    pass

if search_btn and query:
    st.info(f"Searching for: **{query}** (live={live})")
    try:
        offers = []
        if SERPAPI_KEY:
            offers = search_serpapi(query, country="in", no_cache=live)
        else:
            st.error("Missing SERPAPI_KEY — cannot perform live search.")
            offers = []

        if not offers:
            st.warning("No offers returned by SerpApi for this query.")
        else:
            clusters = cluster_offers(offers)
            # show top (best) cluster and lowest price
            top = clusters[0]
            st.markdown("### 🏆 Best match & lowest price (from clusters)")
            if top.get("min_price") is not None:
                st.success(f"Cheapest: **₹{top['min_price']:.2f}** on **{top.get('min_source')}**")
                if top.get("min_link"):
                    st.markdown(f"[Open product link]({top.get('min_link')})")
            else:
                st.info("Found offers but none had a parseable price.")

            st.markdown("---")
            st.markdown("#### All clusters (click to expand)")
            for c in clusters[:30]:
                header = f"{c['canonical']} — Min: {'₹{:.2f}'.format(c['min_price']) if c['min_price'] is not None else 'N/A'}"
                with st.expander(header):
                    df = pd.DataFrame(c["items"])
                    # include clickable links (markdown) if present
                    if not df.empty:
                        # ensure columns
                        if "price" in df.columns:
                            df["price_display"] = df["price"].apply(lambda v: f"₹{v:.2f}" if v is not None else "N/A")
                        display_cols = [c for c in ["title", "source", "price_display", "link"] if c in df.columns]
                        # Use st.table / st.dataframe for clean view, and also show direct clickable links below
                        st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
                        # Provide clickable links as separate list for easier click
                        for idx, row in df.iterrows():
                            txt = row.get("title") or "-"
                            src = row.get("source") or "-"
                            link = row.get("link") or ""
                            if link:
                                st.markdown(f"- **{src}** — [{txt}]({link}) — {row.get('price_display','')}")
                            else:
                                st.markdown(f"- **{src}** — {txt} — {row.get('price_display','')}")
                    else:
                        st.write("No items in this cluster.")

    except requests.HTTPError as e:
        st.error(f"HTTP error while calling SerpApi: {e}")
    except Exception as e:
        st.error(f"Error: {e}")

# Show cached queries summary
st.markdown("---")
st.subheader("Cached searches (recent)")

init_db()
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute("SELECT query, fetched_at FROM search_cache ORDER BY fetched_at DESC LIMIT 50")
rows = cur.fetchall()
conn.close()
if rows:
    dfc = pd.DataFrame(rows, columns=["query", "fetched_at"])
    dfc["age_minutes"] = dfc["fetched_at"].apply(lambda ts: int((time.time() - ts) / 60))
    st.dataframe(dfc, use_container_width=True)
else:
    st.info("No cached searches yet. Run a query to populate the cache.")
