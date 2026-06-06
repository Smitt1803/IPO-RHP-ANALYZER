import os
import logging
import pdfplumber
import pandas as pd

from modules.utils import safe_mkdir

logger = logging.getLogger(__name__)


def _clean_table(table: list[list[str]]) -> pd.DataFrame | None:
    if not table or len(table) < 2:
        return None

    max_cols = max(len(r) for r in table)
    rows = []
    for r in table:
        r = [(c or "").strip() for c in r]
        if len(r) < max_cols:
            r = r + [""] * (max_cols - len(r))
        rows.append(r)

    df = pd.DataFrame(rows)
    df = df.replace("", pd.NA).dropna(how="all").fillna("")
    if df.shape[0] < 2 or df.shape[1] < 2:
        return None
    return df


def dump_tables_from_pages(
    pdf_path: str,
    pages: list[int],
    output_dir: str,
    min_rows: int = 2,
) -> pd.DataFrame:
    """
    Dumps all pdfplumber tables from given PDF page indices (1-based) into:
      output_dir/dumped_tables/page_XXXX_table_YY.csv
    And writes:
      output_dir/dumped_tables_index.csv
    """
    safe_mkdir(output_dir)
    dump_dir = os.path.join(output_dir, "dumped_tables")
    safe_mkdir(dump_dir)

    records = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        valid_pages = [p for p in sorted(set(pages)) if 1 <= p <= total_pages]

        logger.info("Dumping tables from %d pages into %s",
                    len(valid_pages), dump_dir)

        for pno in valid_pages:
            page = pdf.pages[pno - 1]
            try:
                tables = page.extract_tables() or []
            except Exception as e:
                logger.warning("extract_tables failed page=%d: %s", pno, e)
                tables = []

            for t_idx, t in enumerate(tables):
                df = _clean_table(t)
                if df is None:
                    continue
                if df.shape[0] < min_rows:
                    continue

                fname = f"page_{pno:04d}_table_{t_idx:02d}.csv"
                fpath = os.path.join(dump_dir, fname)
                df.to_csv(fpath, index=False, header=False)

                records.append({
                    "page": int(pno),
                    "table_index": int(t_idx),
                    "rows": int(df.shape[0]),
                    "cols": int(df.shape[1]),
                    "csv_file": fname,
                    "csv_path": fpath,
                })

    index_df = pd.DataFrame(records).sort_values(
        ["page", "table_index"]).reset_index(drop=True)
    index_path = os.path.join(output_dir, "dumped_tables_index.csv")
    index_df.to_csv(index_path, index=False)

    logger.info("Dumped %d tables. Index saved: %s", len(index_df), index_path)
    return index_df
