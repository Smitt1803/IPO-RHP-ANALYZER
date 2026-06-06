import os
import time
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _safe_to_csv(df: pd.DataFrame, path: str) -> str:
    try:
        df.to_csv(path, index=False)
        return path
    except PermissionError:
        base, ext = os.path.splitext(path)
        alt = f"{base}_{int(time.time())}{ext}"
        df.to_csv(alt, index=False)
        logger.warning("File locked: %s. Wrote instead: %s", path, alt)
        return alt


def add_scores_to_comparison(comparison_df: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """
    Composite score using last-3-year averages (preferred):
      Score = 0.30*Margin + 0.25*ROA + 0.15*RevGrowth + 0.10*ProfitGrowth - 0.20*DebtEquity

    Also:
      - fills missing with 0
      - clips outliers (5th-95th)
      - assigns category labels by quantiles
    """
    os.makedirs(output_dir, exist_ok=True)

    df = comparison_df.copy()
    if df.empty:
        logger.warning("Empty comparison dataframe passed.")
        return df

    # Prefer avg columns if present
    margin_col = "NetProfitMargin_avg" if "NetProfitMargin_avg" in df.columns else "NetProfitMargin"
    roa_col = "ROA_avg" if "ROA_avg" in df.columns else "ROA"
    de_col = "DebtEquityRatio_avg" if "DebtEquityRatio_avg" in df.columns else "DebtEquityRatio"
    revg_col = "RevenueGrowth_avg" if "RevenueGrowth_avg" in df.columns else "RevenueGrowth"
    profg_col = "ProfitGrowth_avg" if "ProfitGrowth_avg" in df.columns else "ProfitGrowth"

    used_cols = [margin_col, roa_col, de_col, revg_col, profg_col]

    # Ensure cols exist + numeric + fill NaN with 0
    for col in used_cols:
        if col not in df.columns:
            logger.warning("%s missing; defaulting 0 for scoring", col)
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Clip outliers
    for col in used_cols:
        lower = np.percentile(df[col], 5)
        upper = np.percentile(df[col], 95)
        df[col] = df[col].clip(lower, upper)

    # Weights (B + growth)
    W_MARGIN = 0.30
    W_ROA = 0.25
    W_REVG = 0.15
    W_PROFG = 0.10
    W_DE = -0.20

    df["CompositeScore"] = (
        W_MARGIN * df[margin_col]
        + W_ROA * df[roa_col]
        + W_REVG * df[revg_col]
        + W_PROFG * df[profg_col]
        + W_DE * df[de_col]
    )

    df["Rank"] = df["CompositeScore"].rank(
        ascending=False, method="min").astype(int)

    # Category bands (quantiles)
    q70 = df["CompositeScore"].quantile(0.70)
    q30 = df["CompositeScore"].quantile(0.30)

    def label(x: float) -> str:
        if x >= q70:
            return "Better"
        if x <= q30:
            return "Not Recommended"
        return "Moderate"

    df["Category"] = df["CompositeScore"].map(label)

    out_path = os.path.join(output_dir, "scored_ipo_comparison.csv")
    _safe_to_csv(df.sort_values("Rank"), out_path)
    logger.info("Scored IPO comparison saved: %s", out_path)

    # (Optional) save weights used
    weights_path = os.path.join(output_dir, "scoring_weights_used.txt")
    try:
        with open(weights_path, "w", encoding="utf-8") as f:
            f.write(
                f"Used columns: {used_cols}\n"
                f"Weights: Margin={W_MARGIN}, ROA={W_ROA}, RevenueGrowth={W_REVG}, ProfitGrowth={W_PROFG}, DebtEquity={W_DE}\n"
                f"Outlier clipping: 5th-95th percentile\n"
            )
    except PermissionError:
        pass

    return df
