import pandas as pd
import os

# Auto-detect project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_comparison(output_root):

    ipo_folders = os.listdir(output_root)
    master_df = pd.DataFrame()

    for ipo in ipo_folders:

        financial_path = os.path.join(output_root, ipo, "financials.csv")

        if os.path.exists(financial_path):

            df = pd.read_csv(financial_path)
            df["IPO"] = ipo
            master_df = pd.concat([master_df, df], ignore_index=True)

    if not master_df.empty:
        master_df.set_index("IPO", inplace=True)

        # Create comparison folder safely
        comparison_folder = os.path.join(BASE_DIR, "outputs", "comparison")
        os.makedirs(comparison_folder, exist_ok=True)

        master_df.to_csv(
            os.path.join(comparison_folder, "ipo_comparison.csv")
        )

    return master_df
