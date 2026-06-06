import pandas as pd
import numpy as np


# ────────────────────────────────────────────────
# FILE PATH (use any of your files)
# ────────────────────────────────────────────────
file_path = r"E:\404found\Projects\PBL Final\IPO_Automation_System\outputs\comparison\ipo_analysis_comparison.csv"

df = pd.read_csv(file_path)

print("\n📊 Data Loaded Successfully\n")
print(df.head())

df.columns = df.columns.str.strip()


# ────────────────────────────────────────────────
# AUTO COLUMN DETECTION
# ────────────────────────────────────────────────
print("\n📊 Columns Found:")
print(list(df.columns))


# Try to detect column names dynamically
profit_col = None
roa_col = None
de_col = None
score_col = None

for col in df.columns:
    c = col.lower()

    if "profitmargin" in c:
        profit_col = col
    elif "roa" in c:
        roa_col = col
    elif "debt" in c:
        de_col = col
    elif "score" in c:
        score_col = col


# ────────────────────────────────────────────────
# CREATE SCORE IF NOT PRESENT
# ────────────────────────────────────────────────
if score_col is None:
    print("\n⚠️ No score column found → creating composite_score")

    def normalize(series):
        return (series - series.min()) / (series.max() - series.min() + 1e-9)

    df["NPM_norm"] = normalize(df[profit_col])
    df["ROA_norm"] = normalize(df[roa_col])
    df["DE_norm"] = normalize(df[de_col])

    df["composite_score"] = (
        0.4 * df["NPM_norm"] +
        0.3 * df["ROA_norm"] -
        0.3 * df["DE_norm"]
    )

    score_col = "composite_score"

else:
    print("\n✅ Using existing score column:", score_col)


# Clean NaNs AFTER score creation
df = df.dropna()


# ────────────────────────────────────────────────
# EVALUATION FUNCTIONS
# ────────────────────────────────────────────────

def spearman(df):
    return df[score_col].corr(df[profit_col], method='spearman')


def kendall(df):
    return df[score_col].corr(df[profit_col], method='kendall')


def variance(df):
    return np.var(df[score_col])


def range_score(df):
    return df[score_col].max() - df[score_col].min()


def monotonic(df):
    return {
        "profit_vs_score": df[profit_col].corr(df[score_col]),
        "roa_vs_score": df[roa_col].corr(df[score_col]),
        "de_vs_score": df[de_col].corr(df[score_col]),
    }


# ────────────────────────────────────────────────
# RUN EVALUATION
# ────────────────────────────────────────────────

results = {
    "spearman_corr": spearman(df),
    # "kendall_corr": kendall(df),
    "score_variance": variance(df),
    "score_range": range_score(df),
    "monotonicity": monotonic(df)
}


# ────────────────────────────────────────────────
# OUTPUT
# ────────────────────────────────────────────────

print("\n📊 Evaluation Metrics:\n")

for key, value in results.items():
    if isinstance(value, dict):
        print(f"{key}:")
        for sub_k, sub_v in value.items():
            print(f"   {sub_k}: {sub_v}")
    else:
        print(f"{key}: {value}")
