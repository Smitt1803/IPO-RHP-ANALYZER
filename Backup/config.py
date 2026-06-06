import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Gemini API Keys (never hardcode)
GEMINI_API_KEY1 = os.getenv("GEMINI_API_KEY1")
GEMINI_API_KEY2 = os.getenv("GEMINI_API_KEY2")
GEMINI_API_KEY3 = os.getenv("GEMINI_API_KEY3")

PNL_KEYWORDS = [
    "Restated Consolidated Statement of Profit and Loss",
    "Statement of Profit and Loss",
    "Profit and Loss",
    "Summary of Financial Information",
    "Income Statement"
]

BS_KEYWORDS = [
    "Restated Consolidated Statement of Assets and Liabilities",
    "Statement of Assets and Liabilities",
    "Balance Sheet",
    "Statement of Financial Position",
    "Financial Position"
]

FINANCIAL_METRICS = {
    "revenue": [
        "Revenue from operations",
        "Total revenue",
        "Income from operations"
    ],
    "profit": [
        "Profit/(loss) for the period",
        "Profit for the year",
        "Net profit",
        "Profit after tax"
    ],
    "assets": [
        "Total assets"
    ],
    "liabilities": [
        "Total liabilities"
    ]
}