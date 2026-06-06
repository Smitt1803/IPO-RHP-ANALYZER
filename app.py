import os
import io
import json
import time
import shutil
import zipfile
import subprocess
from datetime import datetime

import pandas as pd
import numpy as np
import streamlit as st

from config import CONFIG

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OVERRIDES_PATH = os.path.join(PROJECT_ROOT, "dashboard_overrides.json")

INPUT_DIR = CONFIG.INPUT_DIR
OUTPUT_DIR = CONFIG.OUTPUT_DIR
PROCESSED_ROOT = os.path.join(OUTPUT_DIR, "processed_ipos")
COMPARISON_DIR = os.path.join(OUTPUT_DIR, "comparison")


# ---------------------------
# Utility helpers
# ---------------------------

def load_overrides() -> dict:
    if os.path.exists(OVERRIDES_PATH):
        try:
            with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_overrides(d: dict) -> None:
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)


def default_known_ranges() -> dict:
    # printed footer ranges (human page numbers)
    return {
        "groww": [308, 445],
        "meesho": [420, 549],
        "ksh": [289, 385],
        "icici": [260, 375],
        "corona": [287, 374],
        "bharat": [309, 463],
    }


def list_ipo_dirs() -> list[str]:
    if not os.path.exists(PROCESSED_ROOT):
        return []
    return sorted(
        d for d in os.listdir(PROCESSED_ROOT)
        if os.path.isdir(os.path.join(PROCESSED_ROOT, d))
    )


@st.cache_data(show_spinner=False)
def read_csv_cached(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def path_exists(path: str) -> bool:
    try:
        return os.path.exists(path)
    except Exception:
        return False


def zip_folder_to_bytes(folder_path: str) -> bytes:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(folder_path):
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, folder_path)
                z.write(full, rel)
    mem.seek(0)
    return mem.read()


def zip_files_to_bytes(file_paths: list[str], base_dir: str) -> bytes:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        for fp in file_paths:
            if os.path.exists(fp):
                z.write(fp, os.path.relpath(fp, base_dir))
    mem.seek(0)
    return mem.read()


