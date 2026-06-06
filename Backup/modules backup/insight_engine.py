import os

# Auto-detect project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_insights(df):

    top = df.sort_values("rank").iloc[0]

    summary = f"""
Top IPO: {top.name}
Composite Score: {top['composite_score']}
"""

    # Create reports folder safely
    reports_folder = os.path.join(BASE_DIR, "outputs", "reports")
    os.makedirs(reports_folder, exist_ok=True)

    report_path = os.path.join(reports_folder, "insights.txt")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(summary)
