import os
import re
import glob
import logging
from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from modules.utils import safe_mkdir, normalize_text, parse_number, choose_last_n_years, to_json

logger = logging.getLogger(__name__)

YEAR_RE = re.compile(r"\b(20\d{2})\b")

METRIC_SYNONYMS: dict[str, list[str]] = {
    "revenue": [
        "revenue from operations", "income from operations", "revenue", "total revenue", "total income"
    ],
    "profit": [
        "profit after tax", "profit for the year", "net profit", "pat", "profit/(loss) for the year"
    ],
    "total_assets": [
        "total assets", "total of assets"
    ],
    "total_liabilities": [
        "total liabilities",
        "total of liabilities"
        "total liabilities (b)",
        "total liabilities (c)",
        "total liabilities and provisions",
        "total liabilities (a)",

        # sometimes they write:
        "total liabilities excluding equity",
        "total liabilities excluding shareholders funds",
    ],
    "equity": [
        "total equity",
        "total shareholders' funds",
        "shareholders funds",
        "shareholders' funds",
        "owners' equity",
        "owners equity",
        "equity attributable to owners",
        "net worth",                     # in many RHPs equity is presented as net worth
        "total equity (a)",
    ],
    "total_debt": [
        "borrowings",
        "total borrowings",
        "total debt",
        "total loans",
        "loans and borrowings",
        "non-current borrowings",
        "current borrowings",
        "short-term borrowings",
        "long-term borrowings",
    ],

}

BIG_METRICS = {"revenue", "total_assets",
               "total_liabilities", "equity", "total_debt"}

MIN_MATCH = 0.78  # lowered because labels vary a lot in RHPs


@dataclass
class Hit:
    metric: str
    year: int
    value: float | None
    file: str
    row_label: str
    score: float


def _read_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    df = df.apply(lambda col: col.map(
        lambda x: x.strip() if isinstance(x, str) else x))
    df = df.replace("", pd.NA).dropna(how="all").fillna("")
    return df


def _infer_label_col(df: pd.DataFrame, max_cols: int = 3) -> int:
    """
    RHP tables often have:
      col0 = note no / sr no
      col1 = particulars (labels)
    So pick the column among first few columns with highest alphabetic density.
    """
    best_c = 0
    best = -1.0
    for c in range(min(max_cols, df.shape[1])):
        col = df.iloc[:50, c].astype(str).tolist()
        alpha = 0
        total = 0
        for x in col:
            s = normalize_text(x)
            if not s:
                continue
            total += 1
            if any(ch.isalpha() for ch in s):
                alpha += 1
        score = alpha / max(1, total)
        if score > best:
            best = score
            best_c = c
    return best_c


def _detect_year_cols(df: pd.DataFrame) -> dict[int, int]:
    """
    Look in top rows for 20xx tokens; map year->column index.
    """
    year_to_col: dict[int, int] = {}
    for r in range(min(10, df.shape[0])):
        row = df.iloc[r].astype(str).tolist()
        for c, cell in enumerate(row):
            s = str(cell)
            for y in YEAR_RE.findall(s.replace("FY", " ")):
                year_to_col[int(y)] = c
    return year_to_col


def _match_metric(label: str) -> tuple[str | None, float]:
    nl = normalize_text(label)
    if not nl:
        return None, 0.0
    best_m = None
    best_s = 0.0
    for m, syns in METRIC_SYNONYMS.items():
        for s in syns:
            sc = fuzz.partial_ratio(normalize_text(s), nl) / 100.0
            if sc > best_s:
                best_s = sc
                best_m = m
    return best_m, best_s


def _reconstruct_number(row: list[str], col: int, hops: int = 5) -> float | None:
    """
    If pdf split 1,28,000 into pieces across adjacent cells, join them.
    """
    parts = []
    for j in range(col, min(len(row), col + hops)):
        cell = str(row[j]).strip()
        if not cell:
            if parts:
                break
            continue
        # stop if cell has letters (likely not numeric fragment)
        if any(ch.isalpha() for ch in cell):
            break
        parts.append(cell)
    if not parts:
        return None
    joined = "".join(parts).replace(" ", "").replace(",,", ",")
    return parse_number(joined)


def _extract_hits_from_table(df: pd.DataFrame, file_path: str) -> list[Hit]:
    hits: list[Hit] = []
    if df.shape[0] < 2 or df.shape[1] < 2:
        return hits

    label_col = _infer_label_col(df)

    year_to_col = _detect_year_cols(df)
    if not year_to_col:
        return hits

    years = sorted(year_to_col.keys())
    year_bonus = min(1.0, len(years) / 3.0)  # 1.0 if 3+ years, else smaller

    # Iterate rows and try to pick metric rows
    for r in range(df.shape[0]):
        row = df.iloc[r].astype(str).tolist()

        label = str(row[label_col]).strip() if label_col < len(row) else ""
        metric, mscore = _match_metric(label)
        if not metric or mscore < MIN_MATCH:
            continue

        for year, col in year_to_col.items():
            if col >= len(row):
                continue

            raw = str(row[col]).strip()
            val = parse_number(raw)

            # Attempt reconstruction if value missing or looks like a split fragment
            if val is None or (metric in BIG_METRICS and val is not None and abs(val) < 100):
                rebuilt = _reconstruct_number(row, col, hops=6)
                if rebuilt is not None:
                    # Replace if val was None OR rebuilt is clearly more plausible
                    if val is None:
                        val = rebuilt
                    else:
                        if abs(rebuilt) >= 100 and abs(rebuilt) >= 10 * abs(val):
                            val = rebuilt

            # Build a hit score: label match dominates; year presence helps
            score = float(mscore + 0.35 * year_bonus +
                          (0.15 if val is not None else 0.0))

            hits.append(Hit(
                metric=metric,
                year=int(year),
                value=val,
                file=file_path,
                row_label=label,
                score=score,
            ))

    return hits


