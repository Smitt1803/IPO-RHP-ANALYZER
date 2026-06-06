import logging
from rapidfuzz import fuzz
from modules.utils import normalize_text

logger = logging.getLogger(__name__)


def detect_sections_by_pages(pages_text: list[str], section_keywords: dict, threshold: int = 75) -> dict:
    """
    Returns a dict of section -> list of page indices (1-based) likely to contain that section.
    Uses keyword match + fuzzy.
    """
    section_pages: dict[str, list[int]] = {
        k: [] for k in section_keywords.keys()}

    for idx, text in enumerate(pages_text, start=1):
        t = normalize_text(text)
        if not t:
            continue
        for section, keys in section_keywords.items():
            hit = False
            for kw in keys:
                nkw = normalize_text(kw)
                if nkw in t:
                    hit = True
                    break
                # fuzzy match: compare keyword against a slice of page text (first 1500 chars)
                window = t[:1500]
                if fuzz.partial_ratio(nkw, window) >= threshold:
                    hit = True
                    break
            if hit:
                section_pages[section].append(idx)

    # Post-process: keep only dense clusters (reduce noise)
    cleaned = {}
    for section, pages in section_pages.items():
        pages = sorted(set(pages))
        if not pages:
            cleaned[section] = []
            continue
        clusters = []
        cur = [pages[0]]
        for p in pages[1:]:
            if p == cur[-1] + 1:
                cur.append(p)
            else:
                clusters.append(cur)
                cur = [p]
        clusters.append(cur)
        # take the largest cluster
        best = max(clusters, key=len)
        cleaned[section] = best if len(best) >= 2 else pages[:5]

    logger.info("Detected section pages: %s", {
                k: (v[:3], len(v)) for k, v in cleaned.items()})
    return cleaned


def get_financial_focus_pages(section_pages: dict) -> list[int]:
    """
    Merge financial-related detected pages and expand slightly.
    """
    focus = set()
    for k in ("financial_summary", "pnl", "balance_sheet"):
        for p in section_pages.get(k, []):
            focus.add(int(p))

    # Expand by +/-2 pages (tables often continue)
    expanded = set()
    for p in focus:
        for q in range(p - 2, p + 3):
            if q > 0:
                expanded.add(q)

    return sorted(expanded)
