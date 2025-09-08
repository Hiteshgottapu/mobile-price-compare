# product_fetcher.py
"""
Fetch a single product page and extract title/price/availability.

Usage:
    from product_fetcher import fetch_product_page
    info = fetch_product_page("https://www.some-shop.example/product/123", use_cache=True, max_age_minutes=1440)
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re
import time
import logging

# try to import your product_cache module (expects functions save_offers/get_offers from product_cache.py)
try:
    import product_cache  # type: ignore
    HAVE_PRODUCT_CACHE = True
except Exception:
    HAVE_PRODUCT_CACHE = False

# Try playwright import (optional)
try:
    from playwright.sync_api import sync_playwright  # type: ignore
    HAVE_PLAYWRIGHT = True
except Exception:
    HAVE_PLAYWRIGHT = False

logger = logging.getLogger(__name__)


def _normalize_price_string(s: str) -> Optional[float]:
    if not s:
        return None
    # extract first match of digits, commas, dots
    m = re.search(r"[\d\.,]+", s.replace("\u00a0", " "))
    if not m:
        return None
    num = m.group(0).replace(",", "")
    # handle multiple dots - keep last dot as decimal separator if present
    if num.count(".") > 1:
        parts = num.split(".")
        # join all but last as thousands, keep last as decimal
        num = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(num)
    except Exception:
        try:
            return float(num.replace(".", ""))
        except Exception:
            return None


def _extract_price_from_soup(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """
    Tries multiple selectors and meta tags to find a price string and currency.
    Returns dict with keys: price_raw (str or None), price (float or None), currency (str or None)
    """
    # Candidate selectors typically used by e-commerce sites
    selectors = [
        "[itemprop=price]::attr(content)",  # meta price
        "meta[property='product:price:amount']::attr(content)",
        "meta[itemprop='price']::attr(content)",
        "span[itemprop='price']::text",
        ".price::text",
        ".product-price::text",
        ".selling-price::text",
        ".final-price::text",
        ".priceblock_ourprice::text",  # amazon-ish
        ".a-price-whole::text",  # amazon whole part
        ".a-offscreen::text",  # amazon offscreen price
        "[class*='price']::text",
        "[id*='price']::text",
    ]

    # Try meta tags first
    # meta tags
    meta_price = None
    meta = soup.find("meta", {"property": "product:price:amount"})
    if meta and meta.get("content"):
        meta_price = meta.get("content").strip()
    if not meta_price:
        meta = soup.find("meta", {"itemprop": "price"})
        if meta and meta.get("content"):
            meta_price = meta.get("content").strip()
    if meta_price:
        price_val = _normalize_price_string(meta_price)
        return {"price_raw": meta_price, "price": price_val, "currency": None}

    # More robust approach: scan many text nodes for currency symbols or patterns
    currency_re = re.compile(r"(₹|rs\.?|inr|\$|€|£)", re.IGNORECASE)
    # candidate nodes that often contain price
    candidate_nodes = []
    # common classes/ids heuristics
    for sel in ["span", "div", "p", "strong", "b"]:
        candidate_nodes.extend(soup.select(f"{sel}[class*='price']"))
        candidate_nodes.extend(soup.select(f"{sel}[id*='price']"))
        candidate_nodes.extend(soup.select(f"{sel}[class*='amount']"))

    # also check some specific patterns
    candidate_nodes.extend(soup.select(".a-offscreen"))  # Amazon price container
    candidate_nodes.extend(soup.select("[itemprop='price']"))

    # fallback: entire body text split into lines
    if not candidate_nodes:
        text = soup.get_text(separator="\n")
        for line in text.splitlines():
            if currency_re.search(line):
                candidate_nodes.append(line)

    # examine candidates
    for node in candidate_nodes:
        text = node.get_text() if hasattr(node, "get_text") else str(node)
        if not text:
            continue
        text = text.strip()
        # prefer lines that include a currency symbol or "Rs" or a number with thousands separator
        if currency_re.search(text) or re.search(r"\d[\d,\.]{2,}\d", text):
            price_val = _normalize_price_string(text)
            if price_val is not None:
                # try to capture currency symbol
                cur_m = currency_re.search(text)
                currency = cur_m.group(0) if cur_m else None
                return {"price_raw": text, "price": price_val, "currency": currency}

    # Final fallback: search whole page for first numeric-looking token with currency
    page_text = soup.get_text(separator=" ")
    m = re.search(r"((₹|Rs\.?|INR|\$|€|£)\s*[\d\.,]+)", page_text, re.IGNORECASE)
    if m:
        text = m.group(1).strip()
        price_val = _normalize_price_string(text)
        currency = m.group(2)
        return {"price_raw": text, "price": price_val, "currency": currency}

    return {"price_raw": None, "price": None, "currency": None}


def _extract_title_from_soup(soup: BeautifulSoup) -> Optional[str]:
    # Try common meta/title selectors
    title = None
    meta = soup.find("meta", {"property": "og:title"})
    if meta and meta.get("content"):
        title = meta.get("content").strip()
    if not title:
        meta = soup.find("meta", {"name": "twitter:title"})
        if meta and meta.get("content"):
            title = meta.get("content").strip()
    if not title:
        # h1
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
    if not title:
        # page title
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
    return title


def fetch_product_page(
    url: str,
    use_cache: bool = True,
    max_age_minutes: int = 60 * 24,  # default 24 hours
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    timeout: int = 15,
    use_playwright_if_needed: bool = True,
    force_playwright: bool = False,
) -> Dict[str, Any]:
    """
    Fetch a product page and attempt to extract title, price, currency and availability.
    Returns a dict with keys:
      - title, price_raw, price (float or None), currency, availability (text), url, fetched_at (ISO), method (requests/playwright/cache)
    Caching: if product_cache module is available, we store the returned dict under the URL as a cache entry (using save_offers/get_offers).
    """

    cache_key = url.strip()
    # Try cache
    if use_cache and HAVE_PRODUCT_CACHE:
        try:
            cached = product_cache.get_offers(cache_key, max_age_minutes=max_age_minutes)
            if cached:
                # our product_cache stores offers list per query; we store single element lists for URL
                if isinstance(cached, list) and len(cached) > 0:
                    obj = cached[0]
                    obj["method"] = "cache"
                    obj["cached"] = True
                    return obj
        except Exception:
            # ignore cache failures
            pass

    headers = {"User-Agent": user_agent, "Accept-Language": "en-US,en;q=0.9"}

    # Use requests to fetch first
    if not force_playwright:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            title = _extract_title_from_soup(soup)
            price_info = _extract_price_from_soup(soup)
            availability = None
            # try common availability indicators
            av = soup.select_one("[class*='availability'], [id*='availability'], .stock, .product-availability")
            if av:
                availability = av.get_text(strip=True)
            result = {
                "url": url,
                "title": title,
                "price_raw": price_info.get("price_raw"),
                "price": price_info.get("price"),
                "currency": price_info.get("currency"),
                "availability": availability,
                "fetched_at": datetime.utcnow().isoformat(),
                "method": "requests"
            }
            # if price found, cache and return
            if result["price"] is not None or not use_playwright_if_needed:
                if HAVE_PRODUCT_CACHE:
                    try:
                        product_cache.save_offers(cache_key, [result])
                    except Exception:
                        pass
                return result
            # else, price not found; fall through to playwright if allowed
        except Exception as e:
            logger.debug(f"requests fetch failed for {url}: {e}")
            # Fall through to playwright if allowed

    # Playwright fallback
    if (force_playwright or use_playwright_if_needed) and HAVE_PLAYWRIGHT:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=user_agent)
                page.goto(url, timeout=60000)
                # wait for network idle or small time
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except Exception:
                    time.sleep(1)
                html = page.content()
                browser.close()
            soup = BeautifulSoup(html, "html.parser")
            title = _extract_title_from_soup(soup)
            price_info = _extract_price_from_soup(soup)
            availability = None
            av = soup.select_one("[class*='availability'], [id*='availability'], .stock, .product-availability")
            if av:
                availability = av.get_text(strip=True)
            result = {
                "url": url,
                "title": title,
                "price_raw": price_info.get("price_raw"),
                "price": price_info.get("price"),
                "currency": price_info.get("currency"),
                "availability": availability,
                "fetched_at": datetime.utcnow().isoformat(),
                "method": "playwright"
            }
            if HAVE_PRODUCT_CACHE:
                try:
                    product_cache.save_offers(cache_key, [result])
                except Exception:
                    pass
            return result
        except Exception as e:
            logger.debug(f"Playwright fetch failed for {url}: {e}")
            # final fallback: return partial info or error object

    # If we reach here, neither requests nor playwright produced a price
    # Return best-effort object
    fallback = {
        "url": url,
        "title": None,
        "price_raw": None,
        "price": None,
        "currency": None,
        "availability": None,
        "fetched_at": datetime.utcnow().isoformat(),
        "method": "none"
    }
    if HAVE_PRODUCT_CACHE:
        try:
            product_cache.save_offers(cache_key, [fallback])
        except Exception:
            pass
    return fallback


# Quick CLI test
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch a product page and print extracted fields.")
    parser.add_argument("url", help="Product page URL to fetch")
    parser.add_argument("--no-cache", action="store_true", help="Ignore cache")
    parser.add_argument("--playwright", action="store_true", help="Force Playwright rendering")
    args = parser.parse_args()
    res = fetch_product_page(args.url, use_cache=not args.no_cache, force_playwright=args.playwright)
    import json
    print(json.dumps(res, indent=2, ensure_ascii=False))
