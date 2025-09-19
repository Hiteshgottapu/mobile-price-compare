# app.py
"""
Minimal Streamlit app for Mobile Price Compare using SerpApi.
Self-contained: includes a tiny SerpApi client and a simple SQLite cache.
Dependencies:
    pip install streamlit requests pandas rapidfuzz python-dotenv
(rapidfuzz is optional — if missing, the app will fall back to a simple exact/substring clusterer)

Usage:
    1. Put SERPAPI_KEY in your environment or .env
    2. Run:
           streamlit run app.py
"""
import os
from dotenv import load_dotenv
import time
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import pandas as pd
import streamlit as st
from collections import Counter
import re

# Optional fuzzy library: rapidfuzz
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except Exception:
    HAS_RAPIDFUZZ = False

load_dotenv()
# ---------- Config ----------
DB_PATH = Path(__file__).parent / "cache.sqlite"
SERPAPI_URL = "https://serpapi.com/search"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")  # now loaded from .env or environment
CACHE_TTL = 60 * 60  # 1 hour cache default

st.set_page_config(page_title="Mobile Price Compare", layout="wide")
st.title("📱 Mobile Price Compare — SerpApi")

# ---------- Custom HTML & CSS ----------
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
    .stExpander {
        transition: box-shadow 0.2s;
    }
    .stExpander:hover {
        box-shadow: 0 2px 12px rgba(30,64,175,0.10);
    }
    .stTextInput {
        box-shadow: 0 2px 10px rgba(30,64,175,0.07);
        border-radius: 14px;
        margin-bottom: 0.5rem;
    }
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

    # SerpApi returns shopping results commonly under 'shopping_results' or 'product_results'
    offers_raw = data.get("shopping_results") or data.get("product_results") or []

    # Debug: print source and link for each offer before filtering
    print("--- Raw offers from SerpApi ---")
    for it in offers_raw:
        title = it.get("title") or it.get("name") or it.get("product_title") or it.get("title_raw") or ""
        source_val = ""
        for k in ("source", "merchant", "store", "store_name", "seller", "marketplace"):
            v = it.get(k)
            if v:
                source_val = str(v)
                break
        link = it.get("link") or it.get("product_link") or it.get("click") or ""
        print(f"Source: {source_val}, Link: {link}, Title: {title}")
    BLOCKED_DOMAINS = ["addmecart", "meesho"]
    EXCLUDE_KEYWORDS = [
        "case", "cover", "glass", "protector", "tempered", "screen guard", "back cover", "flip cover",
        "bumper", "pouch", "stand", "holder", "skin", "matte", "film", "combo", "charger", "adapter",
        "cable", "earphone", "headphone", "wireless", "bluetooth", "speaker", "smartwatch", "band",
        "strap", "mount", "dock", "cleaner", "lens", "stylus", "ring", "tripod", "selfie", "car mount",
        "car charger", "rent", "rental", "for rent", "maccafe", "back cover", "panel"
    ]

    def is_accessory(title: str) -> bool:
        t = title.lower() if title else ""
        return any(kw in t for kw in EXCLUDE_KEYWORDS)

    def is_blocked_website(source: str, link: str) -> bool:
        s = source.lower() if source else ""
        l = link.lower() if link else ""
        return any(b in s or b in l for b in BLOCKED_DOMAINS)

    def title_matches_query(title: str, query: str) -> bool:
        if not query or not title:
            return True
        q_tokens = [t for t in normalize_text(query).split() if t]
        title_norm = normalize_text(title)
        return all(tok in title_norm for tok in q_tokens)

    offers = []
    for it in offers_raw:
        title = it.get("title") or it.get("name") or it.get("product_title") or it.get("title_raw") or ""
        source_val = ""
        for k in ("source", "merchant", "store", "store_name", "seller", "marketplace"):
            v = it.get(k)
            if v:
                source_val = str(v)
                break
        source = source_val.lower().strip() if source_val else ""
        link = it.get("link") or it.get("product_link") or it.get("click") or ""

        exclusion_reason = None
        if not title:
            exclusion_reason = "No title"
        elif is_accessory(title):
            exclusion_reason = "Accessory/rental detected"
        elif is_blocked_website(source, link):
            exclusion_reason = f"Blocked domain: {source}"
        elif not title_matches_query(title, query):
            exclusion_reason = "Title does not match query"

        if exclusion_reason:
            # Only log for Amazon/Flipkart
            if "amazon" in source or "flipkart" in source:
                print(f"EXCLUDED [{source}] - {exclusion_reason} | Title: {title} | Link: {link}")
            continue

        price = it.get("price") or it.get("extracted_price") or it.get("price_string") or it.get("displayed_price") or ""
        if not price:
            raw = it.get("raw") or {}
            if isinstance(raw, dict):
                price = raw.get("price") or raw.get("price_string") or raw.get("extracted_price") or price

        offers.append({
            "title": title,
            "source": source or None,
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
    # remove punctuation except + and space & numbers -> replace punctuation by space
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
    m = re.search(r"[\d\.,]+", s)
    if not m:
        return None
    num = m.group(0).replace(",", "")
    try:
        return float(num)
    except Exception:
        return None

def choose_canonical_title(titles: List[str]) -> str:
    """
    Choose a canonical title for a cluster:
    prefer the most common normalized title, else shortest descriptive title.
    """
    if not titles:
        return ""
    # count normalized
    norm_map = {t: normalize_text(t) for t in titles}
    counts = Counter(norm_map.values())
    most_common_norm, _ = counts.most_common(1)[0]
    # pick the shortest original title that has that normalized form (for readability)
    candidates = [t for t, n in norm_map.items() if n == most_common_norm]
    return min(candidates, key=len) if candidates else titles[0]

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

    # compute min price per cluster and pick a better canonical
    out = []
    for c in clusters:
        min_p = None
        min_src = None
        min_link = None
        rows = []
        titles_for_canonical = []
        for it in c["items"]:
            pr = price_to_float(it.get("price"))
            rows.append({
                "title": it.get("title"),
                "source": it.get("source"),
                "price": pr,
                "link": it.get("link")
            })
            titles_for_canonical.append(it.get("title"))
            if pr is not None and (min_p is None or pr < min_p):
                min_p = pr
                min_src = it.get("source")
                min_link = it.get("link")
        canonical_title = choose_canonical_title(titles_for_canonical)
        out.append({
            "canonical": canonical_title,
            "canonical_norm": normalize_text(canonical_title),
            "min_price": min_p,
            "min_source": min_src,
            "min_link": min_link,
            "items": rows
        })
    # sort with available prices first, lowest first
    out.sort(key=lambda x: (x["min_price"] is None, x["min_price"] if x["min_price"] is not None else float("inf")))
    return out

# ---------- Streamlit UI ----------
st.sidebar.header("🔎 Filter Products")
query = st.sidebar.text_input("Mobile model (e.g., iPhone 14 128GB)")
live = st.sidebar.checkbox("Live (no-cache)", value=False)
search_btn = st.sidebar.button("Search")

price_min, price_max = st.sidebar.slider("Price Range (₹)", 0, 200000, (0, 200000), step=1000)

if not SERPAPI_KEY:
    st.warning("Missing SERPAPI_KEY. Set it in your environment or .env file.")

def extract_storage_ram(title: str):
    import re
    storage = None
    ram = None
    storage_matches = re.findall(r'(\d+)\s*(gb|tb)', title.lower())
    for val, unit in storage_matches:
        v = int(val)
        if unit == 'tb':
            v *= 1024
        if storage is None or v > storage:
            storage = v
    ram_matches = re.findall(r'(\d+)\s*(gb)\s*(ram)?', title.lower())
    for val, unit, _ in ram_matches:
        v = int(val)
        if ram is None or v > ram:
            ram = v
    return storage, ram

def passes_filters(offer):
    price = offer.get("price")
    try:
        price_val = float(str(price).replace(",", "").replace("₹", "")) if price else None
    except Exception:
        price_val = None
    if price_val is not None and (price_val < price_min or price_val > price_max):
        return False
    storage, ram = extract_storage_ram(offer.get("title", ""))
    return True

if search_btn and query:
    st.info(f"Searching for: **{query}** (live={live})")
    try:
        offers = search_serpapi(query, country="in", no_cache=live)
        def price_to_float(price):
            try:
                return float(str(price).replace(",", "").replace("₹", ""))
            except Exception:
                return float('inf')
        filtered_offers = [o for o in offers if passes_filters(o)]
        filtered_offers.sort(key=lambda o: price_to_float(o.get('price')))
        if not filtered_offers:
            st.warning("No products found matching your filters.")
        else:
            st.markdown("""
            <style>
            .product-card {
                border-radius: 14px;
                padding: 1.2rem;
                margin-bottom: 1.1rem;
                min-height: 350px;
                max-height: 350px;
                box-shadow: 0 2px 10px rgba(30,64,175,0.07);
                transition: box-shadow 0.2s, transform 0.2s;
                border: 1.5px solid #e0e7ef;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }
            .product-card:hover {
                box-shadow: 0 6px 24px rgba(30,64,175,0.13);
                transform: translateY(-2px) scale(1.02);
                border-color: #2563eb;
            }
            .view-btn {
                color: #fff;
                background: linear-gradient(90deg, #22c55e 0%, #1e40af 100%);
                padding: 0.7rem 1.6rem;
                border-radius: 10px;
                text-decoration: none;
                font-weight: 700;
                font-size: 1.09rem;
                margin-top: 0.7rem;
                display: inline-block;
                box-shadow: 0 2px 10px rgba(30,64,175,0.10);
                transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
            }
            .view-btn:hover {
                background: linear-gradient(90deg, #1e40af 0%, #2563eb 100%);
                transform: scale(1.07);
                box-shadow: 0 4px 16px rgba(30,64,175,0.13);
            }
            </style>
            """, unsafe_allow_html=True)
            st.markdown("## 🛒 Products Found")
            cols = st.columns(3)
            for idx, offer in enumerate(filtered_offers):
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class='product-card'>
                        <b style='font-size:1.15rem;color:#1a365d'>{offer.get('title')}</b><br>
                        <span style='color:#2563eb;font-weight:600'>Price:</span> <b style='color:#1e40af;font-size:1.18rem'>{offer.get('price','-')}</b><br>
                        <a href='{offer.get('link')}' target='_blank' class='view-btn'>View Product</a>
                    </div>
                    """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error: {e}")

# Show notice if API key missing
if not SERPAPI_KEY:
    st.warning("SERPAPI_KEY not set. Live searches will not run. Set the SERPAPI_KEY environment variable or create a .env file.")

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
            if not clusters:
                st.warning("No clusters formed from offers.")
            else:
                # show top (best) cluster and lowest price
                top = clusters[0]
                st.markdown("### 🏆 Best match & lowest price (from clusters)")
                if top.get("min_price") is not None:
                    st.success(f"Cheapest: **₹{top['min_price']:.2f}** on **{top.get('min_source') or 'unknown'}**")
                    if top.get("min_link"):
                        st.markdown(f"[Open product link]({top.get('min_link')})")
                else:
                    st.info("Found offers but none had a parseable price.")

                        # All clusters section and related code removed

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
