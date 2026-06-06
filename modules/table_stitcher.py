import os
import re
import logging
from dataclasses import dataclass

import pandas as pd
from rapidfuzz import fuzz

from modules.utils import safe_mkdir, normalize_text

logger = logging.getLogger(__name__)
YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _read_table_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    # applymap is deprecated; do column-wise map instead
    df = df.apply(lambda col: col.map(
        lambda x: x.strip() if isinstance(x, str) else x))
    df = df.replace("", pd.NA).dropna(how="all").fillna("")
    return df


def _extract_years_from_df(df: pd.DataFrame, max_rows: int = 8) -> list[int]:
    years = set()
    for r in range(min(max_rows, df.shape[0])):
        row = " ".join(df.iloc[r].astype(str).tolist())
        for y in YEAR_RE.findall(row):
            years.add(int(y))
    return sorted(years)


def _header_signature(df: pd.DataFrame) -> str:
    top = df.head(3).astype(str).values.tolist()
    flat = " | ".join(" ".join(r) for r in top)
    return normalize_text(flat)[:700]


def _label_preview(df: pd.DataFrame, n: int = 18) -> str:
    if df.shape[1] == 0:
        return ""
    col0 = [normalize_text(x) for x in df.iloc[:, 0].astype(str).tolist()]
    col0 = [x for x in col0 if x]
    return " | ".join(col0[:n])


def _drop_repeated_header_rows(df: pd.DataFrame) -> pd.DataFrame:
    keep = []
    for i in range(df.shape[0]):
        row = " ".join(df.iloc[i].astype(str).tolist()).lower()
        yrs = set(YEAR_RE.findall(row))
        headerish = (
            "particular" in row or "note" in row or "notes" in row) and len(yrs) >= 2
        if not headerish:
            keep.append(i)
    return df.iloc[keep].reset_index(drop=True)


@dataclass
class Entry:
    page: int
    table_index: int
    rows: int
    cols: int
    csv_path: str
    years: list[int]
    header_sig: str
    label_preview: str


def stitch_dumped_tables(ipo_out_dir: str) -> list[str]:
    index_path = os.path.join(ipo_out_dir, "dumped_tables_index.csv")
    stitched_dir = os.path.join(ipo_out_dir, "stitched_tables")
    safe_mkdir(stitched_dir)

    if not os.path.exists(index_path):
        raise FileNotFoundError(f"Missing: {index_path}")

    idx = pd.read_csv(index_path)
    if idx.empty:
        logger.warning("No dumped tables to stitch in %s", ipo_out_dir)
        return []

    entries: list[Entry] = []
    for _, r in idx.iterrows():
        p = str(r["csv_path"])
        if not os.path.exists(p):
            continue
        df = _read_table_csv(p)
        years = _extract_years_from_df(df)
        entries.append(Entry(
            page=int(r["page"]),
            table_index=int(r["table_index"]),
            rows=int(df.shape[0]),
            cols=int(df.shape[1]),
            csv_path=p,
            years=years,
            header_sig=_header_signature(df),
            label_preview=_label_preview(df),
        ))

    entries.sort(key=lambda x: (x.page, x.table_index))

    groups: list[list[Entry]] = []
    for e in entries:
        placed = False
        for g in groups:
            ref = g[-1]
            if e.page < ref.page or (e.page - ref.page) > 5:
                continue
            if e.cols != ref.cols:
                continue
            if e.years and ref.years and e.years != ref.years:
                continue

            hs = fuzz.partial_ratio(e.header_sig, ref.header_sig)
            ls = fuzz.partial_ratio(e.label_preview, ref.label_preview)

            if hs >= 75 and ls >= 55:
                g.append(e)
                placed = True
                break
        if not placed:
            groups.append([e])

    stitched_paths: list[str] = []
    for gi, g in enumerate(groups, start=1):
        # keep meaningful groups only
        any_years = any(len(x.years) >= 2 for x in g)
        if len(g) == 1 and not any_years:
            continue

        dfs = []
        for e in g:
            df = _read_table_csv(e.csv_path)
            df = _drop_repeated_header_rows(df)
            dfs.append(df)

        stitched = pd.concat(dfs, axis=0, ignore_index=True)
        out_path = os.path.join(stitched_dir, f"stitched_group_{gi:02d}.csv")
        stitched.to_csv(out_path, index=False, header=False)
        stitched_paths.append(out_path)

    logger.info("Stitched %d table groups for %s",
                len(stitched_paths), ipo_out_dir)
    return stitched_paths
