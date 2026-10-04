"""
SEC EDGAR client for recent filings (10-K, 10-Q, 8-K) per ticker.
Free, no key — just requires a real contact in the User-Agent per SEC's
fair-access policy.
"""
import time
import threading
import requests

USER_AGENT = "Portfolio Optimization App umerfarooq230@gmail.com"  # <-- put a real contact
HEADERS = {"User-Agent": USER_AGENT}

CACHE_TTL_SECONDS = 60 * 60 * 12
FORMS_OF_INTEREST = {"10-K", "10-Q", "8-K"}
MAX_FILINGS_PER_TICKER = 3

_lock = threading.Lock()
_ticker_to_cik: dict | None = None
_filing_cache: dict = {}


def _load_ticker_to_cik() -> dict:
    global _ticker_to_cik
    if _ticker_to_cik is not None:
        return _ticker_to_cik
    resp = requests.get("https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    raw = resp.json()
    _ticker_to_cik = {e["ticker"].upper(): str(e["cik_str"]).zfill(10) for e in raw.values()}
    return _ticker_to_cik


def get_recent_filings(ticker: str) -> list[dict]:
    base_ticker = ticker.split("-")[0]  # strips "-USD" for crypto (which won't be found anyway)

    with _lock:
        entry = _filing_cache.get(base_ticker)
        if entry and (time.time() - entry[0]) < CACHE_TTL_SECONDS:
            return entry[1]

    try:
        cik = _load_ticker_to_cik().get(base_ticker)
        if not cik:
            return []  # not SEC-registered (e.g. crypto)
        resp = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"SEC EDGAR request failed for {ticker}: {exc}")
        return []

    recent = data.get("filings", {}).get("recent", {})
    filings = []
    for form, date, accession, doc in zip(
        recent.get("form", []), recent.get("filingDate", []),
        recent.get("accessionNumber", []), recent.get("primaryDocument", []),
    ):
        if form not in FORMS_OF_INTEREST:
            continue
        acc_nodash = accession.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{doc}"
        filings.append({"form": form, "date": date, "url": url})
        if len(filings) >= MAX_FILINGS_PER_TICKER:
            break

    with _lock:
        _filing_cache[base_ticker] = (time.time(), filings)
    return filings