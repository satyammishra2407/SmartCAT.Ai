"""Parse RMS/AIR EP curve or loss CSV outputs."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from smartcat_logging import get_logger

logger = get_logger("module6.parser")


def load_ep_curve(path: Path) -> pd.DataFrame:
    """Accept common column variants."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    cols = {c.lower().strip(): c for c in df.columns}
    rename = {}
    for target, aliases in [
        ("rp", ["return_period", "return period", "rp", "year"]),
        ("oep", ["oep", "occurrence ep", "occurrence"]),
        ("aep", ["aep", "aggregate ep", "aggregate"]),
        ("loss", ["loss", "severity", "ground_up_loss", "gu loss"]),
    ]:
        for a in aliases:
            if a in cols:
                rename[cols[a]] = target.upper() if target != "loss" else "LOSS"
                break

    df = df.rename(columns=rename)
    logger.info("Parsed columns: %s", list(df.columns))
    return df


def load_elt_stub(path: Path) -> pd.DataFrame:
    """Minimal ELT reader — expects EventID, Rate, Loss columns if present."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)
