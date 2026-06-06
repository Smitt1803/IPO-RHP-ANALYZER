import re
import logging
from dataclasses import dataclass
from typing import Optional

import pdfplumber
import pandas as pd

logger = logging.getLogger(__name__)

# Matches: "308" or "Page 308" or "PAGE 308"
FOOTER_PAGE_RE = re.compile(r"(?i)\b(?:page\s*)?(\d{1,4})\b")


@dataclass
class PrintedPageSample:
    pdf_page: int          # 1-based PDF index
    printed_page: int      # footer page number
    raw_footer: str


def extract_footer_text(page, footer_height_ratio: float = 0.13) -> str:
    """
    Extract text only from bottom portion of the page to avoid picking table numbers.
    """
    h = page.height
    footer = page.crop((0, h * (1 - footer_height_ratio), page.width, h))
    return (footer.extract_text() or "").strip()


def parse_printed_page_from_footer(footer_text: str) -> Optional[int]:
    """
    Try to extract a plausible printed page number from footer text.
    Picks the last number found (common in footers).
    """
    if not footer_text:
        return None

    # Find all candidates
    nums = [int(m.group(1)) for m in FOOTER_PAGE_RE.finditer(footer_text)]
    if not nums:
        return None

    # Heuristic: choose the last number in footer text
    printed = nums[-1]

    # sanity limits
    if printed <= 0 or printed > 5000:
        return None
    return printed


def sample_printed_pages(
    pdf_path: str,
    sample_every: int = 10,
    start_pdf_page: int = 1,
    end_pdf_page: int | None = None,
) -> list[PrintedPageSample]:
    """
    Sample footer printed page numbers across the PDF.
    """
    samples: list[PrintedPageSample] = []
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        end = total if end_pdf_page is None else min(total, end_pdf_page)
        start = max(1, start_pdf_page)

        for pno in range(start, end + 1, sample_every):
            page = pdf.pages[pno - 1]
            footer = extract_footer_text(page)
            printed = parse_printed_page_from_footer(footer)
            if printed is not None:
                samples.append(PrintedPageSample(
                    pdf_page=pno,
                    printed_page=printed,
                    raw_footer=footer,
                ))
    return samples


def estimate_offset(samples: list[PrintedPageSample]) -> Optional[float]:
    """
    Estimate offset where:
      printed_page ≈ pdf_page + offset
    offset = printed - pdf_page
    Uses median for robustness.
    """
    if not samples:
        return None

    diffs = [s.printed_page - s.pdf_page for s in samples]
    return float(pd.Series(diffs).median())


def printed_range_to_pdf_pages(
    pdf_path: str,
    printed_start: int,
    printed_end: int,
    pad: int = 2,
) -> list[int]:
    """
    Convert a printed footer page-number range (inclusive) to PDF page indices.
    """
    if printed_end < printed_start:
        printed_start, printed_end = printed_end, printed_start

    # sample more densely near end (where your financials are)
    samples = sample_printed_pages(pdf_path, sample_every=7)
    off = estimate_offset(samples)
    if off is None:
        raise RuntimeError(
            "Could not estimate printed->pdf offset (footer text not extractable).")

    # pdf_page = printed - offset
    pdf_start = int(round(printed_start - off))
    pdf_end = int(round(printed_end - off))

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)

    pdf_start = max(1, pdf_start - pad)
    pdf_end = min(total, pdf_end + pad)

    logger.info(
        "printed->pdf mapping: offset≈%.2f, printed=%d-%d => pdf=%d-%d",
        off, printed_start, printed_end, pdf_start, pdf_end
    )

    return list(range(pdf_start, pdf_end + 1))
