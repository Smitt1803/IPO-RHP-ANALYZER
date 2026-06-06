import os
import time
import logging
import pandas as pd
import numpy as np

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


def _list_ipo_dirs(processed_root: str) -> list[str]:
    if not os.path.exists(processed_root):
        return []
    return sorted(
        os.path.join(processed_root, d)
        for d in os.listdir(processed_root)
        if os.path.isdir(os.path.join(processed_root, d))
    )


def build_comparison(processed_root: str, output_dir: str, years_window: int = 3) -> pd.DataFrame:
    """
    Builds comparison datasets from each IPO's final_table.csv.

    Outputs:
      - output_dir/master_final_table_by_year.csv   (all IPOs x years)
      - output_dir/ipo_summary_for_scoring.csv      (1 row per IPO)

    Returns:
      summary_df (1 row per IPO) for scoring.
    """
    os.makedirs(output_dir, exist_ok=True)

    ipo_dirs = _list_ipo_dirs(processed_root)
    if not ipo_dirs:
        logger.warning("No IPO directories found in %s", processed_root)
        return pd.DataFrame()

    all_year_rows = []
    summary_rows = []

    for ipo_dir in ipo_dirs:
        ipo_name = os.path.basename(ipo_dir)
        final_path = os.path.join(ipo_dir, "final_table.csv")
        if not os.path.exists(final_path):
            continue

        try:
            df = pd.read_csv(final_path)
        except Exception as e:
            logger.warning("Failed reading %s: %s", final_path, e)
            continue

        if df.empty:
            continue

        if "IPO" not in df.columns:
            df.insert(0, "IPO", ipo_name)
        else:
            df["IPO"] = df["IPO"].fillna(ipo_name)

        # ensure Year numeric and sorted
        if "Year" in df.columns:
            df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
            df = df.sort_values("Year").reset_index(drop=True)

        all_year_rows.append(df)

        # ---- Build 1-row summary for scoring ----
        # Use latest year row for most metrics + mean of last N years for stability
        if "Year" in df.columns and df["Year"].notna().any():
            latest_year = int(df["Year"].dropna().max())
            latest = df[df["Year"] == latest_year].tail(1)
        else:
            latest_year = None
            latest = df.tail(1)

        tail = df.tail(years_window)

        def latest_val(col: str):
            return latest[col].iloc[0] if (col in latest.columns and not latest.empty) else np.nan

        def mean_val(col: str):
            if col not in tail.columns:
                return np.nan
            return pd.to_numeric(tail[col], errors="coerce").mean()

        row = {
            "IPO": ipo_name,
            "LatestYear": latest_year,

            # Latest values
            "NetProfitMargin": latest_val("NetProfitMargin"),
            "ROA": latest_val("ROA"),
            "DebtEquityRatio": latest_val("DebtEquityRatio"),
            "RevenueGrowth": latest_val("RevenueGrowth"),
            "ProfitGrowth": latest_val("ProfitGrowth"),

            # Rolling averages (last N years)
            "NetProfitMargin_avg": mean_val("NetProfitMargin"),
            "ROA_avg": mean_val("ROA"),
            "DebtEquityRatio_avg": mean_val("DebtEquityRatio"),
            "RevenueGrowth_avg": mean_val("RevenueGrowth"),
            "ProfitGrowth_avg": mean_val("ProfitGrowth"),
        }
        summary_rows.append(row)

    if not all_year_rows:
        logger.warning("No final_table.csv found under %s", processed_root)
        return pd.DataFrame()

    master_by_year = pd.concat(all_year_rows, ignore_index=True)
    out1 = os.path.join(output_dir, "master_final_table_by_year.csv")
    _safe_to_csv(master_by_year, out1)
    logger.info("Saved: %s", out1)

    summary_df = pd.DataFrame(summary_rows)
    out2 = os.path.join(output_dir, "ipo_summary_for_scoring.csv")
    _safe_to_csv(summary_df, out2)
    logger.info("Saved: %s", out2)

    return summary_df
