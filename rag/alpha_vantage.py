"""
Alpha Vantage client: daily price move, sector performance, Nasdaq proxy,
and news sentiment. Free tier is rate-limited (25 req/day), so results are
cached hard — this is not meant to be called once per user question.
"""
import os
import time
import threading
import requests

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY")
BASE_URL = "https://www.alphavantage.co/query"
CACHE_TTL_SECONDS = 60 * 60 * 6  # 6h

_lock = threading.Lock()
_cache: dict = {}


def _cached_get(params: dict, cache_key: str) -> dict | None:
    with _lock:
        entry = _cache.get(cache_key)
        if entry and (time.time() - entry[0]) < CACHE_TTL_SECONDS:
            return entry[1]

    if not ALPHA_VANTAGE_KEY:
        return None

    try:
        resp = requests.get(BASE_URL, params={**params, "apikey": ALPHA_VANTAGE_KEY}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"Alpha Vantage request failed ({cache_key}): {exc}")
        return None

    # AV returns HTTP 200 even when rate-limited — message is in the body.
    if "Note" in data or "Information" in data:
        print(f"Alpha Vantage limited: {data.get('Note') or data.get('Information')}")
        return None

    with _lock:
        _cache[cache_key] = (time.time(), data)
    return data


def get_daily_quote(ticker: str) -> dict | None:
    data = _cached_get({"function": "GLOBAL_QUOTE", "symbol": ticker}, f"quote:{ticker}")
    quote = (data or {}).get("Global Quote") or {}
    if not quote:
        return None
    try:
        return {
            "price": float(quote["05. price"]),
            "change": float(quote["09. change"]),
            "change_pct": float(quote["10. change percent"].rstrip("%")),
        }
    except (KeyError, ValueError):
        return None


def get_nasdaq_change_pct() -> float | None:
    """QQQ (Nasdaq-100 ETF) as a proxy — free tier doesn't support raw
    index symbols like ^IXIC."""
    quote = get_daily_quote("QQQ")
    return quote["change_pct"] if quote else None


def get_sector_performance() -> dict | None:
    data = _cached_get({"function": "SECTOR"}, "sector_performance")
    if not data:
        return None
    bucket = data.get("Rank A: Real-Time Performance") or data.get("Rank B: 1 Day Performance")
    if not bucket:
        return None
    out = {}
    for sector, pct_str in bucket.items():
        try:
            out[sector] = float(pct_str.rstrip("%"))
        except ValueError:
            continue
    return out


def get_news_sentiment(ticker: str, limit: int = 5) -> list[dict]:
    data = _cached_get(
        {"function": "NEWS_SENTIMENT", "tickers": ticker, "limit": limit},
        f"news:{ticker}",
    )
    if not data:
        return []
    out = []
    for item in data.get("feed", [])[:limit]:
        title = item.get("title")
        if not title:
            continue
        ts = next((t for t in item.get("ticker_sentiment", []) if t.get("ticker") == ticker), None)
        out.append({
            "title": title,
            "score": float(ts["ticker_sentiment_score"]) if ts else None,
            "label": ts["ticker_sentiment_label"] if ts else "unknown",
            "source": item.get("source"),
        })
    return out