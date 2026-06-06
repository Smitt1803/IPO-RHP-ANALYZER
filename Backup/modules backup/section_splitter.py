# modules/section_splitter.py

import os
import difflib


def find_anchor(lines, keywords, similarity_threshold=0.75):
    """
    Find the starting line index of a section using fuzzy + substring matching.
    Returns the earliest matching line index or None.
    """
    for i, line in enumerate(lines):
        lower_line = line.lower().strip()
        if not lower_line:
            continue  # skip empty lines

        for keyword in keywords:
            lower_kw = keyword.lower()
            # 1. Simple containment (fast & common case)
            if lower_kw in lower_line:
                print(
                    f"✓ Found exact/partial match for '{keyword}' at line {i+1}")
                return i

            # 2. Fuzzy similarity (handles typos, extra words, formatting)
            ratio = difflib.SequenceMatcher(None, lower_kw, lower_line).ratio()
            if ratio >= similarity_threshold:
                print(
                    f"✓ Fuzzy match for '{keyword}' ({ratio:.2f}) at line {i+1}")
                return i

    print("✗ No match found for keywords:", [k for k in keywords])
    return None


def split_sections(raw_text, output_folder):
    sections = {
        "pnl": "",
        "balance_sheet": "",
        "raw_text": raw_text
    }

    lines = raw_text.split("\n")

    # ────────────────────────────────────────────────
    # Expanded & realistic keyword sets for Indian RHPs
    # ────────────────────────────────────────────────
    pnl_keywords = [
        "Restated Consolidated Statement of Profit and Loss",
        "Restated Statement of Profit and Loss",
        "Statement of Profit and Loss",
        "Profit and Loss Account",
        "Profit & Loss Statement",
        "Consolidated Profit and Loss",
        "Summary of Financial Information",      # sometimes used
        "Restated Summary Statement of Profit and Loss",
    ]

    bs_keywords = [
        "Restated Consolidated Statement of Assets and Liabilities",
        "Restated Statement of Assets and Liabilities",
        "Statement of Assets and Liabilities",
        "Balance Sheet",
        "Consolidated Balance Sheet",
        "Statement of Financial Position",
        "Restated Summary Statement of Assets and Liabilities",
    ]

    # Keywords that typically mark the END of financial sections
    next_section_markers = [
        "Cash Flow",
        "Cash Flows",
        "Statement of Cash Flows",
        "Notes to the",
        "Significant Accounting Policies",
        "Schedules",
        "Annexure",
        "Other Financial Information",
        "Capitalisation Statement",
        "Capital Structure",
        "Management's Discussion",
    ]

    # ────────────────────────────────────────────────
    # Locate P&L
    # ────────────────────────────────────────────────
    pnl_start = find_anchor(lines, pnl_keywords)

    if pnl_start is not None:
        pnl_end = len(lines)  # default to end of document
        for j in range(pnl_start + 1, len(lines)):
            lower_j = lines[j].lower()
            if any(marker.lower() in lower_j for marker in next_section_markers + bs_keywords):
                pnl_end = j
                print(f"→ P&L section ends before next marker at line {j+1}")
                break
        # Safety cap – prevent taking huge useless chunk
        pnl_end = min(pnl_end, pnl_start + 2500)
        # Also capture more context after header
        if pnl_start is not None:
            pnl_end = pnl_start + 1
            while pnl_end < len(lines) and not any(m.lower() in lines[pnl_end].lower() for m in next_section_markers):
                pnl_end += 1
            # give buffer after marker
            pnl_end = min(pnl_end + 200, len(lines))
        sections["pnl"] = "\n".join(lines[pnl_start:pnl_end]).strip()
        print(f"✅ P&L extracted (lines {pnl_start+1} → {pnl_end})")
    else:
        print("⚠️ P&L section not found.")

    # ────────────────────────────────────────────────
    # Locate Balance Sheet
    # ────────────────────────────────────────────────
    bs_start = find_anchor(lines, bs_keywords)

    if bs_start is not None:
        bs_end = len(lines)
        for j in range(bs_start + 1, len(lines)):
            lower_j = lines[j].lower()
            if any(marker.lower() in lower_j for marker in next_section_markers):
                bs_end = j
                print(
                    f"→ Balance Sheet section ends before next marker at line {j+1}")
                break
        bs_end = min(bs_end, bs_start + 1200)
        sections["balance_sheet"] = "\n".join(lines[bs_start:bs_end]).strip()
        print(f"✅ Balance Sheet extracted (lines {bs_start+1} → {bs_end})")
    else:
        print("⚠️ Balance Sheet section not found.")

    # ────────────────────────────────────────────────
    # Save extracted sections for inspection / debugging
    # ────────────────────────────────────────────────
    section_folder = os.path.join(output_folder, "sections")
    os.makedirs(section_folder, exist_ok=True)

    if sections["pnl"]:
        with open(os.path.join(section_folder, "pnl.txt"), "w", encoding="utf-8") as f:
            f.write(sections["pnl"])

    if sections["balance_sheet"]:
        with open(os.path.join(section_folder, "balance_sheet.txt"), "w", encoding="utf-8") as f:
            f.write(sections["balance_sheet"])

    return sections
