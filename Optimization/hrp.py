"""
Hierarchical Risk Parity (Lopez de Prado).

Clusters assets by correlation distance, quasi-diagonalizes the
covariance matrix, then recursively bisects and allocates inverse-
variance weights within each split. Bounds are applied as a soft
clip + renormalize pass at the end (HRP doesn't natively support
box constraints).
"""

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, dendrogram
from scipy.spatial.distance import squareform


def _correl_dist(corr: pd.DataFrame) -> pd.DataFrame:
    return ((1 - corr) / 2) ** 0.5


def _quasi_diag(link) -> list:
    link = link.astype(int)
    sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
    num_items = link[-1, 3]
    while sort_ix.max() >= num_items:
        sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
        df0 = sort_ix[sort_ix >= num_items]
        i = df0.index
        j = df0.values - num_items
        sort_ix[i] = link[j, 0]
        df1 = pd.Series(link[j, 1], index=i + 1)
        sort_ix = pd.concat([sort_ix, df1]).sort_index()
        sort_ix.index = range(sort_ix.shape[0])
    return sort_ix.tolist()


def _cluster_var(cov: pd.DataFrame, items: list) -> float:
    sub = cov.loc[items, items]
    ivp = 1 / np.diag(sub)
    ivp /= ivp.sum()
    return float(ivp @ sub.values @ ivp)


def _recursive_bisection(cov: pd.DataFrame, sort_ix: list) -> pd.Series:
    weights = pd.Series(1.0, index=sort_ix)
    clusters = [sort_ix]
    while clusters:
        clusters = [c[i:j] for c in clusters for i, j in
                    ((0, len(c) // 2), (len(c) // 2, len(c))) if len(c) > 0]
        clusters = [c for c in clusters if len(c) > 0]
        for i in range(0, len(clusters), 2):
            if i + 1 >= len(clusters):
                continue
            c0, c1 = clusters[i], clusters[i + 1]
            var0, var1 = _cluster_var(cov, c0), _cluster_var(cov, c1)
            alpha = 1 - var0 / (var0 + var1)
            weights[c0] *= alpha
            weights[c1] *= (1 - alpha)
        clusters = [c for c in clusters if len(c) > 1]
    return weights


def optimize(mu, cov, bounds, **kwargs):
    tickers = list(cov.columns)
    corr = cov.copy()
    std = np.sqrt(np.diag(cov.values))
    corr = cov.values / np.outer(std, std)
    corr_df = pd.DataFrame(corr, index=tickers, columns=tickers)

    dist = _correl_dist(corr_df)
    condensed = squareform(dist.values, checks=False)
    link = linkage(condensed, method="single")
    sort_ix = _quasi_diag(link)
    sorted_tickers = [tickers[i] for i in sort_ix]

    hrp_weights = _recursive_bisection(cov, sorted_tickers)
    hrp_weights = hrp_weights.reindex(tickers).values

    # Soft-apply box constraints (clip then renormalize) since HRP has no
    # native constraint mechanism.
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])
    clipped = np.clip(hrp_weights, lo, hi)
    clipped = clipped / clipped.sum()
    return clipped
