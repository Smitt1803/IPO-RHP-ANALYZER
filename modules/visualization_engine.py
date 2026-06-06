import os
import matplotlib.pyplot as plt
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def generate_comparison_charts(scored_df: pd.DataFrame, output_dir: str) -> None:
    """
    Generates comparison bar charts:
    - Composite Scores by IPO
    - Profit Margin by IPO
    - Revenue Growth by IPO

    Saves PNG files to output_dir
    """
    if scored_df.empty:
        logger.warning("Empty scored dataframe for visualization, skipping charts.")
        return

    os.makedirs(output_dir, exist_ok=True)

    # Sort by rank ascending
    df_sorted = scored_df.sort_values("Rank")

    # Composite Score Bar Chart
    plt.figure(figsize=(12, 6))
    plt.bar(df_sorted["IPO"], df_sorted["CompositeScore"], color="teal")
    plt.xticks(rotation=45, ha='right')
    plt.title("IPO Composite Financial Score")
    plt.ylabel("Score")
    plt.tight_layout()
    path = os.path.join(output_dir, "composite_score.png")
    plt.savefig(path)
    plt.close()
    logger.info(f"Saved chart: {path}")

    # Net Profit Margin Bar Chart
    plt.figure(figsize=(12, 6))
    plt.bar(df_sorted["IPO"], df_sorted["NetProfitMargin"], color="skyblue")
    plt.xticks(rotation=45, ha='right')
    plt.title("IPO Net Profit Margin")
    plt.ylabel("Net Profit Margin")
    plt.tight_layout()
    path = os.path.join(output_dir, "net_profit_margin.png")
    plt.savefig(path)
    plt.close()
    logger.info(f"Saved chart: {path}")

    # Revenue Growth Bar Chart
    plt.figure(figsize=(12, 6))
    plt.bar(df_sorted["IPO"], df_sorted["RevenueGrowth"], color="orange")
    plt.xticks(rotation=45, ha='right')
    plt.title("IPO Revenue Growth (%)")
    plt.ylabel("Revenue Growth %")
    plt.tight_layout()
    path = os.path.join(output_dir, "revenue_growth.png")
    plt.savefig(path)
    plt.close()
    logger.info(f"Saved chart: {path}")