"""
Risk Parity optimization — equalizes each asset's contribution to
total portfolio risk rather than equalizing capital weights.
"""

import numpy as np
from scipy.optimize import minimize


def optimize(mu, cov, bounds, **kwargs):
    n = len(mu)
    x0 = np.repeat(1 / n, n)
    target = np.repeat(1 / n, n)

    def risk_contributions(w):
        portfolio_var = w @ cov.values @ w
        marginal = cov.values @ w
        return (w * marginal) / portfolio_var

    def objective(w):
        rc = risk_contributions(w)
        return np.sum((rc - target) ** 2)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    non_negative_bounds = [(max(b[0], 1e-4), b[1]) for b in bounds]
    res = minimize(
        objective, x0, method="SLSQP", bounds=non_negative_bounds,
        constraints=constraints, options={"maxiter": 500, "ftol": 1e-12},
    )
    return res.x if res.success else x0
