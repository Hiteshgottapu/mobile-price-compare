# aggregate.py
"""
Simple aggregator for mobile offers.
- Normalizes titles
- Clusters similar offers (uses rapidfuzz if available, otherwise substring logic)
- Computes min price per cluster and returns clusters sorted by price (lowest first)

Usage:
    from aggregate import run_aggregation, cluster_offers
    clusters = run_aggregation(offers=offers_list)

Or as CLI to read a JSON file (array or newline-delimited):
    python aggregate.py path/to/offers.json
"""

from typing import List, Dict, Any, Optional
import json
import re
from pathlib import Path

# optional fuzzy matching
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except Exception:
    HAS_RAPIDFUZZ = False


def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    # keep alnum, space, + and remove other punctuation
    s = re.sub(r"[^a-z0-9+\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def price_to_float(p) -> Optional[float]:
    if p is None:
        return None
    s = str(p)
    m = re.search(r"[\d\.,]+", s)
    if not m:
        return None
    num = m.group(0).replace(",", "")
    try:
        return float(num)
    except Exception:
        return None


def cluster_offers(
    offers: List[Dict[str, Any]],
    threshold: int = 85
) -> List[Dict[str, Any]]:
    """
    Cluster offers into groups that likely refer to the same canonical model.
    Input offers: list of dicts with at least 'title', 'source', 'price', 'link' (price optional).
    Returns clusters:
    [
      {
        "canonical": <representative title>,
        "canonical_norm": <normalized>,
        "min_price": <float or None>,
        "min_source": <str or None>,
        "min_link": <str or None>,
        "items": [ {title, source, price, link}, ... ]
      },
      ...
    ]
    """
    clusters: List[Dict[str, Any]] = []

    for off in offers:
        title = (off.get("title") or off.get("name") or off.get("product") or "").strip()
        norm = normalize_text(title)

        placed = False
        if HAS_RAPIDFUZZ:
            for c in clusters:
                # compare normalized strings using token sort ratio (robust to word order)
                score = fuzz.token_sort_ratio(norm, c["canonical_norm"])
                if score >= threshold:
                    c["items"].append(off)
                    placed = True
                    break
        else:
            # fallback heuristic: normalized substring or token overlap
            for c in clusters:
                if not c["canonical_norm"] or not norm:
                    continue
                if norm in c["canonical_norm"] or c["canonical_norm"] in norm:
                    c["items"].append(off)
                    placed = True
                    break
                # token overlap > 60%
                tokens_a = set(norm.split())
                tokens_b = set(c["canonical_norm"].split())
                if tokens_a and tokens_b:
                    inter = tokens_a.intersection(tokens_b)
                    score = (len(inter) * 100) / max(len(tokens_a), len(tokens_b))
                    if score >= 60:
                        c["items"].append(off)
                        placed = True
                        break

        if not placed:
            clusters.append({
                "canonical": title or "",
                "canonical_norm": norm or "",
                "items": [off]
            })

    # compute min price and pick min item per cluster
    out_clusters: List[Dict[str, Any]] = []
    for c in clusters:
        min_price = None
        min_item = None
        items_out = []
        for it in c["items"]:
            pr = price_to_float(it.get("price") or it.get("price_raw") or it.get("display_price") or "")
            items_out.append({
                "title": it.get("title") or it.get("name") or "",
                "source": it.get("source") or it.get("merchant") or it.get("store") or "",
                "price": pr,
                "price_raw": it.get("price") or it.get("price_raw") or "",
                "link": it.get("link") or it.get("url") or ""
            })
            if pr is not None and (min_price is None or pr < min_price):
                min_price = pr
                min_item = it
        out_clusters.append({
            "canonical": c.get("canonical") or (items_out[0]["title"] if items_out else ""),
            "canonical_norm": c.get("canonical_norm") or "",
            "min_price": min_price,
            "min_source": (min_item.get("source") if min_item else None) or (items_out[0]["source"] if items_out else None),
            "min_link": (min_item.get("link") if min_item else None) or (items_out[0]["link"] if items_out else None),
            "items": items_out
        })

    # sort clusters: ones with prices first, ascending by min_price
    out_clusters.sort(key=lambda x: (x["min_price"] is None, x["min_price"] if x["min_price"] is not None else float("inf")))
    return out_clusters


def load_offers_from_file(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8").strip()
    if not txt:
        return []
    try:
        data = json.loads(txt)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # if shape is {offers: [...]}
            if "offers" in data and isinstance(data["offers"], list):
                return data["offers"]
            # else wrap
            return [data]
    except Exception:
        # try NDJSON (one JSON object per line)
        items = []
        for line in txt.splitlines():
            ln = line.strip()
            if not ln:
                continue
            # trim trailing commas
            if ln.endswith(","):
                ln = ln[:-1]
            try:
                obj = json.loads(ln)
                items.append(obj)
            except Exception:
                # try to salvage JSON object inside the line
                m = re.search(r"\{.*\}", ln)
                if m:
                    try:
                        obj = json.loads(m.group(0))
                        items.append(obj)
                    except Exception:
                        continue
        return items


def run_aggregation(offers: Optional[List[Dict[str, Any]]] = None, input_file: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Main entry point.
    - offers: optional list of offer dicts (if provided, will be used)
    - input_file: optional path to a JSON/NDJSON file with offers
    Returns clustered aggregation list.
    """
    if offers is None:
        if input_file:
            offers = load_offers_from_file(input_file)
        else:
            return []
    # ensure list
    if not isinstance(offers, list):
        return []

    clusters = cluster_offers(offers)
    return clusters


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aggregate scraped / SerpApi offers into clusters and compute min price.")
    parser.add_argument("input", nargs="?", help="Input JSON or NDJSON file with offers. If omitted, reads from stdin.")
    parser.add_argument("--threshold", type=int, default=85, help="Fuzzy-match threshold (0-100)")
    args = parser.parse_args()

    offers_data = []
    if args.input:
        offers_data = load_offers_from_file(args.input)
    else:
        # try read stdin
        import sys
        txt = sys.stdin.read().strip()
        if txt:
            try:
                offers_data = json.loads(txt)
                if not isinstance(offers_data, list):
                    offers_data = [offers_data]
            except Exception:
                lines = [l for l in txt.splitlines() if l.strip()]
                for l in lines:
                    try:
                        offers_data.append(json.loads(l))
                    except Exception:
                        continue

    clusters = run_aggregation(offers=offers_data)
    print(json.dumps(clusters, indent=2, ensure_ascii=False))
