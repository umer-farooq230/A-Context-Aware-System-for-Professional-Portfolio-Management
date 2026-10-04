import time
import threading
from dataclasses import dataclass

import numpy as np
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from data.mock_data import get_market_data
from rag import alpha_vantage as av
from rag import sec_edgar

NEWS_PER_TICKER = 5
DOC_CACHE_TTL_SECONDS = 300

_sia = SentimentIntensityAnalyzer()
_lock = threading.Lock()
_cache = {"docs": None, "fetched_at": 0.0}

# Maps your asset_class strings to Alpha Vantage's sector bucket names.
SECTOR_MAP = {
    "Equity - Tech": "Information Technology",
    "Equity - Consumer": "Consumer Discretionary",
    "Equity - Auto": "Consumer Discretionary",
    "Equity - Financials": "Financials",
}


@dataclass
class Doc:
    text: str
    ticker: str
    kind: str  # "metrics" | "market_move" | "news" | "filing"


def _metrics_docs() -> list[Doc]:
    md = get_market_data()
    docs = []
    for t in md.tickers:
        r = md.returns[t].dropna()
        if r.empty:
            continue
        vol_ann = float(r.std() * np.sqrt(252) * 100)
        ret_1d = float((md.prices[t].iloc[-1] / md.prices[t].iloc[-2] - 1) * 100) if len(md.prices) > 1 else None
        ret_5d = float((md.prices[t].iloc[-1] / md.prices[t].iloc[-6] - 1) * 100) if len(md.prices) > 6 else None
        text = (
            f"{t} ({md.names.get(t, t)}, {md.asset_class.get(t, 'Unknown')}): "
            f"annualized volatility {vol_ann:.1f}%, "
            f"{'1-day return ' + f'{ret_1d:.1f}%, ' if ret_1d is not None else ''}"
            f"{'5-day return ' + f'{ret_5d:.1f}%, ' if ret_5d is not None else ''}"
            f"target portfolio weight {md.target_weight.get(t, 0)*100:.1f}%, "
            f"current shares held {md.holdings_qty.get(t, 0)}."
        )
        docs.append(Doc(text=text, ticker=t, kind="metrics"))
    return docs


def _market_move_docs() -> list[Doc]:
    """Ticker move vs. Nasdaq vs. sector — the comparison layer the LLM
    needs to distinguish company-specific moves from broad market moves."""
    md = get_market_data()
    docs = []
    nasdaq_pct = av.get_nasdaq_change_pct()
    sector_perf = av.get_sector_performance() or {}

    for t in md.tickers:
        quote = av.get_daily_quote(t)
        if not quote:
            continue
        sector_name = SECTOR_MAP.get(md.asset_class.get(t))
        sector_pct = sector_perf.get(sector_name) if sector_name else None

        parts = [f"{t} is {quote['change_pct']:+.1f}% today (price ${quote['price']:.2f})."]
        if nasdaq_pct is not None:
            parts.append(f"Nasdaq-100 (QQQ) is {nasdaq_pct:+.1f}% today.")
        if sector_pct is not None:
            parts.append(f"{sector_name} sector is {sector_pct:+.1f}% today.")
        docs.append(Doc(text=" ".join(parts), ticker=t, kind="market_move"))
    return docs


def _news_docs() -> list[Doc]:
    md = get_market_data()
    docs = []
    for t in md.tickers:
        av_items = av.get_news_sentiment(t, limit=NEWS_PER_TICKER)
        if av_items:
            for item in av_items:
                score_str = f"{item['score']:.2f}" if item["score"] is not None else "n/a"
                docs.append(Doc(
                    text=f"News about {t}: \"{item['title']}\" (source: {item['source']}) — "
                         f"sentiment: {item['label']} ({score_str}).",
                    ticker=t, kind="news",
                ))
            continue

        # Fallback for tickers Alpha Vantage doesn't cover well (e.g. crypto).
        try:
            items = yf.Ticker(t).news[:NEWS_PER_TICKER]
        except Exception:
            continue
        for item in items:
            title = item.get("title") or item.get("content", {}).get("title")
            if not title:
                continue
            score = _sia.polarity_scores(title)["compound"]
            label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
            docs.append(Doc(text=f"News about {t}: \"{title}\" — sentiment: {label} ({score:.2f}).",
                             ticker=t, kind="news"))
    return docs


def _filing_docs() -> list[Doc]:
    md = get_market_data()
    docs = []
    for t in md.tickers:
        for f in sec_edgar.get_recent_filings(t):
            docs.append(Doc(
                text=f"{t} filed a {f['form']} with the SEC on {f['date']}. Source: {f['url']}",
                ticker=t, kind="filing",
            ))
    return docs


def get_documents(force_refresh: bool = False) -> list[Doc]:
    with _lock:
        fresh = (time.time() - _cache["fetched_at"]) < DOC_CACHE_TTL_SECONDS
        if _cache["docs"] is not None and fresh and not force_refresh:
            return _cache["docs"]

        docs = _metrics_docs() + _market_move_docs() + _news_docs() + _filing_docs()
        _cache["docs"] = docs
        _cache["fetched_at"] = time.time()
        return docs