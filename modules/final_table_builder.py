import os
import time
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def _safe_to_csv(df: pd.DataFrame, path: str) -> str:
    """
    Write CSV safely. If file is locked (Excel), write an alternate file.
    Returns the path that was written.
    """
    try:
        df.to_csv(path, index=False)
        return path
    except PermissionError:
        base, ext = os.path.splitext(path)
        alt = f"{base}_{int(time.time())}{ext}"
        df.to_csv(alt, index=False)
        logger.warning("File locked: %s. Wrote instead: %s", path, alt)
        return alt


def build_final_table(ipo_name: str, ipo_out_dir: str) -> pd.DataFrame:
    """
    Builds a final model-ready table by merging:
      - financials.csv
      - ratios.csv

    Writes:
      - final_table.csv (in ipo_out_dir)

    Returns:
      final_df
    """
    fin_path = os.path.join(ipo_out_dir, "financials.csv")
    ratios_path = os.path.join(ipo_out_dir, "ratios.csv")

    if not os.path.exists(fin_path):
        raise FileNotFoundError(
            f"Missing {fin_path} (run financial extractor first).")

    fin = pd.read_csv(fin_path)
    if fin.empty:
        final_df = fin.copy()
        final_df.insert(0, "IPO", ipo_name)
        out_path = os.path.join(ipo_out_dir, "final_table.csv")
        _safe_to_csv(final_df, out_path)
        return final_df

    # Ensure Year is numeric for stable merging/sorting
    fin["Year"] = pd.to_numeric(fin["Year"], errors="coerce")

    if os.path.exists(ratios_path):
        ratios = pd.read_csv(ratios_path)
        if "Year" in ratios.columns:
            ratios["Year"] = pd.to_numeric(ratios["Year"], errors="coerce")
        else:
            ratios = pd.DataFrame({"Year": fin["Year"].copy()})
    else:
        ratios = pd.DataFrame({"Year": fin["Year"].copy()})

    # Merge on Year
    final_df = pd.merge(fin, ratios, on="Year", how="left",
                        suffixes=("", "_ratio"))

    # Add IPO name as first col (useful later when stacking multiple IPOs)
    final_df.insert(0, "IPO", ipo_name)

    # Sort by Year
    if "Year" in final_df.columns:
        final_df = final_df.sort_values("Year").reset_index(drop=True)

    # (Optional) Keep only relevant columns if you want strict schema:
    preferred_order = [
        "IPO", "Year",
        "Revenue", "Profit", "TotalAssets", "TotalLiabilities", "Equity", "TotalDebt",
        "DebtEquityRatio", "NetProfitMargin", "ROA",
        "RevenueGrowth", "ProfitGrowth",
    ]
    cols = [c for c in preferred_order if c in final_df.columns] + \
        [c for c in final_df.columns if c not in preferred_order]
    final_df = final_df[cols]

    out_path = os.path.join(ipo_out_dir, "final_table.csv")
    written = _safe_to_csv(final_df, out_path)
    logger.info("Final table saved: %s", written)

    return final_df
