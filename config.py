import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    # Input/Output
    PROJECT_ROOT: str = os.path.dirname(os.path.abspath(__file__))
    INPUT_DIR: str = os.path.join(PROJECT_ROOT, "rhp_inputs")
    OUTPUT_DIR: str = os.path.join(PROJECT_ROOT, "outputs")

    # Extraction
    MAX_PAGES: int | None = None  # set to e.g. 200 for faster debug; None = all pages
    YEARS_BACK: int = 3
    MIN_TABLE_ROWS: int = 3

    # Section detection keywords
    SECTION_KEYWORDS: dict = None

    # Scoring
    USE_NORMALIZED_SCORING: bool = True
    SCORE_WEIGHTS: dict = None
    OUTLIER_CLIP_QUANTILES: tuple[float, float] = (0.05, 0.95)

    # Gemini
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_ENDPOINT: str = os.getenv(
        "GEMINI_ENDPOINT",
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    )

def build_config() -> Config:
    section_keywords = {
        "financial_summary": [
            "summary of financial information", "financial information", "financial summary",
            "restated financial information", "selected financial"
        ],
        "pnl": [
            "statement of profit and loss", "profit and loss", "statement of profit", "income statement"
        ],
        "balance_sheet": [
            "balance sheet", "statement of assets and liabilities", "assets and liabilities"
        ],
        "risk_factors": ["risk factors"],
        "objects": ["objects of the issue", "objects of the offer", "objects of the ipo"],
    }

    score_weights = {
        "profit_margin": 0.4,
        "roa": 0.3,
        "debt_to_equity": -0.3,
    }

    return Config(
        SECTION_KEYWORDS=section_keywords,
        SCORE_WEIGHTS=score_weights,
    )

CONFIG = build_config()