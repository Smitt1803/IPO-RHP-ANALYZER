# main_pipeline.py

import os
import logging
import time
from datetime import datetime

from modules.extractor import extract_text_from_pdf
from modules.section_splitter import split_sections
from modules.financial_extractor import extract_basic_financials
from modules.comparison_engine import build_comparison
from modules.analysis_engine import compute_ratios
from modules.scoring_engine import score_ipos
from modules.visualization_engine import generate_visuals
from modules.insight_engine import generate_insights


# ────────────────────────────────────────────────
# Logging Setup – console + file
# ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('pipeline.log', encoding='utf-8'),
        logging.StreamHandler()  # also print to console
    ]
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────
# AUTO-DETECT PROJECT ROOT
# ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    start_time_total = time.time()

    input_folder = os.path.join(BASE_DIR, "rhp_inputs")
    output_root = os.path.join(BASE_DIR, "outputs", "processed_ipos")

    os.makedirs(output_root, exist_ok=True)

    if not os.path.exists(input_folder):
        logger.error("Input folder not found: %s", input_folder)
        return

    logger.info("Starting IPO processing pipeline")
    logger.info("Input folder : %s", input_folder)
    logger.info("Output root  : %s", output_root)

    processed_count = 0
    success_count = 0
    failed_count = 0

    pdf_files = [f for f in os.listdir(
        input_folder) if f.lower().endswith(".pdf")]

    if not pdf_files:
        logger.warning("No PDF files found in input folder.")
        return

    logger.info("Found %d PDF files to process", len(pdf_files))

    for file in pdf_files:
        processed_count += 1
        ipo_name = file.replace(".pdf", "").replace(".PDF", "").strip()
        ipo_folder = os.path.join(output_root, ipo_name)
        pdf_path = os.path.join(input_folder, file)

        start_time = time.time()

        logger.info("─" * 60)
        logger.info("Processing IPO %d/%d : %s",
                    processed_count, len(pdf_files), ipo_name)

        try:
            os.makedirs(ipo_folder, exist_ok=True)

            # Step 1: Extract raw text
            logger.info("Extracting text from PDF...")
            raw_text = extract_text_from_pdf(pdf_path, ipo_folder)

            # Step 2: Split into sections
            logger.info("Splitting sections...")
            sections = split_sections(raw_text, ipo_folder)

            # Step 3: Extract financials – now passing pdf_path for tabula
            logger.info("Extracting financial metrics...")
            financial_df = extract_basic_financials(
                sections,
                ipo_folder,
                # ← Added this line (required for tabula-py)
                pdf_path=pdf_path
            )

            elapsed = time.time() - start_time
            logger.info("Completed %s successfully in %.1f seconds",
                        ipo_name, elapsed)
            success_count += 1

        except Exception as e:
            logger.error("Failed to process %s : %s",
                         ipo_name, str(e), exc_info=True)
            failed_count += 1
            # Continue to next file – don't crash whole pipeline

    # ────────────────────────────────────────────────
    # Post-processing: comparison, ratios, scoring, visuals, insights
    # ────────────────────────────────────────────────
    logger.info("─" * 60)
    logger.info("Starting comparison & analysis phase...")

    try:
        df = build_comparison(output_root)

        if df is not None and not df.empty:
            logger.info(
                "Comparison DataFrame built – %d IPOs with data", len(df))

            df = compute_ratios(df)
            logger.info("Ratios computed")

            df = score_ipos(df)
            logger.info("Scoring c9ompleted")

            generate_visuals(df)
            logger.info("Visualizations generated")

            generate_insights(df)
            logger.info("Insights report generated")

            logger.info("Full pipeline completed successfully")
        else:
            logger.warning(
                "No valid financial data found across all IPOs – skipping analysis")

    except Exception as e:
        logger.error("Error during comparison/analysis phase: %s",
                     str(e), exc_info=True)

    total_elapsed = time.time() - start_time_total
    logger.info("─" * 60)
    logger.info("Pipeline Summary")
    logger.info("  Total time     : %.1f seconds", total_elapsed)
    logger.info("  Files processed: %d", processed_count)
    logger.info("  Successful     : %d", success_count)
    logger.info("  Failed         : %d", failed_count)
    logger.info("Pipeline finished at %s",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()
