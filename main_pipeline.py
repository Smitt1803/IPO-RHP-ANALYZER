import os
import json
import logging

from config import CONFIG
from modules.utils import safe_mkdir
from modules.page_number_mapper import printed_range_to_pdf_pages

from modules.extractor import extract_text_per_page
from modules.section_splitter import detect_sections_by_pages, get_financial_focus_pages

# smart financial page detector (optional; if missing/fails we fallback)
from modules.page_detector import find_financial_pages

# table dumping
from modules.table_dumper import dump_tables_from_pages

# table stitching
from modules.table_stitcher import stitch_dumped_tables

# final merged table (financials + ratios)
from modules.final_table_builder import build_final_table

from modules.financial_extractor import extract_financials
from modules.analysis_engine import compute_financial_ratios
from modules.comparison_engine import build_comparison
from modules.scoring_engine import add_scores_to_comparison
from modules.visualization_engine import generate_comparison_charts
from modules.insight_engine import generate_all_insights

logger = logging.getLogger(__name__)


def load_dashboard_overrides(project_root: str) -> dict:
    """
    Optional: Streamlit dashboard writes dashboard_overrides.json.
    This lets the dashboard control small pipeline parameters without rewriting code.
    """
    path = os.path.join(project_root, "dashboard_overrides.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def list_pdf_files(input_dir: str) -> list[str]:
    if not os.path.exists(input_dir):
        return []
    return sorted(
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith(".pdf")
    )


def safe_name_from_path(pdf_path: str) -> str:
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    return "".join(c if (c.isalnum() or c in (" ", "-", "_")) else "_" for c in base).strip()


def main() -> None:
    # -------------------------------------------------------
    # Setup output directories
    # -------------------------------------------------------
    safe_mkdir(CONFIG.OUTPUT_DIR)
    processed_root = os.path.join(CONFIG.OUTPUT_DIR, "processed_ipos")
    safe_mkdir(processed_root)

    pdf_files = list_pdf_files(CONFIG.INPUT_DIR)
    if not pdf_files:
        raise SystemExit(f"No PDFs found in: {CONFIG.INPUT_DIR}")

    # -------------------------------------------------------
    # Defaults (can be overridden by dashboard_overrides.json)
    # -------------------------------------------------------
    KNOWN_PRINTED_RANGES = {
        "groww": (308, 445),
        "meesho": (420, 549),
        "ksh": (289, 385),
        "icici": (260, 375),
        "corona": (287, 374),
        "bharat": (309, 463),
        "fractal": (330, 520),
        "lg": (150, 390),
        "shadowfax": (140, 330),
        "aye": (150, 460),
        "cleanmax": (200, 870),
        "twistex": (140, 320),
        "pngs": (160, 350),
        "omnitech": (180, 450),
        "sedemac": (160, 450),
        "rajputana": (190, 410),
        "innovision": (160, 400),
        "sai": (180, 420),
        "cmpdi": (140, 440),
        "gsp": (160, 460),
    }

    project_root = os.path.dirname(os.path.abspath(__file__))
    overrides = load_dashboard_overrides(project_root)

    # Override printed ranges from dashboard if provided
    if isinstance(overrides.get("KNOWN_PRINTED_RANGES"), dict) and overrides["KNOWN_PRINTED_RANGES"]:
        # dashboard stores lists; convert to tuples
        KNOWN_PRINTED_RANGES = {
            k: (int(v[0]), int(v[1]))
            for k, v in overrides["KNOWN_PRINTED_RANGES"].items()
            if isinstance(v, (list, tuple)) and len(v) == 2
        }

    DASH_YEARS_BACK = int(overrides.get(
        "YEARS_BACK", getattr(CONFIG, "YEARS_BACK", 3)))
    DASH_MIN_TABLE_ROWS = int(overrides.get(
        "MIN_TABLE_ROWS", getattr(CONFIG, "MIN_TABLE_ROWS", 3)))
    DASH_PRINTED_PAD = int(overrides.get("PRINTED_PAD", 2))
    DASH_YEARS_WINDOW = int(overrides.get("YEARS_WINDOW", DASH_YEARS_BACK))

    # -------------------------------------------------------
    # Process each IPO RHP
    # -------------------------------------------------------
    for pdf_path in pdf_files:
        ipo_name = safe_name_from_path(pdf_path)
        ipo_out_dir = os.path.join(processed_root, ipo_name)
        safe_mkdir(ipo_out_dir)

        logger.info("=" * 90)
        logger.info("Processing IPO: %s", ipo_name)
        logger.info("PDF: %s", pdf_path)

        # ---------------------------------------------------
        # 1) Detect financial pages FIRST (override > detector > fallback)
        #    IMPORTANT: Only extract full text if fallback is needed (slow step).
        # ---------------------------------------------------
        low = ipo_name.lower()
        override = None

        for key, rng in KNOWN_PRINTED_RANGES.items():
            if key in low:
                override = rng
                break

        if override is not None:
            a, b = override  # printed footer pages
            try:
                focus_pages = printed_range_to_pdf_pages(
                    pdf_path, a, b, pad=DASH_PRINTED_PAD)
                logger.info(
                    "Using PRINTED range override for %s: %d-%d => %d pdf pages",
                    ipo_name, a, b, len(focus_pages)
                )
            except Exception as e:
                logger.warning(
                    "Printed-page mapping failed (%s). Falling back to detector.",
                    e
                )
                focus_pages = []
        else:
            focus_pages = []

        # If no override result, try automated page detector (does NOT need pages_text)
        if not focus_pages:
            try:
                focus_pages = find_financial_pages(pdf_path)
            except Exception as e:
                logger.warning("find_financial_pages failed: %s", e)
                focus_pages = []

        # If still empty, fallback to section splitter (NOW extract full text)
        if not focus_pages:
            logger.warning(
                "Fallback to section splitter -> extracting text per page (slow)")
            pages_text = extract_text_per_page(
                pdf_path=pdf_path,
                output_dir=ipo_out_dir,
                max_pages=CONFIG.MAX_PAGES
            )
            section_pages = detect_sections_by_pages(
                pages_text, CONFIG.SECTION_KEYWORDS)
            focus_pages = get_financial_focus_pages(section_pages)

        # Normalize focus pages to ints
        focus_pages = sorted(set(
            int(p) for p in focus_pages if isinstance(p, int) or str(p).isdigit()
        ))

        logger.info("Financial focus pages: %d", len(focus_pages))
        logger.info(
            "Focus pages preview: %s",
            focus_pages[:20] + (["..."] if len(focus_pages) > 20 else [])
        )

        # ---------------------------------------------------
        # 2) Dump ALL tables from financial pages
        # ---------------------------------------------------
        dump_tables_from_pages(
            pdf_path=pdf_path,
            pages=focus_pages,
            output_dir=ipo_out_dir,
            min_rows=2
        )

        # ---------------------------------------------------
        # 3) Stitch multi-page tables (based on dumped tables)
        # ---------------------------------------------------
        try:
            stitched_paths = stitch_dumped_tables(ipo_out_dir)
            logger.info(
                "Stitched %d table groups into %s",
                len(stitched_paths),
                os.path.join(ipo_out_dir, "stitched_tables")
            )
        except Exception as e:
            logger.warning("Table stitching failed: %s", e)

        # ---------------------------------------------------
        # 4) Extract structured financials
        # ---------------------------------------------------
        financials_df, debug = extract_financials(
            pdf_path=pdf_path,
            focus_pages=focus_pages,
            output_dir=ipo_out_dir,
            years_back=DASH_YEARS_BACK,
            min_table_rows=DASH_MIN_TABLE_ROWS,
        )

        # ---------------------------------------------------
        # 5) Compute ratios (writes ratios.csv)
        # ---------------------------------------------------
        compute_financial_ratios(financials_df, ipo_out_dir)

        # ---------------------------------------------------
        # 6) Build final model-ready table (financials + ratios)
        # ---------------------------------------------------
        build_final_table(ipo_name, ipo_out_dir)

    # -------------------------------------------------------
    # 7) Comparison across all IPOs
    # -------------------------------------------------------
    comparison_dir = os.path.join(CONFIG.OUTPUT_DIR, "comparison")
    safe_mkdir(comparison_dir)

    comparison_df = build_comparison(
        processed_root, comparison_dir, years_window=DASH_YEARS_WINDOW)
    scored_df = add_scores_to_comparison(comparison_df, comparison_dir)

    # -------------------------------------------------------
    # 8) Visualization
    # -------------------------------------------------------
    visuals_dir = os.path.join(CONFIG.OUTPUT_DIR, "visuals")
    safe_mkdir(visuals_dir)

    generate_comparison_charts(scored_df, visuals_dir)

    # -------------------------------------------------------
    # 9) Insight generation
    # -------------------------------------------------------
    insights_dir = os.path.join(CONFIG.OUTPUT_DIR, "insights")
    safe_mkdir(insights_dir)

    generate_all_insights(scored_df, insights_dir)

    logger.info("Pipeline completed. Outputs available in: %s",
                CONFIG.OUTPUT_DIR)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")
    main()
