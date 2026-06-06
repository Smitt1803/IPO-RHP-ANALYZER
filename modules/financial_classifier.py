import pandas as pd
import re

FINANCIAL_KEYWORDS = [
    "revenue",
    "income",
    "profit",
    "assets",
    "liabilities",
    "cash",
    "earnings",
    "expenses",
    "equity",
    "ebitda"
]


def keyword_score(df):

    text = " ".join(df.astype(str).values.flatten()).lower()

    score = 0

    for word in FINANCIAL_KEYWORDS:
        if word in text:
            score += 1

    return score


def detect_years(df):

    text = " ".join(df.astype(str).values.flatten())

    years = re.findall(r"20\d{2}", text)

    return len(years)


def numeric_density(df):

    total = df.size

    nums = df.applymap(
        lambda x: str(x).replace(",", "").replace(".", "").isdigit()
    ).sum().sum()

    return nums / total


def financial_confidence(df):

    k_score = keyword_score(df)
    y_score = detect_years(df)
    n_score = numeric_density(df)

    score = 0

    if k_score >= 2:
        score += 4

    if y_score >= 2:
        score += 3

    if n_score > 0.2:
        score += 3

    return score
