# modules/financial_extractor.py

import pandas as pd
import os
import re
import pdfplumber


# ────────────────────────────────────────────────
# Clean number utility (handles Indian RHP format)
# ────────────────────────────────────────────────
def clean_number(value):
    if value is None:
        return 0.0

    value = str(value).strip()

    if not value:
        return 0.0

    value = (
        value.replace(",", "")
        .replace("₹", "")
        .replace("in million", "")
        .replace("(₹", "(")
        .strip()
    )

    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]

    try:
        return float(value)
    except:
        return 0.0


# ────────────────────────────────────────────────
# Detect correct 2025 column
# ────────────────────────────────────────────────
def detect_2025_column(df):

    latest_indicators = [
        "march 31, 2025",
        "31 march 2025",
        "year ended march 31, 2025",
        "as at march 31, 2025",
        "31.03.2025",
    ]

    # 1️⃣ Check column headers
    for col_idx, col_header in enumerate(df.columns):
        header_str = str(col_header).lower()
        if any(ind in header_str for ind in latest_indicators):
            return col_idx

    # 2️⃣ Check first 3 rows (multi-row header case)
    for row_idx in range(min(3, len(df))):
        for col_idx, val in enumerate(df.iloc[row_idx]):
            val_str = str(val).lower()
            if any(ind in val_str for ind in latest_indicators):
                return col_idx

    # 3️⃣ Fallback: rightmost numeric column
    numeric_cols = [
        i for i, dt in enumerate(df.dtypes)
        if pd.api.types.is_numeric_dtype(dt)
    ]

    if numeric_cols:
        return numeric_cols[-1]

    return -1


# ────────────────────────────────────────────────
# pdfplumber extraction (PRIMARY ENGINE)
# ────────────────────────────────────────────────
def extract_with_pdfplumber(pdf_path):

    collected = {
        "revenue": 0.0,
        "profit": 0.0,
        "assets": 0.0,
        "liabilities": 0.0,
    }

    rev_keywords = [
        "revenue from operations",
        "total revenue",
        "income from operations",
    ]

    profit_keywords = [
        "profit/(loss)",
        "profit for the year",
        "net profit",
        "profit after tax",
    ]

    assets_keywords = ["total assets"]
    liab_keywords = ["total liabilities"]

    try:
        with pdfplumber.open(pdf_path) as pdf:

            for page_num, page in enumerate(pdf.pages):

                page_text = page.extract_text()

                if not page_text:
                    continue

                lower_text = page_text.lower()

                # Only process pages that look financial
                if not any(k in lower_text for k in
                           ["revenue", "profit", "assets", "liabilities"]):
                    continue

                tables = page.extract_tables()

                if not tables:
                    continue

                for table in tables:

                    df = pd.DataFrame(table)

                    if df.empty:
                        continue

                    latest_col_idx = detect_2025_column(df)

                    if latest_col_idx == -1:
                        continue

                    for _, row in df.iterrows():

                        row_text = " ".join(
                            str(x).lower() for x in row if x
                        )

                        if latest_col_idx >= len(row):
                            continue

                        val = clean_number(row[latest_col_idx])

                        if val == 0:
                            continue

                        if any(k in row_text for k in rev_keywords):
                            collected["revenue"] = max(
                                collected["revenue"], val
                            )

                        if any(k in row_text for k in profit_keywords):
                            collected["profit"] = max(
                                collected["profit"], val
                            )

                        if any(k in row_text for k in assets_keywords):
                            collected["assets"] = max(
                                collected["assets"], val
                            )

                        if any(k in row_text for k in liab_keywords):
                            collected["liabilities"] = max(
                                collected["liabilities"], val
                            )

        print("pdfplumber extracted values:", collected)

        if collected["assets"] > 0 and collected["liabilities"] > 0:
            return collected

        print("⚠️ Incomplete extraction from pdfplumber")
        return None

    except Exception as e:
        print("pdfplumber error:", str(e))
        return None


# ────────────────────────────────────────────────
# Rule-based fallback (secondary safety)
# ────────────────────────────────────────────────
def extract_rule_based(full_text):

    lines = full_text.split("\n")

    data = {
        "revenue": 0.0,
        "profit": 0.0,
        "assets": 0.0,
        "liabilities": 0.0,
    }

    rev_kws = ["revenue from operations", "total revenue"]
    profit_kws = ["profit for the year", "net profit"]
    assets_kws = ["total assets"]
    liab_kws = [
        "total liabilities",
        "total liabilities (a+b)",
        "total liabilities and equity",
    ]

    for i, line in enumerate(lines):
        lower = line.lower()

        for kws, key in [
            (rev_kws, "revenue"),
            (profit_kws, "profit"),
            (assets_kws, "assets"),
            (liab_kws, "liabilities"),
        ]:
            if any(kw in lower for kw in kws):

                for offset in range(0, 6):
                    if i + offset >= len(lines):
                        break

                    nums = re.findall(
                        r"[\(\d,]+\.?\d*\)?", lines[i + offset]
                    )

                    cleaned = [
                        clean_number(n)
                        for n in nums
                        if clean_number(n) != 0
                    ]

                    if cleaned:
                        data[key] = max(data[key], max(cleaned))
                        break

    print("Fallback extracted values:", data)
    return data


# ────────────────────────────────────────────────
# Main extraction entry point
# ────────────────────────────────────────────────
def extract_basic_financials(sections, output_folder, pdf_path=None):

    print("🚀 FINANCIAL EXTRACTION STARTED")

    # 1️⃣ Try pdfplumber first
    if pdf_path and os.path.exists(pdf_path):
        pdf_data = extract_with_pdfplumber(pdf_path)

        if pdf_data:
            df = pd.DataFrame([pdf_data])
            save_path = os.path.join(output_folder, "financials.csv")
            df.to_csv(save_path, index=False)
            print(f"✅ Saved (pdfplumber): {save_path}")
            return df

    # 2️⃣ Fallback
    print("Using rule-based fallback extraction")
    full_text = sections.get("raw_text", "")
    data = extract_rule_based(full_text)

    df = pd.DataFrame([data])
    save_path = os.path.join(output_folder, "financials.csv")
    df.to_csv(save_path, index=False)

    print(f"✅ Saved (fallback): {save_path}")
    return df
