"""Matplotlib charts for OEP vs AEP."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_oep_aep(rp_table: pd.DataFrame, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    if "Loss_OEP" in rp_table.columns:
        ax.plot(rp_table["ReturnPeriod"], rp_table["Loss_OEP"], marker="o", label="OEP")
    if "Loss_AEP" in rp_table.columns:
        ax.plot(rp_table["ReturnPeriod"], rp_table["Loss_AEP"], marker="s", label="AEP")
    ax.set_xscale("log")
    ax.set_xlabel("Return period (years)")
    ax.set_ylabel("Loss")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