def run_pipeline_streaming(log_placeholder, max_lines: int = 250) -> tuple[int, str]:
    """
    Runs main_pipeline.py and streams stdout to Streamlit.
    Returns (returncode, full_log_text).
    """
    p = subprocess.Popen(
        ["python", "main_pipeline.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    lines: list[str] = []
    while True:
        line = p.stdout.readline() if p.stdout else ""
        if not line and p.poll() is not None:
            break
        if line:
            lines.append(line.rstrip("\n"))
            log_placeholder.code("\n".join(lines[-max_lines:]))

    rc = p.wait()
    return rc, "\n".join(lines)


def ensure_dirs() -> None:
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PROCESSED_ROOT, exist_ok=True)
    os.makedirs(COMPARISON_DIR, exist_ok=True)


# ---------------------------
# Streamlit UI
# ---------------------------

st.set_page_config(page_title="IPO RHP Analyzer", layout="wide")
st.title("IPO RHP Analyzer (PDF → Tables → Financials → Ratios → Ranking)")

if "selected_ipo" not in st.session_state:
    st.session_state.selected_ipo = None

overrides = load_overrides()
overrides.setdefault("KNOWN_PRINTED_RANGES", default_known_ranges())

# Sidebar: Run controls
with st.sidebar:
    st.header("Run Controls")

    st.subheader("Upload Handling")
    clear_inputs = st.checkbox(
        "Clear existing rhp_inputs/ before upload", value=True)
    clear_outputs = st.checkbox(
        "Clear outputs/processed_ipos/ before run", value=False)

    st.subheader("Extraction Settings")
    years_back = st.number_input(
        "Years back (financial extraction)",
        min_value=1, max_value=10,
        value=int(overrides.get("YEARS_BACK", getattr(CONFIG, "YEARS_BACK", 3)))
    )
    min_table_rows = st.number_input(
        "Min table rows (ignore tiny tables)",
        min_value=2, max_value=50,
        value=int(overrides.get("MIN_TABLE_ROWS",
                  getattr(CONFIG, "MIN_TABLE_ROWS", 3)))
    )
    years_window = st.number_input(
        "Years window for comparison averages (B mode)",
        min_value=1, max_value=10,
        value=int(overrides.get("YEARS_WINDOW", 3))
    )

    st.subheader("Page Override (Printed Footer Ranges)")
    pad_pages = st.number_input(
        "Printed→PDF conversion pad (± pages)",
        min_value=0, max_value=10,
        value=int(overrides.get("PRINTED_PAD", 2))
    )

    st.subheader("Scoring Settings (documented/optional)")
    st.caption(
        "These are saved into dashboard_overrides.json. "
        "Your scoring_engine.py must read them if you want dynamic scoring."
    )

    w_margin = st.slider("Weight: NetProfitMargin_avg", -
                         1.0, 1.0, float(overrides.get("W_MARGIN", 0.30)), 0.01)
    w_roa = st.slider("Weight: ROA_avg", -1.0, 1.0,
                      float(overrides.get("W_ROA", 0.25)), 0.01)
    w_revg = st.slider("Weight: RevenueGrowth_avg", -1.0, 1.0,
                       float(overrides.get("W_REVG", 0.15)), 0.01)
    w_profg = st.slider("Weight: ProfitGrowth_avg", -1.0,
                        1.0, float(overrides.get("W_PROFG", 0.10)), 0.01)
    w_de = st.slider("Weight: DebtEquityRatio_avg (penalty)", -
                     1.0, 1.0, float(overrides.get("W_DE", -0.20)), 0.01)

    clip_low = st.slider("Clip low percentile", 0, 20,
                         int(overrides.get("CLIP_LOW", 5)), 1)
    clip_high = st.slider("Clip high percentile", 80, 100,
                          int(overrides.get("CLIP_HIGH", 95)), 1)

    st.subheader("Category Thresholds")
    q_better = st.slider("Better threshold quantile", 0.50,
                         0.95, float(overrides.get("Q_BETTER", 0.70)), 0.01)
    q_notrec = st.slider("Not Recommended threshold quantile", 0.05, 0.50, float(
        overrides.get("Q_NOTREC", 0.30)), 0.01)

    st.subheader("Run Mode (optional)")
    run_mode_choices = [
        "Full pipeline", "Tables only (dump+stitch)", "Extraction only (from existing tables)"]
    run_mode = st.radio(
        "Mode",
        run_mode_choices,
        index=run_mode_choices.index(
            overrides.get("RUN_MODE", "Full pipeline"))
        if overrides.get("RUN_MODE", "Full pipeline") in run_mode_choices else 0
    )

    st.subheader("Performance / UX")
    log_tail_lines = st.slider("Show last N log lines", 50, 600, int(
        overrides.get("LOG_TAIL_LINES", 250)), 10)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        save_btn = st.button("Save Settings")
    with col_s2:
        run_btn = st.button("Run Pipeline", type="primary")


# Save overrides
if save_btn:
    overrides["YEARS_BACK"] = int(years_back)
    overrides["MIN_TABLE_ROWS"] = int(min_table_rows)
    overrides["YEARS_WINDOW"] = int(years_window)
    overrides["PRINTED_PAD"] = int(pad_pages)

    overrides["W_MARGIN"] = float(w_margin)
    overrides["W_ROA"] = float(w_roa)
    overrides["W_REVG"] = float(w_revg)
    overrides["W_PROFG"] = float(w_profg)
    overrides["W_DE"] = float(w_de)

    overrides["CLIP_LOW"] = int(clip_low)
    overrides["CLIP_HIGH"] = int(clip_high)
    overrides["Q_BETTER"] = float(q_better)
    overrides["Q_NOTREC"] = float(q_notrec)

    overrides["RUN_MODE"] = run_mode
    overrides["LOG_TAIL_LINES"] = int(log_tail_lines)

    overrides.setdefault("KNOWN_PRINTED_RANGES", default_known_ranges())
    save_overrides(overrides)
    st.success(f"Saved settings to {OVERRIDES_PATH}")


# Tabs
tab_run, tab_explore, tab_compare, tab_downloads, tab_settings = st.tabs(
    ["Run", "Explore IPO", "Compare & Rank", "Downloads", "Printed Ranges Editor"]
)

# ---------------------------
# Tab: Run
# ---------------------------
with tab_run:
    st.subheader("Upload PDFs")
    uploaded = st.file_uploader(
        "Upload one or more IPO RHP PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    colA, colB = st.columns(2)
    with colA:
        st.write("Input folder:", INPUT_DIR)
    with colB:
        st.write("Output folder:", OUTPUT_DIR)

    st.caption(
        "Tip: With printed-range overrides available, the pipeline skips full-text extraction "
        "and becomes significantly faster."
    )

    if run_btn:
        ensure_dirs()

        if not uploaded and clear_inputs:
            st.error("Upload at least one PDF (or disable clearing inputs).")
            st.stop()

        if clear_inputs:
            for f in os.listdir(INPUT_DIR):
                if f.lower().endswith(".pdf"):
                    try:
                        os.remove(os.path.join(INPUT_DIR, f))
                    except Exception:
                        pass

        if clear_outputs and os.path.exists(PROCESSED_ROOT):
            try:
                shutil.rmtree(PROCESSED_ROOT)
                os.makedirs(PROCESSED_ROOT, exist_ok=True)
            except Exception:
                pass

        # Save uploads
        saved = []
        for up in (uploaded or []):
            out_path = os.path.join(INPUT_DIR, up.name)
            with open(out_path, "wb") as f:
                f.write(up.getbuffer())
            saved.append(out_path)

        st.write("Saved PDFs:")
        st.write(saved if saved else ["(using existing PDFs in rhp_inputs/)"])

        # Save overrides (so main_pipeline.py can read them)
        overrides = load_overrides()
        overrides.setdefault("KNOWN_PRINTED_RANGES", default_known_ranges())

        overrides["YEARS_BACK"] = int(years_back)
        overrides["MIN_TABLE_ROWS"] = int(min_table_rows)
        overrides["YEARS_WINDOW"] = int(years_window)
        overrides["PRINTED_PAD"] = int(pad_pages)

        overrides["RUN_MODE"] = run_mode
        overrides["LOG_TAIL_LINES"] = int(log_tail_lines)

        # (optional saved, if later scoring reads them)
        overrides["W_MARGIN"] = float(w_margin)
        overrides["W_ROA"] = float(w_roa)
        overrides["W_REVG"] = float(w_revg)
        overrides["W_PROFG"] = float(w_profg)
        overrides["W_DE"] = float(w_de)
        overrides["CLIP_LOW"] = int(clip_low)
        overrides["CLIP_HIGH"] = int(clip_high)
        overrides["Q_BETTER"] = float(q_better)
        overrides["Q_NOTREC"] = float(q_notrec)

        save_overrides(overrides)

        st.info("Running pipeline… live logs will appear below.")
        log_box = st.empty()

        start = time.time()
        with st.spinner("Running…"):
            rc, full_log = run_pipeline_streaming(
                log_box, max_lines=int(log_tail_lines))
        elapsed = time.time() - start

        st.write(f"Finished in {elapsed:.1f} seconds. Return code: {rc}")

        with st.expander("Full Log (copy/paste)", expanded=False):
            st.text(full_log if full_log else "(no log output)")

        if rc != 0:
            st.error(
                "Pipeline failed. Open the full log above and paste the last error lines.")
        else:
            st.success(
                "Pipeline completed successfully. Go to Compare & Rank / Explore IPO tabs.")

# ---------------------------
# Tab: Explore IPO
# ---------------------------
with tab_explore:
    st.subheader("Explore per-IPO outputs")

    ipo_dirs = list_ipo_dirs()
    if not ipo_dirs:
        st.info("No IPO outputs found yet. Run the pipeline first.")
    else:
        selected = st.selectbox("Select IPO", ipo_dirs)
        ipo_dir = os.path.join(PROCESSED_ROOT, selected)

        fin_path = os.path.join(ipo_dir, "financials.csv")
        ratios_path = os.path.join(ipo_dir, "ratios.csv")
        final_path = os.path.join(ipo_dir, "final_table.csv")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("financials.csv", "Yes" if path_exists(fin_path) else "No")
        col2.metric("ratios.csv", "Yes" if path_exists(ratios_path) else "No")
        col3.metric("final_table.csv",
                    "Yes" if path_exists(final_path) else "No")
        col4.metric("stitched_tables/", "Yes" if os.path.exists(
            os.path.join(ipo_dir, "stitched_tables")) else "No")

        subtab1, subtab2, subtab3, subtab4 = st.tabs(
            ["Final Table + Trends", "Financials",
                "Ratios", "Stitched Tables Browser"]
        )

        with subtab1:
            if path_exists(final_path):
                df = read_csv_cached(final_path)
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("final_table.csv not found for selected IPO.")
                df = pd.DataFrame()

            # Quick charts from final_table
            if not df.empty:
                df2 = df.copy()
                if "Year" in df2.columns:
                    df2["Year"] = pd.to_numeric(df2["Year"], errors="coerce")

                st.markdown("### Quick Trends")
                metric_options = [c for c in ["Revenue", "Profit", "TotalAssets",
                                              "TotalLiabilities", "Equity", "TotalDebt"] if c in df2.columns]
                ratio_options = [c for c in ["DebtEquityRatio", "ROA", "NetProfitMargin",
                                             "RevenueGrowth", "ProfitGrowth"] if c in df2.columns]

                c1, c2 = st.columns(2)
                with c1:
                    metric_col = st.selectbox("Metric trend", metric_options if metric_options else [
                                              "(none)"], key=f"{selected}_metric_trend")
                    if metric_col != "(none)" and "Year" in df2.columns:
                        chart_df = df2[["Year", metric_col]].dropna()
                        if not chart_df.empty:
                            st.line_chart(
                                chart_df.set_index("Year")[metric_col])
                        else:
                            st.info("Not enough data to plot metric trend.")
                with c2:
                    ratio_col = st.selectbox("Ratio trend", ratio_options if ratio_options else [
                                             "(none)"], key=f"{selected}_ratio_trend")
                    if ratio_col != "(none)" and "Year" in df2.columns:
                        chart_df = df2[["Year", ratio_col]].dropna()
                        if not chart_df.empty:
                            st.line_chart(
                                chart_df.set_index("Year")[ratio_col])
                        else:
                            st.info("Not enough data to plot ratio trend.")

        with subtab2:
            if path_exists(fin_path):
                fin = read_csv_cached(fin_path)
                st.dataframe(fin, use_container_width=True)
            else:
                st.warning("financials.csv not found for selected IPO.")

        with subtab3:
            if path_exists(ratios_path):
                ratios = read_csv_cached(ratios_path)
                st.dataframe(ratios, use_container_width=True)
            else:
                st.warning("ratios.csv not found for selected IPO.")

        with subtab4:
            stitched_dir = os.path.join(ipo_dir, "stitched_tables")
            if not os.path.exists(stitched_dir):
                st.warning("No stitched_tables folder found for this IPO.")
            else:
                stitched_files = sorted([f for f in os.listdir(
                    stitched_dir) if f.lower().endswith(".csv")])
                if not stitched_files:
                    st.warning("No stitched table CSVs found.")
                else:
                    sf = st.selectbox(
                        "Select stitched table", stitched_files, key=f"{selected}_stitched_file")
                    sf_path = os.path.join(stitched_dir, sf)

                    try:
                        st.caption(sf_path)

                        # stitched tables are headerless; read raw
                        sdf = pd.read_csv(sf_path, header=None,
                                          dtype=str, keep_default_na=False)
                        st.dataframe(sdf.head(200), use_container_width=True)

                        st.markdown("### Search inside stitched table")
                        q = st.text_input(
                            "Search text (e.g., 'total assets', 'profit after tax', 'borrowings')",
                            key=f"{selected}_search"
                        )

                        if q:
                            qn = q.strip().lower()
                            # simple contains filter across all cells
                            mask = sdf.astype(str).apply(
                                lambda col: col.str.lower().str.contains(qn, na=False))
                            rows = mask.any(axis=1)
                            filtered = sdf[rows]
                            st.write(f"Matches: {len(filtered)} rows")
                            st.dataframe(filtered.head(200),
                                         use_container_width=True)

                    except Exception as e:
                        st.error(f"Failed to open stitched table: {e}")


# ---------------------------
# Tab: Compare & Rank
# ---------------------------
with tab_compare:
    st.subheader("📊 IPO Decision Dashboard")

    st.markdown("""
        <style>

        @keyframes flashGlow {
            0% {
                box-shadow: 0 0 10px #00ff88, 0 0 20px #00ff88;
                border-color: #00ff88;
            }
            50% {
                box-shadow: 0 0 10px red, 0 0 25px red;
                border-color: red;
            }
            100% {
                box-shadow: 0 0 10px #00ff88, 0 0 20px #00ff88;
                border-color: #00ff88;
            }
        }

        .flash-banner {
            padding: 18px;
            border-radius: 12px;
            text-align: center;
            font-weight: 600;
            font-size: 16px;
            color: white;
            background: linear-gradient(145deg, #022e1f, #2e0202);
            border: 2px solid #00ff88;
            animation: flashGlow 1.5s infinite;
        }

        </style>

        <div class="flash-banner">
        📌 AI Recommendation: Based on profitability, growth, and risk analysis.
        </div>
        """, unsafe_allow_html=True
                )

    # ---------------------------
    # CSS STYLING (UPGRADED + SAFE)
    # ---------------------------
    st.markdown("""
    <style>

    .buy-card {
        border-radius: 18px;
        padding: 25px;
        background: linear-gradient(145deg, #022e1f, #065f46);
        border: 1px solid #00ff88;
        box-shadow: 0 0 15px #00ff88, inset 0 0 10px rgba(0,255,136,0.1);
        transition: all 0.3s ease;
    }
    .buy-card:hover {
        transform: translateY(-6px) scale(1.02);
        box-shadow: 0 0 25px #00ff88, 0 0 60px rgba(0,255,136,0.3);
    }

    .avoid-card {
        border-radius: 18px;
        padding: 25px;
        background: linear-gradient(145deg, #2e0202, #7f1d1d);
        border: 1px solid red;
        box-shadow: 0 0 15px red, inset 0 0 10px rgba(255,0,0,0.1);
        transition: all 0.3s ease;
    }
    .avoid-card:hover {
        transform: translateY(-6px) scale(1.02);
        box-shadow: 0 0 25px red, 0 0 60px rgba(255,0,0,0.3);
    }

    .card-title {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .card-score {
        font-size: 34px;
        font-weight: 700;
        margin: 12px 0;
    }

    .card-sub {
        font-size: 14px;
        opacity: 0.9;
        line-height: 1.6;
    }

    </style>
    """, unsafe_allow_html=True)

    scored_path = os.path.join(COMPARISON_DIR, "scored_ipo_comparison.csv")

    if not path_exists(scored_path):
        st.warning("Run pipeline first.")
    else:
        scored = read_csv_cached(scored_path)

        # Fix infinity issues
        scored = scored.replace([np.inf, -np.inf], np.nan)
        scored = scored.fillna(0)

        scored = scored.sort_values("CompositeScore", ascending=False)

        top_buy = scored.head(3)
        top_avoid = scored.tail(3)

        # ---------------------------
        # 🟢 TOP 3 BUY
        # ---------------------------
        st.markdown("## 🟢 Top 3 IPOs to BUY")

        cols = st.columns(3)
        for i, (_, row) in enumerate(top_buy.iterrows()):
            ipo_name = row['IPO'].split('-')[0][:35]

            with cols[i]:
                html = f"""
                <div class="buy-card">
                    <div class="card-title">{ipo_name}</div>
                    <div class="card-score">{round(row['CompositeScore'], 2)}</div>
                    <div class="card-sub">
                        ROA: {round(row.get('ROA_avg', 0), 2)} <br>
                        Margin: {round(row.get('NetProfitMargin_avg', 0), 2)}
                    </div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

                # 👇 ADD THIS BUTTON
                if st.button("View Details", key=f"buy_{row['IPO']}"):
                    st.session_state.selected_ipo = row["IPO"]

        # ---------------------------
        # 🔴 TOP 3 AVOID
        # ---------------------------
        st.markdown("## 🔴 Top 3 IPOs to AVOID")

        cols = st.columns(3)
        for i, (_, row) in enumerate(top_avoid.iterrows()):
            ipo_name = row['IPO'].split('-')[0][:35]

            with cols[i]:
                html = f"""
                <div class="avoid-card">
                    <div class="card-title">{ipo_name}</div>
                    <div class="card-score">{round(row['CompositeScore'], 2)}</div>
                    <div class="card-sub">
                        ROA: {round(row.get('ROA_avg', 0), 2)} <br>
                        Debt: {round(row.get('DebtEquityRatio_avg', 0), 2)}
                    </div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

                # 👇 ADD THIS BUTTON
                if st.button("View Details", key=f"avoid_{row['IPO']}"):
                    st.session_state.selected_ipo = row["IPO"]

        # ---------------------------
        # 📊 SELECTED IPO DETAILS
        # ---------------------------
        if st.session_state.selected_ipo:

            st.markdown("---")
            st.markdown(
                f"## 📌 Detailed Analysis: {st.session_state.selected_ipo}")

            selected_row = scored[scored["IPO"]
                                  == st.session_state.selected_ipo]

            if not selected_row.empty:
                row = selected_row.iloc[0]

                c1, c2, c3, c4 = st.columns(4)

                c1.metric("Score", round(row["CompositeScore"], 2))
                c2.metric("ROA", round(row.get("ROA_avg", 0), 2))
                c3.metric("Margin", round(
                    row.get("NetProfitMargin_avg", 0), 2))
                c4.metric("Debt", round(row.get("DebtEquityRatio_avg", 0), 2))

                st.markdown("### 📊 Full Data")
                st.dataframe(selected_row, use_container_width=True)

            else:
                st.warning("IPO data not found.")

        # ---------------------------
        # 📈 GRAPHS (ALWAYS SHOW)
        # ---------------------------
        if "scored" in locals():

            st.markdown("## 📈 Market Insights")

            st.markdown("### Composite Score Distribution")
            st.bar_chart(scored.set_index("IPO")["CompositeScore"])

            if "ROA_avg" in scored.columns and "NetProfitMargin_avg" in scored.columns:
                import altair as alt

                st.markdown("### ROA vs Profit Margin")

                scatter = alt.Chart(scored).mark_circle(size=120).encode(
                    x="ROA_avg",
                    y="NetProfitMargin_avg",
                    color="CompositeScore",
                    tooltip=["IPO", "CompositeScore"]
                ).interactive()

                st.altair_chart(scatter, use_container_width=True)

            if "DebtEquityRatio_avg" in scored.columns:
                st.markdown("### Debt Comparison (Lower is Better)")
                st.bar_chart(
                    scored.sort_values("DebtEquityRatio_avg")
                    .set_index("IPO")["DebtEquityRatio_avg"]
                )


# ---------------------------
# Tab: Downloads
# ---------------------------
with tab_downloads:
    st.subheader("Download Outputs")

    ensure_dirs()

    ipo_dirs = list_ipo_dirs()
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Download one IPO as ZIP")
        if not ipo_dirs:
            st.info("No IPO outputs available.")
        else:
            selected = st.selectbox(
                "Select IPO to download", ipo_dirs, key="download_one_ipo")
            if st.button("Build ZIP for selected IPO"):
                folder = os.path.join(PROCESSED_ROOT, selected)
                data = zip_folder_to_bytes(folder)
                st.download_button(
                    "Download ZIP",
                    data=data,
                    file_name=f"{selected}_outputs.zip",
                    mime="application/zip"
                )

    with col2:
        st.markdown("### Download comparison outputs as ZIP")
        files = [
            os.path.join(COMPARISON_DIR, "master_final_table_by_year.csv"),
            os.path.join(COMPARISON_DIR, "ipo_summary_for_scoring.csv"),
            os.path.join(COMPARISON_DIR, "scored_ipo_comparison.csv"),
        ]
        if st.button("Build ZIP for comparison outputs"):
            data = zip_files_to_bytes(files, base_dir=OUTPUT_DIR)
            st.download_button(
                "Download Comparison ZIP",
                data=data,
                file_name="comparison_outputs.zip",
                mime="application/zip"
            )


# ---------------------------
# Tab: Printed Ranges Editor
# ---------------------------
with tab_settings:
    st.subheader("Printed Footer Page Ranges Editor")

    overrides = load_overrides()
    ranges = overrides.get("KNOWN_PRINTED_RANGES", default_known_ranges())

    st.caption(
        "These are printed footer page ranges (the page number written at the bottom of the PDF page). "
        "They are converted to PDF indices automatically in the pipeline."
    )

    keys = sorted(ranges.keys())
    selected_key = st.selectbox("Company key (matched by IPO filename)", keys)
    c1, c2, c3 = st.columns(3)

    with c1:
        start_p = st.number_input(
            "Printed start page", min_value=1, max_value=5000, value=int(ranges[selected_key][0]))
    with c2:
        end_p = st.number_input("Printed end page", min_value=1,
                                max_value=5000, value=int(ranges[selected_key][1]))
    with c3:
        st.write("Example match:")
        st.code(
            f"If IPO name contains '{selected_key}', use {start_p}-{end_p}")

    if st.button("Update range"):
        ranges[selected_key] = [int(start_p), int(end_p)]
        overrides["KNOWN_PRINTED_RANGES"] = ranges
        save_overrides(overrides)
        st.success("Updated printed ranges and saved to dashboard_overrides.json")

    st.markdown("### Current ranges JSON")
    st.code(json.dumps(ranges, indent=2))

st.divider()
st.caption(f"Dashboard config file: {OVERRIDES_PATH}")
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
