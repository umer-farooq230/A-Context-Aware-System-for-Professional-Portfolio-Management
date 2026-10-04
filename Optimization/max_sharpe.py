"""Maximum Sharpe Ratio optimization (tangency portfolio)."""

import numpy as np
from scipy.optimize import minimize

RISK_FREE_RATE = 0.045


def optimize(mu, cov, bounds, **kwargs):
    n = len(mu)
    x0 = np.repeat(1 / n, n)

    def neg_sharpe(w):
        ret = w @ mu.values - RISK_FREE_RATE
        vol = np.sqrt(w @ cov.values @ w)
        return -(ret / vol) if vol > 0 else 1e6

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    res = minimize(
        neg_sharpe, x0, method="SLSQP", bounds=bounds,
        constraints=constraints, options={"maxiter": 300, "ftol": 1e-9},
    )
    return res.x if res.success else x0
