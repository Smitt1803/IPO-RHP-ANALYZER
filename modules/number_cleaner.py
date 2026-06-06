import pandas as pd
import re


def parse_financial_number(value):

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value == "":
        return None

    value = value.replace("₹", "").replace("$", "")

    negative = False
    if value.startswith("(") and value.endswith(")"):
        negative = True
        value = value[1:-1]

    value = value.replace(",", "").strip()

    if not re.match(r"^-?\d+(\.\d+)?$", value):
        return None

    num = float(value)

    if negative:
        num = -num

    return num


def clean_dataframe_numbers(df):
    # FIX: applymap deprecated → use map on stack
    return df.stack().map(parse_financial_number).unstack()
