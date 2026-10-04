"""
Tiny in-memory store so a run of /api/optimize can feed /api/rebalance.
Fine for a single-user demo; swap for a real session/DB-backed store
once multiple users are involved.
"""

_state = {"last_optimized_weights": None}


def set_last_optimized_weights(weights: dict):
    _state["last_optimized_weights"] = weights


def get_last_optimized_weights():
    return _state["last_optimized_weights"]