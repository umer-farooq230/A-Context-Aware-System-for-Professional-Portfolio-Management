from dataclasses import dataclass
import threading
import time

import pandas as pd
import yfinance as yf

from backend import db

LOOKBACK_PERIOD = "2y"     # how much daily price history to pull
CACHE_TTL_SECONDS = 60     # anti-hammering cache, not a scheduler


@dataclass
class MarketData:
    tickers: list
    names: dict
    asset_class: dict
    prices: pd.DataFrame       # date x ticker, adjusted close
    returns: pd.DataFrame      # daily simple returns
    holdings_qty: dict
    target_weight: dict


class MarketDataError(RuntimeError):
    """Raised when live prices can't be fetched"""


_cache_lock = threading.Lock()
_cache: dict = {"data": None, "fetched_at": 0.0}


def _fetch_live_prices(tickers: list[str]) -> pd.DataFrame:
    try:
        raw = yf.download(
            tickers,
            period=LOOKBACK_PERIOD,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        raise MarketDataError(f"Failed to fetch prices: {exc}")

    if raw is None or raw.empty:
        raise MarketDataError("No market data could be retrieved.")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise MarketDataError("Unexpected response shape from yfinance (no 'Close' field).")
        prices = raw["Close"]
    else:
        if "Close" not in raw.columns:
            raise MarketDataError("Unexpected response shape from yfinance (no 'Close' field).")
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})

    prices = prices.dropna(how="all").ffill().dropna()

    missing = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    if missing:
        raise MarketDataError(f"No price data returned for: {', '.join(missing)}")

    return prices[tickers]


def get_market_data(force_refresh: bool = False) -> MarketData:
    with _cache_lock:
        cached = _cache["data"]
        fresh_enough = (time.time() - _cache["fetched_at"]) < CACHE_TTL_SECONDS
        if cached is not None and fresh_enough and not force_refresh:
            return cached

        user_id = db.get_demo_user_id()
        holdings = db.get_holdings(user_id)
        if not holdings:
            raise MarketDataError("No holdings found in the database for the demo user.")

        tickers = [h["ticker"] for h in holdings]
        names = {h["ticker"]: h["name"] for h in holdings}
        asset_class = {h["ticker"]: h["asset_class"] for h in holdings}
        holdings_qty = {h["ticker"]: h["qty"] for h in holdings}
        target_weight = {h["ticker"]: h["target_weight"] for h in holdings}

        prices_df = _fetch_live_prices(tickers)
        returns_df = prices_df.pct_change().dropna()

        data = MarketData(
            tickers=tickers,
            names=names,
            asset_class=asset_class,
            prices=prices_df,
            returns=returns_df,
            holdings_qty=holdings_qty,
            target_weight=target_weight,
        )
        _cache["data"] = data
        _cache["fetched_at"] = time.time()
        return data


def get_cash_balance() -> float:
    return db.get_cash_balance(db.get_demo_user_id())

CASH_BALANCE = get_cash_balance()