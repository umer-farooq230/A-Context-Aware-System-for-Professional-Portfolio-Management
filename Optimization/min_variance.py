"""Minimum Variance optimization — minimizes portfolio variance only."""

import numpy as np
from scipy.optimize import minimize


def optimize(mu, cov, bounds, **kwargs):
    n = len(mu)
    x0 = np.repeat(1 / n, n)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    res = minimize(
        lambda w: w @ cov.values @ w,
        x0, method="SLSQP", bounds=bounds,
        constraints=constraints, options={"maxiter": 300, "ftol": 1e-9},
    )
    return res.x if res.success else x0
