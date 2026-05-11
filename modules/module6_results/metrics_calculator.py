"""AAL, OEP/AEP metrics, return period table."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from smartcat_logging import get_logger

logger = get_logger("module6.metrics")


def interpolate_loss_at_rp(df: pd.DataFrame, target_rp: float, rp_col: str, loss_col: str) -> float:
    sub = df[[rp_col, loss_col]].dropna().sort_values(rp_col)
    if sub.empty or len(sub) < 2:
        return float("nan")
    rps = sub[rp_col].astype(float).values
    losses = sub[loss_col].astype(float).values
    if np.any(rps <= 0):
        return float(np.interp(target_rp, rps, losses))
    return float(np.interp(np.log(target_rp), np.log(rps), losses))


def build_return_period_table(df: pd.DataFrame, rps: list[float] | None = None) -> pd.DataFrame:
    rps = rps or [50, 100, 250, 500, 1000]
    rp_col = "RP" if "RP" in df.columns else str(df.columns[0])
    rows: list[dict[str, Any]] = []

    for rp in rps:
        row: dict[str, Any] = {"ReturnPeriod": rp}
        if "OEP" in df.columns:
            row["Loss_OEP"] = interpolate_loss_at_rp(df, rp, rp_col, "OEP")
        elif "LOSS" in df.columns:
            row["Loss_OEP"] = interpolate_loss_at_rp(df, rp, rp_col, "LOSS")
        else:
            row["Loss_OEP"] = float("nan")

        if "AEP" in df.columns:
            row["Loss_AEP"] = interpolate_loss_at_rp(df, rp, rp_col, "AEP")
        else:
            row["Loss_AEP"] = float("nan")
        rows.append(row)

    return pd.DataFrame(rows)


def summarize_distribution(losses: pd.Series) -> dict[str, float]:
    x = pd.to_numeric(losses, errors="coerce").dropna()
    if x.empty:
        return {"aal": float("nan"), "std": float("nan"), "cv": float("nan")}
    mean = float(x.mean())
    std = float(x.std(ddof=1)) if len(x) > 1 else 0.0
    cv = float(std / mean) if mean else float("nan")
    return {"aal": mean, "std": std, "cv": cv}


def metrics_from_ep(df: pd.DataFrame) -> dict[str, Any]:
    loss_col = None
    for c in df.columns:
        if str(c).upper() in ("LOSS", "OEP"):
            loss_col = c
            break
    if loss_col is None:
        loss_col = df.columns[-1]
    stats = summarize_distribution(df[loss_col])
    rp_tbl = build_return_period_table(df)
    logger.info("Computed metrics AAL=%s CV=%s", stats["aal"], stats["cv"])
    return {"stats": stats, "return_period_table": rp_tbl}
