from typing import Sequence
import re
import math
import json
from typing import Any

NUMBER_RE = re.compile(r"""
    (?P<neg>\$)?
    (?P<num>
        (?:\d{1,3}(?:,\d{3})+|\d+)
        (?:\.\d+)?
    )
    (?P<neg2>\$)?
""", re.VERBOSE)


def safe_mkdir(path: str) -> None:
    import os
    os.makedirs(path, exist_ok=True)


def normalize_text(s: str) -> str:
    s = s or ""
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_number(token: str) -> float | None:
    """
    Robust number parser:
    - Supports Indian and Western grouping by stripping commas
    - Supports accounting negatives via parentheses, e.g. (1,234)
    - Handles leading minus signs and various dash characters
    """
    if token is None:
        return None

    s = str(token).strip()
    if s == "" or s.lower() in {"-", "—", "–", "na", "n/a"}:
        return None

    # Normalize unicode dashes and spaces
    s = s.replace("−", "-").replace("\u2212", "-").replace("\u00A0", " ")

    # Detect accounting negative (parentheses)
    is_neg = False
    if "(" in s and ")" in s:
        inner = s[s.find("(") + 1:s.rfind(")")]
        if inner.strip():
            s = inner
            is_neg = True

    # Remove common currency/symbol noise
    s = s.replace("₹", "").replace("rs", "").replace("inr", "")
    s = s.replace("%", "")

    # Remove thousand separators (both Indian and Western)
    s = s.replace(",", "")
    # Extract first numeric token (allow leading sign and decimal point)
    m = re.search(r"[-+]?\s*\d+(?:\.\d+)?", s)
    if not m:
        return None

    num_str = m.group(0).replace(" ", "")
    try:
        val = float(num_str)
    except ValueError:
        return None

    if is_neg or num_str.startswith("-"):
        val = -abs(val)

    return val


def extract_years_from_row(row: list[str]) -> list[int]:
    years = []
    for cell in row:
        if not cell:
            continue
        for y in re.findall(r"\b(20\d{2})\b", str(cell)):
            try:
                years.append(int(y))
            except ValueError:
                pass
    # Unique, keep order
    seen = set()
    out = []
    for y in years:
        if y not in seen:
            out.append(y)
            seen.add(y)
    return out


def choose_last_n_years(years: list[int], n: int) -> list[int]:
    years = sorted(set(years))
    return years[-n:] if len(years) > n else years


def is_suspicious_zero(value: float | None) -> bool:
    if value is None:
        return False
    # In IPO financials, 0 for assets/liabilities is almost always missing extraction
    return abs(value) < 1e-9


def to_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    if b == 0:
        return None
    if any(map(lambda v: isinstance(v, float) and (math.isnan(v) or math.isinf(v)), [a, b])):
        return None
    return a / b


_NUM_FRAGMENT_RE = re.compile(r"^[\s(),.\d]+$")


def is_numeric_fragment(s: str) -> bool:
    """
    True for strings that look like a piece of a number: '1', '28', ',000', '(1', '23.4'
    """
    if s is None:
        return False
    s = str(s).strip()
    if not s:
        return False
    if not _NUM_FRAGMENT_RE.match(s):
        return False
    return any(ch.isdigit() for ch in s)


def reconstruct_number_from_row(row: Sequence[str], start_col: int, max_hops: int = 4) -> float | None:
    """
    Join split numeric tokens across adjacent cells and parse as one number.
    Example: ['Total assets', '1', '28', '000'] => '128000'
    Example: ['...', '1,', '28,', '000'] => '1,28,000'
    """
    parts: list[str] = []
    for j in range(start_col, min(len(row), start_col + max_hops)):
        cell = str(row[j]).strip()
        if not cell:
            # stop if we already started collecting
            if parts:
                break
            continue
        if not is_numeric_fragment(cell):
            break
        parts.append(cell)

    if not parts:
        return None

    joined = "".join(parts)
    # Normalize odd joins like '1 ,28 ,000' => '1,28,000'
    joined = joined.replace(" ", "")
    joined = joined.replace(",,", ",")
    # Now reuse your existing parse_number
    return parse_number(joined)
