"""
Mean-Variance (Markowitz) optimization.

Maximizes a risk-adjusted objective (return - risk_aversion * variance)
subject to weight bounds and a fully-invested constraint. `risk_aversion`
is derived from the requested risk profile.
"""

import numpy as np
from scipy.optimize import minimize

RISK_AVERSION_BY_PROFILE = {
    "Conservative": 6.0,
    "Moderate": 3.0,
    "Aggressive": 1.2,
}


def optimize(mu, cov, bounds, risk_profile: str = "Moderate", **kwargs):
    n = len(mu)
    risk_aversion = RISK_AVERSION_BY_PROFILE.get(risk_profile, 3.0)
    x0 = np.repeat(1 / n, n)

    def objective(w):
        ret = w @ mu.values
        var = w @ cov.values @ w
        return -(ret - risk_aversion * var)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    res = minimize(
        objective, x0, method="SLSQP", bounds=bounds,
        constraints=constraints, options={"maxiter": 300, "ftol": 1e-9},
    )
    return res.x if res.success else x0
