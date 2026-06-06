import os

# Auto-detect project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def score_ipos(df):

    # Normalize metrics (e.g., min-max scale) to avoid extremes
    for col in ["Net Profit Margin", "ROA"]:
        df[col] = (df[col] - df[col].min()) / \
            (df[col].max() - df[col].min() + 1e-6)
    for col in ["Debt to Equity"]:
        df[col] = 1 / (df[col] + 1)  # Inverse for penalty

    df["composite_score"] = (
        df["Net Profit Margin"] * 0.4 +
        df["ROA"] * 0.3 -
        df["Debt to Equity"] * 0.3
    )

    df["rank"] = df["composite_score"].rank(ascending=False)

    # Create comparison folder safely
    comparison_folder = os.path.join(BASE_DIR, "outputs", "comparison")
    os.makedirs(comparison_folder, exist_ok=True)

    scoring_path = os.path.join(comparison_folder, "ipo_scoring.csv")
    df.to_csv(scoring_path)

    return df
