"""
Rebalance plan generation: current -> target weights, per-holding
buy/sell recommendations, and estimated turnover / transaction cost.
"""

import pandas as pd

from data.mock_data import get_market_data, CASH_BALANCE

TRANSACTION_COST_BPS = 5  # assumed round-trip cost estimate, in basis points


def generate_rebalance_plan(target_weights: dict | None = None) -> dict:
    """
    target_weights: {ticker: weight_fraction}. If None, falls back to the
    portfolio's stored target weights (from mock_data), which is what the
    frontend shows before an optimization run has been performed.
    """
    md = get_market_data()
    last_prices = md.prices.iloc[-1]

    market_values = {t: md.holdings_qty[t] * last_prices[t] for t in md.tickers}
    total_value = sum(market_values.values()) + CASH_BALANCE

    current_weights = {t: market_values[t] / total_value for t in md.tickers}
    targets = target_weights or md.target_weight

    rows = []
    total_turnover_value = 0.0
    for t in md.tickers:
        cur_w = current_weights[t]
        tgt_w = targets.get(t, cur_w)
        delta_w = tgt_w - cur_w
        delta_value = delta_w * total_value
        est_shares = delta_value / last_prices[t]

        action = "HOLD"
        if delta_w > 0.001:
            action = "BUY"
        elif delta_w < -0.001:
            action = "SELL"

        total_turnover_value += abs(delta_value)

        rows.append({
            "ticker": t,
            "action": action,
            "currentWeightPct": round(cur_w * 100, 2),
            "targetWeightPct": round(tgt_w * 100, 2),
            "deltaWeightPct": round(delta_w * 100, 2),
            "estShares": round(float(est_shares), 2),
            "estValue": round(float(delta_value), 2),
        })

    rows.sort(key=lambda r: -abs(r["deltaWeightPct"]))

    turnover_pct = total_turnover_value / total_value * 100
    est_cost = total_turnover_value * (TRANSACTION_COST_BPS / 10_000)
    trade_count = sum(1 for r in rows if r["action"] != "HOLD")

    return {
        "totalValue": round(total_value, 2),
        "holdings": rows,
        "turnoverPct": round(turnover_pct, 2),
        "estimatedCost": round(est_cost, 2),
        "tradeCount": trade_count,
    }