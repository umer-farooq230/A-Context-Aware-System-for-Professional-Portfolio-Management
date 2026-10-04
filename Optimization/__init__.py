from Optimization import (
    mean_variance,
    min_variance,
    max_sharpe,
    risk_parity,
    hrp,
    black_litterman,
)
from Optimization.base import (
    expected_returns_and_cov,
    build_bounds,
    weights_to_payload,
    efficient_frontier,
)

METHOD_MAP = {
    "Mean-Variance (Markowitz)": mean_variance.optimize,
    "Minimum Variance": min_variance.optimize,
    "Maximum Sharpe Ratio": max_sharpe.optimize,
    "Risk Parity": risk_parity.optimize,
    "Black-Litterman": black_litterman.optimize,
    "Hierarchical Risk Parity (HRP)": hrp.optimize,
}


def run_optimization(method: str, risk_profile: str, min_weight: float,
                      max_weight: float, long_only: bool):
    mu, cov, tickers = expected_returns_and_cov()
    bounds = build_bounds(len(tickers), min_weight / 100, max_weight / 100, long_only)

    fn = METHOD_MAP.get(method, mean_variance.optimize)
    weights = fn(mu, cov, bounds, risk_profile=risk_profile)

    payload = weights_to_payload(tickers, weights, mu, cov)
    payload["method"] = method
    payload["frontier"] = efficient_frontier(mu, cov, bounds)
    return payload