"""
Shared utilities for all optimization methods.
"""

import numpy as np
import pandas as pd

from data.mock_data import get_market_data


def expected_returns_and_cov():
    """Annualized expected returns (historical mean) and covariance matrix."""
    md = get_market_data()
    mu = md.returns.mean() * 252
    cov = md.returns.cov() * 252
    return mu, cov, md.tickers


def build_bounds(n: int, min_weight: float, max_weight: float, long_only: bool):
    lo = max(min_weight, 0.0) if long_only else -max_weight
    hi = max_weight
    return [(lo, hi) for _ in range(n)]


def weights_to_payload(tickers, weights, mu=None, cov=None):
    weights = np.clip(weights, 0, None)
    weights = weights / weights.sum() if weights.sum() > 0 else weights
    payload = [
        {"ticker": t, "weightPct": round(float(w) * 100, 2)}
        for t, w in zip(tickers, weights)
    ]
    payload.sort(key=lambda x: -x["weightPct"])

    result = {"weights": payload}
    if mu is not None and cov is not None:
        exp_return = float(weights @ mu.values)
        exp_vol = float(np.sqrt(weights @ cov.values @ weights))
        sharpe = exp_return / exp_vol if exp_vol > 0 else 0.0
        result["expectedReturnPct"] = round(exp_return * 100, 2)
        result["expectedVolatilityPct"] = round(exp_vol * 100, 2)
        result["sharpeRatio"] = round(sharpe, 3)
    return result


def efficient_frontier(mu: pd.Series, cov: pd.DataFrame, bounds, n_points: int = 12):
    """Sample the efficient frontier by sweeping target returns through min-variance QPs."""
    from scipy.optimize import minimize

    n = len(mu)
    lo_returns, hi_returns = mu.min(), mu.max()
    targets = np.linspace(lo_returns, hi_returns, n_points)

    points = []
    for target in targets:
        x0 = np.repeat(1 / n, n)
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "eq", "fun": lambda w, t=target: w @ mu.values - t},
        ]
        res = minimize(
            lambda w: w @ cov.values @ w,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 200, "ftol": 1e-9},
        )
        if res.success:
            vol = float(np.sqrt(res.x @ cov.values @ res.x))
            points.append({"returnPct": round(target * 100, 2), "volatilityPct": round(vol * 100, 2)})
    return points
