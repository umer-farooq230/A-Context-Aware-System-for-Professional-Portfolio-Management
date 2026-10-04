
import numpy as np
import pandas as pd

from data.mock_data import get_market_data

CONFIDENCE = 0.95


def _current_weights() -> pd.Series:
    md = get_market_data()
    last_prices = md.prices.iloc[-1]
    values = pd.Series({t: md.holdings_qty[t] * last_prices[t] for t in md.tickers})
    return values / values.sum()


def get_risk_metrics() -> dict:
    md = get_market_data()
    weights = _current_weights()
    returns = md.returns[weights.index]
    cov = returns.cov() * 252

    port_returns = returns @ weights  # daily portfolio return series
    ann_vol = float(port_returns.std() * np.sqrt(252) * 100)

    # Historical simulation VaR / CVaR (1-day, 95%)
    var_1d = float(np.percentile(port_returns, (1 - CONFIDENCE) * 100))
    tail_losses = port_returns[port_returns <= var_1d]
    cvar_1d = float(tail_losses.mean()) if len(tail_losses) else var_1d

    # Correlation matrix
    corr = returns.corr()
    correlation_matrix = {
        "tickers": list(corr.columns),
        "matrix": [[round(float(v), 3) for v in row] for row in corr.values],
    }

    # Volatility contribution per holding: w_i * (Cov w)_i / portfolio_var
    port_var = weights.values @ cov.values @ weights.values
    marginal = cov.values @ weights.values
    contrib = weights.values * marginal / port_var
    vol_contribution = sorted(
        [
            {"ticker": t, "contributionPct": round(float(c) * 100, 2)}
            for t, c in zip(weights.index, contrib)
        ],
        key=lambda x: -x["contributionPct"],
    )

    # Histogram of the simulated (historical) daily portfolio return distribution
    counts, edges = np.histogram(port_returns * 100, bins=24)
    histogram = [
        {"binStart": round(float(edges[i]), 2), "binEnd": round(float(edges[i + 1]), 2),
         "count": int(counts[i])}
        for i in range(len(counts))
    ]

    return {
        "volatilityPct": round(ann_vol, 2),
        "var95Pct": round(var_1d * 100, 2),
        "cvar95Pct": round(cvar_1d * 100, 2),
        "correlationMatrix": correlation_matrix,
        "volatilityContribution": vol_contribution,
        "returnDistribution": histogram,
    }