def _choose_best_hits(all_hits: list[Hit]) -> dict[tuple[str, int], Hit]:
    """
    Pick the best hit per (metric, year) by max score.
    """
    chosen: dict[tuple[str, int], Hit] = {}
    for h in all_hits:
        k = (h.metric, h.year)
        if k not in chosen or h.score > chosen[k].score:
            chosen[k] = h
    return chosen


def _load_candidate_tables(output_dir: str) -> list[str]:
    """
    Prefer stitched tables. If not present, fall back to dumped tables.
    Returns list of CSV paths.
    """
    stitched_dir = os.path.join(output_dir, "stitched_tables")
    dumped_dir = os.path.join(output_dir, "dumped_tables")

    stitched = sorted(glob.glob(os.path.join(
        stitched_dir, "stitched_group_*.csv")))
    if stitched:
        return stitched

    dumped = sorted(glob.glob(os.path.join(dumped_dir, "page_*_table_*.csv")))
    return dumped


def extract_financials(
    pdf_path: str,
    focus_pages: list[int],
    output_dir: str,
    years_back: int = 3,
    min_table_rows: int = 3,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Extract structured financials (Revenue, Profit, TotalAssets, TotalLiabilities, Equity, TotalDebt)
    by scanning stitched tables first (then dumped tables as fallback).
    """
    safe_mkdir(output_dir)

    debug: dict[str, Any] = {
        "pdf": os.path.basename(pdf_path),
        "focus_pages": focus_pages,
        "candidate_files": [],
        "hits_total": 0,
        "chosen": {},
        "liabilities_fallback_used": False,
    }

    candidate_files = _load_candidate_tables(output_dir)
    debug["candidate_files"] = candidate_files

    all_hits: list[Hit] = []
    for fpath in candidate_files:
        try:
            df = _read_csv(fpath)
        except Exception as e:
            logger.warning("Failed reading table csv %s: %s", fpath, e)
            continue

        if df.shape[0] < min_table_rows or df.shape[1] < 2:
            continue

        hits = _extract_hits_from_table(df, fpath)
        all_hits.extend(hits)

    debug["hits_total"] = len(all_hits)

    if not all_hits:
        logger.warning(
            "No financial rows extracted — creating empty dataframe")
        empty = pd.DataFrame(columns=[
            "Year", "Revenue", "Profit", "TotalAssets", "TotalLiabilities", "Equity", "TotalDebt"
        ])
        out_csv = os.path.join(output_dir, "financials.csv")
        empty.to_csv(out_csv, index=False)
        with open(os.path.join(output_dir, "financials_debug.json"), "w", encoding="utf-8") as f:
            f.write(to_json(debug))
        return empty, debug

    chosen = _choose_best_hits(all_hits)
    debug["chosen"] = {f"{m}:{y}": asdict(h) for (m, y), h in chosen.items()}

    # Decide which years to output
    years_found = sorted({y for (_, y) in chosen.keys()})
    years_keep = choose_last_n_years(years_found, years_back)

    def get(metric: str, year: int) -> float | None:
        h = chosen.get((metric, year))
        return None if h is None else h.value

    rows: list[dict[str, Any]] = []
    for y in years_keep:
        rows.append({
            "Year": int(y),
            "Revenue": get("revenue", y),
            "Profit": get("profit", y),
            "TotalAssets": get("total_assets", y),
            "TotalLiabilities": get("total_liabilities", y),
            "Equity": get("equity", y),
            "TotalDebt": get("total_debt", y),
        })

    financials_df = pd.DataFrame(rows).sort_values(
        "Year").reset_index(drop=True)

    # ---- Fallback: if TotalLiabilities missing, compute it from Assets = Equity + Liabilities ----
    # Only do this when we have both TotalAssets and Equity.
    if "TotalLiabilities" in financials_df.columns:
        can_compute = (
            financials_df["TotalLiabilities"].isna()
            & financials_df.get("TotalAssets").notna()
            & financials_df.get("Equity").notna()
        )

        if bool(can_compute.any()):
            debug["liabilities_fallback_used"] = True

        financials_df.loc[can_compute, "TotalLiabilities"] = (
            financials_df.loc[can_compute, "TotalAssets"] -
            financials_df.loc[can_compute, "Equity"]
        )

        # if computation produces negatives, invalidate (means equity/asset mismatch)
        neg = financials_df["TotalLiabilities"].notna() & (
            financials_df["TotalLiabilities"] < 0)
        financials_df.loc[neg, "TotalLiabilities"] = None

    out_csv = os.path.join(output_dir, "financials.csv")
    financials_df.to_csv(out_csv, index=False)

    out_dbg = os.path.join(output_dir, "financials_debug.json")
    with open(out_dbg, "w", encoding="utf-8") as f:
        f.write(to_json(debug))

    return financials_df, debug


# Optional: quick local test
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print(
            "Usage: python modules/financial_extractor.py <output_dir_with_stitched_tables>")
        raise SystemExit(1)

    out_dir = sys.argv[1]
    df, dbg = extract_financials(
        pdf_path="",
        focus_pages=[],
        output_dir=out_dir,
        years_back=5,
        min_table_rows=3,
    )
    print(df)
    print("Saved:", os.path.join(out_dir, "financials.csv"))
    print("Debug :", os.path.join(out_dir, "financials_debug.json"))
