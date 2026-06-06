import os
import logging
import pdfplumber
from modules.utils import safe_mkdir

logger = logging.getLogger(__name__)


def extract_text_per_page(pdf_path: str, output_dir: str, max_pages: int | None = None) -> list[str]:
    """
    Extracts text per page to support page-range sectioning.
    Saves raw_text.txt and per_page_text.jsonl (debuggable).
    """
    safe_mkdir(output_dir)
    raw_text_path = os.path.join(output_dir, "raw_text.txt")
    per_page_path = os.path.join(output_dir, "per_page_text.jsonl")

    pages_text: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        end = total_pages if max_pages is None else min(total_pages, max_pages)
        logger.info("Extracting text: %s (pages=%d, using=%d)",
                    os.path.basename(pdf_path), total_pages, end)

        with open(per_page_path, "w", encoding="utf-8") as fjsonl:
            for i in range(end):
                page = pdf.pages[i]
                text = page.extract_text() or ""
                pages_text.append(text)
                fjsonl.write(f'{{"page": {i+1}, "text": {text!r}}}\n')

    with open(raw_text_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(pages_text))

    return pages_text
