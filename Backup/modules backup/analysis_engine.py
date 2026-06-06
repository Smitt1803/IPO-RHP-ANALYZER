def compute_ratios(df):

    # Net Profit Margin
    df["Net Profit Margin"] = df.apply(
        lambda row: row["profit"] / row["revenue"]
        if row["revenue"] != 0 else 0,
        axis=1
    )

    # ROA
    df["ROA"] = df.apply(
        lambda row: row["profit"] / row["assets"]
        if row["assets"] != 0 else 0,
        axis=1
    )

    # Debt to Equity
    def safe_de_ratio(row):
        equity = row["assets"] - row["liabilities"]
        if equity <= 0:
            return 10  # Cap at high value instead of inf for scoring
        return row["liabilities"] / equity

    df["Debt to Equity"] = df.apply(safe_de_ratio, axis=1)

    return df
