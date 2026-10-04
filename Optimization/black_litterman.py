"""
Simplified Black-Litterman.

No investor "views" UI exists yet, so this computes the market-implied
equilibrium returns (reverse optimization from current target weights)
and treats those as the posterior expected returns directly — this is
the neutral BL case. Wire in a views panel later to make it a true
Black-Litterman blend of prior + views.
"""

import numpy as np
from scipy.optimize import minimize

from data.mock_data import get_market_data

RISK_AVERSION = 2.5


def optimize(mu, cov, bounds, **kwargs):
    md = get_market_data()
    market_weights = np.array([md.target_weight[t] for t in cov.columns])
    market_weights = market_weights / market_weights.sum()

    # Reverse-optimize implied equilibrium returns: pi = lambda * Sigma * w_mkt
    implied_returns = RISK_AVERSION * cov.values @ market_weights

    n = len(mu)
    x0 = market_weights.copy()

    def objective(w):
        ret = w @ implied_returns
        var = w @ cov.values @ w
        return -(ret - RISK_AVERSION * var)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    res = minimize(
        objective, x0, method="SLSQP", bounds=bounds,
        constraints=constraints, options={"maxiter": 300, "ftol": 1e-9},
    )
    return res.x if res.success else x0
