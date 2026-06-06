import logging
import re
from dataclasses import dataclass
from typing import Iterable

import pdfplumber
from rapidfuzz import fuzz

from modules.utils import normalize_text

logger = logging.getLogger(__name__)

YEAR_RE = re.compile(r"\b(20\d{2})\b")

MONEY_CUES = [
    "₹", "rs", "inr", "crore", "cr.", "lakh", "lakhs", "million", "mn"
]

FIN_KWS = [
    # strongest anchors
    "restated financial information",
    "restated consolidated financial information",
    "restated standalone financial information",

    "statement of profit and loss",
    "profit and loss",
    "income statement",

    "balance sheet",
    "statement of assets and liabilities",
    "assets and liabilities",

    "cash flow",
    "statement of cash flows",
]


@dataclass
class PageScore:
    page: int
    score: float
    kw_best: float
    year_count: int
    money_hit: bool


def _money_hit(text: str) -> bool:
    t = normalize_text(text)
    return any(cue in t for cue in [c.lower() for c in MONEY_CUES])


def _year_count(text: str) -> int:
    return len(set(YEAR_RE.findall(text or "")))


def _keyword_best(text: str) -> float:
    """
    Returns best fuzzy score (0..100) across FIN_KWS for the page.
    """
    t = normalize_text(text or "")
    window = t[:2600]
    best = 0.0
    for kw in FIN_KWS:
        nkw = normalize_text(kw)
        if nkw in window:
            return 100.0
        sc = float(fuzz.partial_ratio(nkw, window))
        if sc > best:
            best = sc
    return best


def _cluster_pages(pages: list[PageScore], max_gap: int = 2) -> list[list[PageScore]]:
    if not pages:
        return []
    pages = sorted(pages, key=lambda x: x.page)
    clusters: list[list[PageScore]] = []
    cur = [pages[0]]
    for ps in pages[1:]:
        if ps.page - cur[-1].page <= max_gap:
            cur.append(ps)
        else:
            clusters.append(cur)
            cur = [ps]
    clusters.append(cur)
    return clusters


def _expand(pages: Iterable[int], total_pages: int, pad: int = 2) -> list[int]:
    out = set()
    for p in pages:
        for q in range(p - pad, p + pad + 1):
            if 1 <= q <= total_pages:
                out.add(q)
    return sorted(out)


def _build_scan_ranges(total_pages: int, window: int) -> list[tuple[int, int]]:
    """
    Multi-zone scanning tuned to your observed real ranges (~45%..90%).
    """
    def clamp(a: int, b: int) -> tuple[int, int]:
        a = max(1, a)
        b = min(total_pages, b)
        return (a, b) if a <= b else (1, 0)

    zones = []

    # small early scan (sometimes "restated" starts earlier)
    zones.append(clamp(1, min(90, total_pages)))

    # mid-high zones (most of your PDFs fall here)
    for ratio in (0.35, 0.45, 0.55, 0.65, 0.75):
        start = int(total_pages * ratio)
        zones.append(clamp(start, start + window))

    # strong tail scan (catch very late statements)
    zones.append(clamp(max(1, total_pages - 280), total_pages))

    # de-duplicate while preserving order
    seen = set()
    out = []
    for a, b in zones:
        if (a, b) not in seen and b >= a:
            out.append((a, b))
            seen.add((a, b))
    return out


def find_financial_pages(pdf_path: str, window: int = 220, min_page_ratio: float = 0.25) -> list[int]:
    """
    Returns 1-based page numbers likely to contain financial statements.
    Args kept for compatibility; algorithm is multi-zone now.
    """
    scored: list[PageScore] = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        scan_ranges = _build_scan_ranges(total_pages, window=window)

        pages_to_scan = []
        seen_pages = set()
        for a, b in scan_ranges:
            for p in range(a, b + 1):
                if p not in seen_pages:
                    pages_to_scan.append(p)
                    seen_pages.add(p)

        for pno in pages_to_scan:
            text = pdf.pages[pno - 1].extract_text() or ""
            if not text.strip():
                continue

            kw = _keyword_best(text)
            if kw < 78:  # ignore weak matches
                continue

            ycnt = _year_count(text)
            mhit = _money_hit(text)

            # scoring: keywords dominate, then years, then money cues
            score = (kw / 25.0)  # 78..100 => ~3.1..4.0
            score += 0.9 if ycnt >= 3 else (0.6 if ycnt ==
                                            2 else (0.2 if ycnt == 1 else 0.0))
            score += 0.6 if mhit else 0.0

            scored.append(PageScore(
                page=pno,
                score=float(score),
                kw_best=float(kw),
                year_count=int(ycnt),
                money_hit=bool(mhit),
            ))

    if not scored:
        return []

    # Keep only strong pages
    scored.sort(key=lambda x: x.score, reverse=True)
    threshold = max(3.3, scored[0].score * 0.62)
    strong = [p for p in scored if p.score >= threshold]

    clusters = _cluster_pages(strong, max_gap=2)
    if not clusters:
        return []

    # Prefer clusters that are later (financials are usually later)
    def cluster_score(c: list[PageScore]) -> float:
        base = sum(x.score for x in c) + 0.25 * len(c)
        tail_bonus = c[-1].page / max(1, strong[-1].page)
        return base + 1.0 * tail_bonus

    clusters.sort(key=cluster_score, reverse=True)
    best = clusters[0]

    # Return expanded pages
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

    pages = sorted({x.page for x in best})
    final_pages = _expand(pages, total_pages, pad=2)

    logger.info("page_detector: picked cluster %d..%d (len=%d), expanded to %d pages",
                best[0].page, best[-1].page, len(best), len(final_pages))

    return final_pages
