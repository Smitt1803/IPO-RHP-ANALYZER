import os
import pandas as pd

from modules.financial_classifier import financial_confidence


def filter_tables(raw_dir, financial_dir, reject_dir):

    os.makedirs(financial_dir, exist_ok=True)
    os.makedirs(reject_dir, exist_ok=True)

    for file in os.listdir(raw_dir):

        if not file.endswith(".csv"):
            continue

        path = os.path.join(raw_dir, file)

        try:
            df = pd.read_csv(path, header=None)
        except:
            continue

        score = financial_confidence(df)

        if score >= 7:

            df.to_csv(os.path.join(financial_dir, file),
                      index=False, header=False)

        else:

            df.to_csv(os.path.join(reject_dir, file),
                      index=False, header=False)
