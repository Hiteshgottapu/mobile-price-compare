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
        /* Main Search Button Style */
        .search-button-main > button {
            width: 100%;
            margin-top: 1rem;
            padding: 0.9rem 2.4rem;
            font-size: 1.3rem;
            background: linear-gradient(90deg, #2563eb 0%, #1e40af 100%);
            border-radius: 16px;
            box-shadow: 0 4px 15px rgba(30,64,175,0.2);
        }
        .search-button-main > button:hover {
            background: linear-gradient(90deg, #1e40af 0%, #2563eb 100%);
            box-shadow: 0 6px 20px rgba(30,64,175,0.25);
            transform: translateY(-3px) scale(1.02);
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

        /* New/Updated Styles for UI improvements */
        .stSidebar {
            background-color: #f0f2f6;
            border-right: 1px solid #e0e7ef;
            box-shadow: 2px 0 10px rgba(0,0,0,0.05);
        }
        .stSidebar .stRadio > label, .stSidebar .stCheckbox > label {
            color: #1a365d;
            font-weight: 600;
        }
        .stSidebar .stSlider > div > div:nth-child(1) {
            color: #2563eb;
        }
        .search-container {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            margin-bottom: 2rem;
            padding: 1.5rem;
            background: #f8fafc;
            border-radius: 18px;
            box-shadow: 0 4px 18px rgba(30,64,175,0.08);
            border: 1px solid #e0e7ef;
        }
        .product-card {
            border-radius: 16px;
            padding: 1.2rem;
            margin-bottom: 1.1rem;
            min-height: 420px;
            max-height: 420px;
            box-shadow: 0 3px 12px rgba(30,64,175,0.08);
            transition: box-shadow 0.2s, transform 0.2s;
            border: 1.5px solid #e0e7ef;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
            background: #fff;
            position: relative;
        }
        .product-card:hover {
            box-shadow: 0 8px 28px rgba(30,64,175,0.15);
            transform: translateY(-3px) scale(1.02);
            border-color: #2563eb;
        }
        .product-card img {
            max-width: 90%;
            max-height: 160px;
            object-fit: contain;
            border-radius: 10px;
            margin-bottom: 0.8rem;
            display: block;
            margin-left: auto;
            margin-right: auto;
            border: 1px solid #f1f5fa;
        }
        .product-title {
            font-size:1.2rem;
            color:#1a365d;
            font-weight:700;
            margin-bottom: 0.6rem;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-overflow: ellipsis;
            line-height: 1.35;
        }
        .product-details {
            font-size: 0.98rem;
            color: #4a5568;
            margin-bottom: 0.4rem;
        }
        .product-price {
            color:#1e40af;
            font-size:1.3rem;
            font-weight:800;
            margin-top: 0.6rem;
            margin-bottom: 0.8rem;
        }
        .view-btn {
            color: #fff !important;
            background: linear-gradient(90deg, #22c55e 0%, #10b981 100%);
            padding: 0.8rem 1.8rem;
            border-radius: 12px;
            text-decoration: none !important;
            font-weight: 700;
            font-size: 1.15rem;
            margin-top: auto;
            display: block;
            text-align: center;
            box-shadow: 0 2px 10px rgba(34,197,94,0.15);
            transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
        }
        .view-btn:hover {
            background: linear-gradient(90deg, #10b981 0%, #22c55e 100%);
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(34,197,94,0.2);
        }
        .source-badge {
            display: inline-block;
            font-size: 0.85rem;
            font-weight: 700;
            padding: 0.2em 0.7em;
            border-radius: 8px;
            margin-right: 0.5em;
            margin-bottom: 0.5em;
            color: #fff;
            position: absolute;
            top: 15px;
            right: 15px;
            z-index: 10;
            box-shadow: 0 1px 4px rgba(0,0,0,0.1);
        }
        .amazon-badge {
            background: linear-gradient(45deg, #FF9900, #F7C040);
            left: 15px;
            right: auto;
        }
        .flipkart-badge {
            background: linear-gradient(45deg, #2874f0, #4092f0);
        }
        .stSpinner > div {
            color: #2563eb;
        }
        .stProgress > div > div > div > div {
            background-color: #2563eb;
        }
        .no-results-message {
            text-align: center;
            margin-top: 3rem;
            font-size: 1.3rem;
            color: #4a5568;
            padding: 2rem;
            border: 2px dashed #e0e7ef;
            border-radius: 18px;
            background: #f8fafc;
            box-shadow: 0 2px 10px rgba(30,64,175,0.05);
        }
        .welcome-message {
            text-align: center;
            margin-top: 3rem;
            font-size: 1.4rem;
            color: #2563eb;
            background: linear-gradient(135deg, #e0f2fe 0%, #dbeafe 100%);
            padding: 2.5rem;
            border-radius: 20px;
            box-shadow: 0 4px 15px rgba(30,64,175,0.1);
            border: 1px solid #bfdbfe;
        }
        .welcome-message p {
            margin-bottom: 1.5rem;
            line-height: 1.6;
            color: #1e40af;
        }
        .welcome-message .stIcon {
            font-size: 3rem;
            color: #1e40af;
            margin-bottom: 1rem;
        }
        @media (max-width: 900px) {
            .main .block-container {
                padding: 1.2rem 0.8rem;
            }
            .stDataFrame, .stTable {
                font-size: 0.95rem;
            }
            .product-card {
                min-height: 380px;
                max-height: 380px;
            }
            .product-title {
                font-size: 1.1rem;
            }
            .product-price {
                font-size: 1.2rem;
            }
            .view-btn {
                font-size: 1.0rem;
                padding: 0.6rem 1.2rem;
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

    # Debug: Print all sources and links from SerpApi results
    for it in offers_raw:
        title = it.get("title") or it.get("name") or ""
        source_val = ""
        for k in ("source", "merchant", "store", "store_name", "seller", "marketplace"):
            v = it.get(k)
            if v:
                source_val = str(v)
                break
        link = it.get("link") or it.get("product_link") or it.get("click") or ""
        print(f"DEBUG: Source: {source_val}, Link: {link}, Title: {title}")

    BLOCKED_DOMAINS = ["addmecart", "meesho"]
    EXCLUDE_KEYWORDS = [
        "case", "cover", "glass", "protector", "tempered", "screen guard", "back cover", "flip cover",
        "bumper", "pouch", "stand", "holder", "skin", "matte", "film", "combo", "charger", "adapter",
        "cable", "earphone", "headphone", "wireless", "bluetooth", "speaker", "smartwatch", "band",
        "strap", "mount", "dock", "cleaner", "lens", "stylus", "ring", "tripod", "selfie", "car mount",
        "car charger", "rent", "rental", "for rent", "maccafe", "back cover", "panel",
        "pen", "stylus pen"  # Added to catch S Pen and similar accessories
    ]

    def is_accessory(title: str) -> bool:
        t = title.lower() if title else ""
        return any(kw in t for kw in EXCLUDE_KEYWORDS)

    def is_blocked_website(source: str, link: str) -> bool:
        s = source.lower() if source else ""
        l = link.lower() if link else ""
        # Never block Amazon or Flipkart
        if "amazon" in s or "flipkart" in s or "amazon" in l or "flipkart" in l:
            return False
        return any(b in s or b in l for b in BLOCKED_DOMAINS)

    def title_matches_query(title: str, query_text: str) -> bool: # Renamed query to query_text to avoid conflict
        if not query_text or not title:
            return True
        # Normalize query and title for better matching
        q_tokens = [t for t in normalize_text(query_text).split() if t and len(t) > 1] # Ignore single-char tokens
        title_norm = normalize_text(title)
        # All query tokens must be present in the title (case-insensitive)
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
        thumbnail = it.get("thumbnail") or it.get("image") or "" # Added thumbnail extraction

        exclusion_reason = None
        if not title:
            exclusion_reason = "No title"
        elif is_accessory(title):
            exclusion_reason = "Accessory/rental detected"
        elif is_blocked_website(source, link):
            exclusion_reason = f"Blocked domain: {source}"
        elif not title_matches_query(title, query): # Use the passed 'query' argument here
            exclusion_reason = "Title does not sufficiently match query"

        if exclusion_reason:
            # Uncomment the following line for extensive debug logging of exclusions
            # print(f"EXCLUDED [{source}] - {exclusion_reason} | Title: {title} | Link: {link}")
            continue

        price = (
            it.get("price") or
            it.get("extracted_price") or
            it.get("price_string") or
            it.get("displayed_price") or
            None
        )
        # Try to extract price from nested dicts if not found
        if not price and isinstance(it.get("raw"), dict):
            raw_price = (
                it["raw"].get("price") or
                it["raw"].get("price_string") or
                it["raw"].get("extracted_price")
            )
            if raw_price:
                price = raw_price

        # Try to extract price from title if still not found
        if not price:
            title_str = it.get("title") or it.get("name") or ""
            # Try to find a number with or without currency symbol (₹, Rs, INR, rupees)
            m = re.search(r'(?:₹|rs\.?|inr|rupees)?\s*([\d,]+)', title_str, re.IGNORECASE)
            if m:
                price = m.group(1).replace(",", "")
            else:
                # Try to find a number with "rupees" after it
                m2 = re.search(r'(\d{4,7})\s*(rs|inr|rupees)', title_str.lower())
                if m2:
                    price = m2.group(1)

        # If price is still not found, try to extract from description or subtitle if available
        if not price:
            for key in ["description", "subtitle", "snippet"]:
                val = it.get(key)
                if isinstance(val, str):
                    m = re.search(r'(?:₹|rs\.?|inr|rupees)?\s*([\d,]+)', val, re.IGNORECASE)
                    if m:
                        price = m.group(1).replace(",", "")
                        break

        # If price is still not found, try to extract from the link (for some Indian sites, price is in URL)
        if not price:
            link_val = it.get("link") or ""
            m = re.search(r'[\?&]price=([\d,]+)', link_val)
            if m:
                price = m.group(1).replace(",", "")

        # Ensure price is a string for consistent parsing later
        price_str = str(price) if price is not None else ""

        offers.append({
            "title": title,
            "source": source or None,
            "price": price_str, # Store as string, parse to float when needed for comparison
            "link": link,
            "thumbnail": thumbnail, # Include thumbnail
            "raw_serpapi_data": it # Keep raw data for advanced debugging if needed
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
    # Keep alphanumeric characters, spaces, and '+'
    cleaned = re.sub(r'[^a-z0-9\s+]', ' ', s)
    cleaned = " ".join(cleaned.split()) # Remove extra spaces
    return cleaned

def price_to_float(p) -> Optional[float]:
    if p is None:
        return None
    s = str(p)
    # Remove currency symbols, commas, and spaces, then attempt to convert to float
    s = s.replace(" ", "")
    s = re.sub(r'[^\d\.]', '', s)
    try:
        # Some prices may be like "128000.00" or "128000"
        return float(s)
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
    if not counts: # Handle case where all titles are empty or normalize to empty
        return ""
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
                # Use a more robust check for non-fuzzy matching
                if norm in c["canonical_norm"] or c["canonical_norm"] in norm or norm == c["canonical_norm"]:
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
        min_thumbnail = None
        rows = []
        titles_for_canonical = []
        for it in c["items"]:
            pr = price_to_float(it.get("price"))
            rows.append({
                "title": it.get("title"),
                "source": it.get("source"),
                "price": it.get("price"), # Keep original price string here for display
                "link": it.get("link"),
                "thumbnail": it.get("thumbnail") # Include thumbnail in individual items
            })
            titles_for_canonical.append(it.get("title"))
            if pr is not None and (min_p is None or pr < min_p):
                min_p = pr
                min_src = it.get("source")
                min_link = it.get("link")
                min_thumbnail = it.get("thumbnail")
        canonical_title = choose_canonical_title(titles_for_canonical)
        out.append({
            "canonical": canonical_title,
            "canonical_norm": normalize_text(canonical_title),
            "min_price": min_p,
            "min_source": min_src,
            "min_link": min_link,
            "min_thumbnail": min_thumbnail, # Add thumbnail to cluster output
            "items": rows # Keep all individual offers in the cluster
        })
    # sort with available prices first, lowest first
    out.sort(key=lambda x: (x["min_price"] is None, x["min_price"] if x["min_price"] is not None else float("inf")))
    return out

# ---------- Streamlit UI ----------
st.sidebar.header("🔎 Filter Products")
query = st.sidebar.text_input("Mobile model (e.g., iPhone 14 128GB)", key="query_input")
live = st.sidebar.checkbox("Live (no-cache)", value=False, key="live_checkbox")
search_btn = st.sidebar.button("Search", key="search_button")

price_min, price_max = st.sidebar.slider("Price Range (₹)", 0, 200000, (0, 200000), step=1000, key="price_range")

if not SERPAPI_KEY:
    st.warning("Missing SERPAPI_KEY. Set it in your environment or .env file.")

def extract_storage_ram(title: str):
    """
    Extract storage (GB/TB) and RAM (GB) from product title using context.
    Returns (storage, ram) as integers in GB if found, else None.
    This version avoids assigning impossible values (e.g., RAM > storage, or RAM > 32GB).
    """
    storage = None
    ram = None
    lower_title = title.lower()

    # Find all "number + gb/tb" patterns with context
    matches = list(re.finditer(r'(\d+)\s*(gb|tb)', lower_title))
    candidates = []
    for m in matches:
        val, unit = m.group(1), m.group(2)
        v = int(val)
        if unit == 'tb':
            v *= 1024
        start, end = m.start(), m.end()
        before = lower_title[max(0, start-15):start]
        after = lower_title[end:end+15]
        context = before + after
        candidates.append((v, context, m.group(0)))

    # Assign RAM and storage based on context
    ram_candidates = [v for v, ctx, _ in candidates if 'ram' in ctx]
    storage_candidates = [v for v, ctx, _ in candidates if any(x in ctx for x in ['rom', 'storage', 'internal', 'ssd'])]
    # Remove RAM candidates from storage list if they overlap
    storage_candidates = [v for v in storage_candidates if v not in ram_candidates]

    # Heuristic: RAM is usually <= 32GB, storage is usually >= 64GB
    likely_ram = [v for v, _, _ in candidates if v <= 32]
    likely_storage = [v for v, _, _ in candidates if v >= 64]

    # Prefer context, but fallback to heuristics if ambiguous
    if ram_candidates:
        ram = max(ram_candidates)
    elif likely_ram:
        ram = max(likely_ram)
    if storage_candidates:
        storage = max(storage_candidates)
    elif likely_storage:
        storage = max(likely_storage)

    # If still ambiguous, assign by order: first is storage, second is ram (if not already set)
    if storage is None and ram is None and len(candidates) == 2:
        # Heuristic: first is storage, second is ram
        first, second = candidates[0][0], candidates[1][0]
        # If first is much larger, treat as storage
        if first > second:
            storage, ram = first, second
        else:
            storage, ram = second, first
    elif storage is None and ram is None and len(candidates) == 1:
        # Only one candidate, treat as storage
        storage = candidates[0][0]

    # Final check: don't set both to the same value unless only one is present
    if storage == ram and storage is not None:
        # If value is plausible for storage but not for RAM, keep as storage only
        if storage >= 64:
            ram = None
        # If value is plausible for RAM but not for storage, keep as ram only
        elif storage <= 32:
            storage = None

    # If RAM > storage, swap if plausible
    if ram is not None and storage is not None and ram > storage:
        # If RAM is plausible storage and storage is plausible RAM, swap
        if ram >= 64 and storage <= 32:
            storage, ram = ram, storage
        else:
            # Otherwise, keep only plausible values
            if storage >= 64:
                ram = None
            elif ram <= 32:
                storage = None

    # At the end, always return int or None for storage/ram
    if storage is not None:
        try:
            storage = int(storage)
        except Exception:
            storage = None
    if ram is not None:
        try:
            ram = int(ram)
        except Exception:
            ram = None
    return storage, ram

def passes_filters(offer_item):
    """Checks if an individual offer item passes the price filters."""
    price_str = offer_item.get("price")
    price_val = price_to_float(price_str)
    
    if price_val is None:
        return False # Exclude items without a parseable price
    
    if price_val < price_min or price_val > price_max:
        return False
    
    # You can add more filters here, e.g., storage, RAM if you want to make them user-configurable
    # For now, storage/RAM extraction is just informative
    return True

if search_btn and query:
    # ---------- Suggestions Section ----------
    st.markdown("### 💡 Suggested RAM/Storage (from results)")
    suggested_ram = set()
    suggested_storage = set()
    offers_from_serpapi = search_serpapi(query, country="in", no_cache=live)
    for offer in offers_from_serpapi:
        storage, ram = extract_storage_ram(offer.get("title", ""))
        if ram:
            suggested_ram.add(ram)
        if storage:
            suggested_storage.add(storage)
    if suggested_ram or suggested_storage:
        st.info(
            f"**RAM:** {', '.join(str(r) + 'GB' for r in sorted(suggested_ram)) if suggested_ram else 'N/A'} &nbsp;&nbsp; "
            f"**Storage:** {', '.join(str(s) + 'GB' for s in sorted(suggested_storage)) if suggested_storage else 'N/A'}"
        )
    else:
        st.info("No RAM/Storage suggestions found in the results.")

    st.info(f"Searching for: **{query}** (live={live})")
    
    if not SERPAPI_KEY:
        st.error("SERPAPI_KEY not set. Cannot perform search.")
    else:
        try:
            # Now, filter these raw offers based on price range
            # Note: The `search_serpapi` function already applies title-matching and accessory filtering.
            filtered_individual_offers = [o for o in offers_from_serpapi if passes_filters(o)]

            if not filtered_individual_offers:
                st.warning("No products found matching your query and filters.")
                # Optional: Show a few raw items that were excluded by your filters for debugging
                if st.checkbox("Show all raw offers (debug)"):
                    if offers_from_serpapi:
                        st.dataframe(pd.DataFrame(offers_from_serpapi).head(20), use_container_width=True)
                    else:
                        st.info("No raw offers were returned from SerpApi at all.")
            else:
                # If we have filtered individual offers, now cluster them
                clusters = cluster_offers(filtered_individual_offers)

                if not clusters:
                    st.warning("No product clusters could be formed from the filtered offers.")
                else:
                    st.markdown("""
                    <style>
                    .product-card {
                        border-radius: 14px;
                        padding: 1.2rem;
                        margin-bottom: 1.1rem;
                        min-height: 450px; /* Increased height to accommodate image and more text */
                        max-height: 450px;
                        box-shadow: 0 2px 10px rgba(30,64,175,0.07);
                        transition: box-shadow 0.2s, transform 0.2s;
                        border: 1.5px solid #e0e7ef;
                        display: flex;
                        flex-direction: column;
                        justify-content: space-between;
                        overflow: hidden; /* Ensure content doesn't overflow fixed height */
                    }
                    .product-card:hover {
                        box-shadow: 0 6px 24px rgba(30,64,175,0.13);
                        transform: translateY(-2px) scale(1.02);
                        border-color: #2563eb;
                    }
                    .product-card img {
                        max-width: 100%;
                        max-height: 150px; /* Limit image height */
                        object-fit: contain; /* Contain image within bounds */
                        border-radius: 8px;
                        margin-bottom: 0.8rem;
                        display: block;
                        margin-left: auto;
                        margin-right: auto;
                    }
                    .product-title {
                        font-size:1.15rem;
                        color:#1a365d;
                        font-weight:600;
                        margin-bottom: 0.5rem;
                        display: -webkit-box;
                        -webkit-line-clamp: 3; /* Limit title to 3 lines */
                        -webkit-box-orient: vertical;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        line-height: 1.3;
                    }
                    .product-price {
                        color:#1e40af;
                        font-size:1.18rem;
                        font-weight:700;
                        margin-top: 0.4rem;
                        margin-bottom: 0.7rem;
                    }
                    .product-source {
                        font-size: 0.95rem;
                        color: #555;
                        margin-bottom: 0.5rem;
                    }
                    .view-btn {
                        color: #fff !important; /* !important to override Streamlit's default a tag color */
                        background: linear-gradient(90deg, #22c55e 0%, #10b981 100%); /* Changed to a greener gradient */
                        padding: 0.7rem 1.6rem;
                        border-radius: 10px;
                        text-decoration: none !important; /* !important */
                        font-weight: 700;
                        font-size: 1.09rem;
                        margin-top: auto; /* Pushes button to the bottom */
                        display: block; /* Make button full width */
                        text-align: center;
                        box-shadow: 0 2px 10px rgba(34,197,94,0.10); /* Greenish shadow */
                        transition: background 0.2s, transform 0.1s, box-shadow 0.2s;
                    }
                    .view-btn:hover {
                        background: linear-gradient(90deg, #10b981 0%, #22c55e 100%);
                        transform: translateY(-2px) scale(1.05); /* Slightly less aggressive scale */
                        box-shadow: 0 4px 16px rgba(34,197,94,0.13);
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    st.markdown("## 🛒 Products Found")
                    
                    cols = st.columns(3)
                    for idx, cluster in enumerate(clusters):
                        # Only display clusters with a valid price
                        if cluster.get("min_price") is not None:
                            with cols[idx % 3]:
                                storage, ram = extract_storage_ram(cluster.get('canonical', ''))
                                source = cluster.get('min_source', '').lower()
                                highlight = ""
                                if "amazon" in source:
                                    highlight = "<span style='background:#ff9900;color:#fff;padding:0.2em 0.7em;border-radius:7px;font-size:0.95em;margin-right:0.5em;'>Amazon</span>"
                                elif "flipkart" in source:
                                    highlight = "<span style='background:#2874f0;color:#fff;padding:0.2em 0.7em;border-radius:7px;font-size:0.95em;margin-right:0.5em;'>Flipkart</span>"

                                min_link = cluster.get('min_link')
                                if (
                                    isinstance(min_link, str)
                                    and min_link.strip()
                                    and (min_link.strip().lower().startswith("http://") or min_link.strip().lower().startswith("https://"))
                                ):
                                    view_btn_html = (
                                        f"<a href='{min_link.strip()}' target='_blank' class='view-btn' style='width:100%;display:block;text-align:center;'>View Product</a>"
                                    )
                                else:
                                    view_btn_html = (
                                        "<a class='view-btn' style='width:100%;display:block;text-align:center;pointer-events:none;opacity:0.5;background:#ccc;'>View Product</a>"
                                    )

                                # Replace product title with RAM and ROM info
                                ram_rom_info = f"RAM: {ram if ram is not None else 'N/A'}GB | Storage: {storage if storage is not None else 'N/A'}GB"

                                st.markdown(f"""
                                <div class='product-card'>
                                    <img src='{cluster.get('min_thumbnail', 'https://via.placeholder.com/150?text=No+Image')}' alt='{cluster.get('canonical')}' />
                                    <div class='product-source'>Source: {cluster.get('min_source', 'N/A').title()}</div>
                                    <div class='product-details'>Title: {cluster.get('canonical')}</div>
                                    <div class='product-price'>Price: ₹{cluster['min_price']:.2f}</div>
                                    {view_btn_html}
                                </div>
                                """, unsafe_allow_html=True)
                        
                    # Optional: Display all individual offers within the top cluster if user wants more detail
                    if clusters and st.expander(f"See all offers for: **{clusters[0]['canonical']}**"):
                        df_items = pd.DataFrame(clusters[0]["items"])
                        # Format price column for better readability
                        df_items['price'] = df_items['price'].apply(lambda p: f"₹{price_to_float(p):.2f}" if price_to_float(p) is not None else "N/A")
                        st.dataframe(df_items[['title', 'source', 'price', 'link']], use_container_width=True)


        except requests.HTTPError as e:
            st.error(f"HTTP error while calling SerpApi: {e}. Check your API key and query.")
        except RuntimeError as e: # Catch the specific RuntimeError for missing API key
            st.error(f"Configuration error: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

# Show cached queries summary
st.markdown("---")
st.subheader("Cached searches (recent)")

init_db() # Ensure DB is initialized before trying to read from it
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
