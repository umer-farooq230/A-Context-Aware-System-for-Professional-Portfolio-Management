import numpy as np


def build_features(df):
    out = df.copy()

    r = np.log(out["close"]).diff()

    out["return_1d"] = r
    out["return_5d"] = np.log(out["close"]).diff(5)
    out["return_22d"] = np.log(out["close"]).diff(22)
    out["return_63d"] = np.log(out["close"]).diff(63)

    out["vol_1d"] = r.abs()
    out["vol_5d"] = r.rolling(5).std() * np.sqrt(5)
    out["vol_22d"] = r.rolling(22).std() * np.sqrt(22)

    negative = r.where(r < 0, 0.0)

    out["downside_vol"] = (np.sqrt((negative ** 2).rolling(22).mean()) * np.sqrt(252))

    out["vol_timing"] = (out["vol_5d"] / (out["vol_22d"] + 1e-12))

    rolling_max = out["close"].rolling(252).max()
    out["drawdown"] = (out["close"] / rolling_max - 1)

    out["momentum_22d"] = (out["close"] / out["close"].shift(22) - 1)

    out["momentum_63d"] = (out["close"] / out["close"].shift(63) - 1)

    if "volume" in out.columns:
        out["volume_ma_22d"] = (out["volume"].rolling(22).mean())

        out["volume_ratio"] = (out["volume"] / (out["volume_ma_22d"] + 1e-12))

    out = out.replace([np.inf, -np.inf], np.nan)

    return out