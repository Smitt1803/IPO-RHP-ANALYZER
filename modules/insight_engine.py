import os
import logging

logger = logging.getLogger(__name__)


def generate_rule_based_insights(row: dict) -> str:
    """
    Generate textual insights for one IPO row (dict of metrics)
    """
    lines = []

    if row.get("NetProfitMargin") is not None:
        if row["NetProfitMargin"] > 0.2:
            lines.append("Strong profitability with Net Profit Margin > 20%.")
        elif row["NetProfitMargin"] > 0.1:
            lines.append(
                "Moderate profitability with Net Profit Margin between 10%-20%.")
        else:
            lines.append(
                "Low profitability or losses indicated by Net Profit Margin.")

    if row.get("ROA") is not None:
        if row["ROA"] > 0.15:
            lines.append("Efficient use of assets with ROA above 15%.")
        else:
            lines.append("ROA below 15%, asset utilization could be improved.")

    if row.get("DebtEquityRatio") is not None:
        if row["DebtEquityRatio"] < 0.5:
            lines.append("Low financial leverage, indicating lower risk.")
        elif row["DebtEquityRatio"] < 1.0:
            lines.append("Moderate leverage, manageable debt levels.")
        else:
            lines.append("High leverage, company may carry financial risk.")

    if row.get("RevenueGrowth") is not None:
        if row["RevenueGrowth"] > 15:
            lines.append("Strong revenue growth above 15%.")
        elif row["RevenueGrowth"] > 5:
            lines.append("Moderate revenue growth.")
        else:
            lines.append("Slow or no revenue growth detected.")

    if row.get("ProfitGrowth") is not None:
        if row["ProfitGrowth"] > 15:
            lines.append("Strong profit growth observed.")
        elif row["ProfitGrowth"] > 5:
            lines.append("Moderate profit growth.")
        else:
            lines.append("Profit growth is slow or negative.")

    if not lines:
        lines.append("Limited data to generate insights.")

    return "\n".join(lines)


def generate_all_insights(comparison_df, output_dir) -> None:
    """
    Generates combined insights file for all IPOs.
    Saves to output_dir/ipo_interpretation.txt
    """

    lines = []
    if comparison_df.empty:
        lines.append("No IPO data available for insights.\n")
    else:
        for _, row in comparison_df.iterrows():
            ipo = row["IPO"]
            lines.append(f"### IPO: {ipo}\n")
            insight_text = generate_rule_based_insights(row)
            lines.append(insight_text)
            lines.append("\n")

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "ipo_interpretation.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Rule-based insights saved: {out_path}")
