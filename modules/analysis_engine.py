import os
import numpy as np
import pandas as pd


def _ensure_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Ensure columns exist and are numeric (coerce invalid to NaN).
    """
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def compute_financial_ratios(df: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """
    Compute financial ratios safely.

    Expected (if available):
      Year, Revenue, Profit, TotalAssets, TotalLiabilities, Equity, TotalDebt

    Writes:
      output_dir/ratios.csv
    """
    os.makedirs(output_dir, exist_ok=True)

    if df is None or df.empty:
        # still write an empty ratios file so pipeline doesn't break
        out = pd.DataFrame(columns=[
            "Year",
            "Revenue", "Profit", "TotalAssets", "TotalLiabilities", "Equity", "TotalDebt",
            "DebtEquityRatio", "NetProfitMargin", "ROA", "RevenueGrowth", "ProfitGrowth"
        ])
        out.to_csv(os.path.join(output_dir, "ratios.csv"), index=False)
        return out

    # Work on a copy (avoid SettingWithCopy surprises)
    df = df.copy()

    # Ensure key columns exist + numeric
    numeric_cols = ["Revenue", "Profit", "TotalAssets",
                    "TotalLiabilities", "Equity", "TotalDebt"]
    df = _ensure_numeric(df, numeric_cols)

    # Ensure Year exists
    if "Year" not in df.columns:
        df["Year"] = np.nan

    # Sort by Year for growth calcs
    try:
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        df = df.sort_values("Year").reset_index(drop=True)
    except Exception:
        pass

    # -----------------------------
    # Debt to Equity Ratio
    # -----------------------------
    # Only valid when Equity > 0 and both are present
    df["DebtEquityRatio"] = np.where(
        (df["Equity"].isna()) | (df["Equity"] <= 0) | (df["TotalDebt"].isna()),
        np.nan,
        df["TotalDebt"] / df["Equity"]
    )

    # -----------------------------
    # Net Profit Margin (%)
    # -----------------------------
    df["NetProfitMargin"] = np.where(
        (df["Revenue"].isna()) | (df["Revenue"] == 0) | (df["Profit"].isna()),
        np.nan,
        (df["Profit"] / df["Revenue"]) * 100.0
    )

    # -----------------------------
    # Return on Assets (ROA) (%)
    # -----------------------------
    df["ROA"] = np.where(
        (df["TotalAssets"].isna()) | (
            df["TotalAssets"] == 0) | (df["Profit"].isna()),
        np.nan,
        (df["Profit"] / df["TotalAssets"]) * 100.0
    )

    # -----------------------------
    # Growth (%): Revenue and Profit
    # - fill_method=None avoids the FutureWarning
    # -----------------------------
    df["RevenueGrowth"] = df["Revenue"].pct_change(fill_method=None) * 100.0
    df["ProfitGrowth"] = df["Profit"].pct_change(fill_method=None) * 100.0

    # -----------------------------
    # Save output
    # -----------------------------
    output_path = os.path.join(output_dir, "ratios.csv")
    df.to_csv(output_path, index=False)

    return df
