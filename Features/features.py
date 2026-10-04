"""
Feature computation for the Dashboard and Portfolio views:
total value, P&L, return, volatility, drawdown, holdings, allocation,
current vs target weights.
"""

import numpy as np
import pandas as pd

from data.mock_data import get_market_data, CASH_BALANCE

def _portfolio_value_series() -> pd.Series:
    md = get_market_data()
    qty = pd.Series(md.holdings_qty)
    values = md.prices[qty.index].mul(qty, axis=1).sum(axis=1) + CASH_BALANCE
    return values


def _max_drawdown(value_series: pd.Series):
    running_max = value_series.cummax()
    drawdown = value_series / running_max - 1
    trough_idx = drawdown.idxmin()
    peak_idx = value_series.loc[:trough_idx].idxmax()
    return float(drawdown.min()), peak_idx, trough_idx, drawdown


def get_dashboard_metrics() -> dict:
    md = get_market_data()
    values = _portfolio_value_series()

    total_value = float(values.iloc[-1])
    prev_value = float(values.iloc[-2])
    day_change_pct = (total_value / prev_value - 1) * 100

    start_value = float(values.iloc[0])
    pnl = total_value - start_value
    pnl_pct = (total_value / start_value - 1) * 100

    ytd_start = values[values.index >= pd.Timestamp(pd.Timestamp.today().year, 1, 1)]
    if len(ytd_start) > 1:
        return_ytd = (values.iloc[-1] / ytd_start.iloc[0] - 1) * 100
    else:
        return_ytd = pnl_pct

    daily_rets = values.pct_change().dropna()
    volatility_ann = float(daily_rets.std() * np.sqrt(252) * 100)

    max_dd, peak_idx, trough_idx, dd_series = _max_drawdown(values)

    cutoff = values.index[-1] - pd.Timedelta(days=180)
    six_m = values[values.index >= cutoff]

    return {
        "totalValue": round(total_value, 2),
        "totalValueDeltaPct": round(day_change_pct, 2),
        "pnl": round(pnl, 2),
        "pnlPct": round(pnl_pct, 2),
        "returnYtdPct": round(return_ytd, 2),
        "benchmarkYtdPct": 8.9,  # placeholder benchmark until a real index feed is wired up
        "volatilityPct": round(volatility_ann, 2),
        "maxDrawdownPct": round(max_dd * 100, 2),
        "drawdownWindow": f"{peak_idx.date()} – {trough_idx.date()}",
        "valueSeries": [
            {"date": str(d.date()), "value": round(v, 2)} for d, v in six_m.items()
        ],
        "drawdownSeries": [
            {"date": str(d.date()), "value": round(v * 100, 2)}
            for d, v in dd_series[dd_series.index >= cutoff].items()
        ],
    }


def get_portfolio_holdings() -> dict:
    md = get_market_data()
    last_prices = md.prices.iloc[-1]

    market_values = {t: md.holdings_qty[t] * last_prices[t] for t in md.tickers}
    total_holdings_value = sum(market_values.values())
    total_value = total_holdings_value + CASH_BALANCE

    holdings = []
    for t in md.tickers:
        mv = market_values[t]
        holdings.append({
            "ticker": t,
            "name": md.names[t],
            "assetClass": md.asset_class[t],
            "qty": md.holdings_qty[t],
            "price": round(float(last_prices[t]), 2),
            "marketValue": round(mv, 2),
            "currentWeightPct": round(mv / total_value * 100, 2),
            "targetWeightPct": round(md.target_weight[t] * 100, 2),
        })

    alloc = {}
    for t in md.tickers:
        ac = md.asset_class[t]
        alloc[ac] = alloc.get(ac, 0) + market_values[t]
    alloc["Cash"] = CASH_BALANCE
    allocation = [
        {"assetClass": k, "value": round(v, 2), "weightPct": round(v / total_value * 100, 2)}
        for k, v in sorted(alloc.items(), key=lambda x: -x[1])
    ]

    return {
        "totalValue": round(total_value, 2),
        "cashBalance": round(CASH_BALANCE, 2),
        "cashWeightPct": round(CASH_BALANCE / total_value * 100, 2),
        "holdings": holdings,
        "allocationByAssetClass": allocation,
    }