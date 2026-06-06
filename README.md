## Team Members

- Smit Vaghani (@Smitt1803)
- Vidhi Gadge (@vidhigadge)
- Prisha Rana (@prisharana2024)

## IPO RHP Analyzer

- An end-to-end Financial Intelligence System that automatically extracts, analyzes, compares, and ranks IPOs directly from Red Herring Prospectus (RHP) PDFs.
- The system processes large IPO documents (500–1000+ pages), identifies financial statement sections, extracts key financial metrics, computes financial ratios, generates insights, ranks IPOs based on financial performance, and provides an interactive dashboard for exploration.

## Features

### Automated RHP Processing

- Upload one or multiple IPO RHP PDFs
- Handles large documents efficiently
- Automatic financial section detection
- Printed page number mapping support

### Financial Statement Extraction

Extracts:

- Revenue
- Profit After Tax (PAT)
- Total Assets
- Total Liabilities
- Equity
- Total Debt

### Smart Table Processing

- Financial page detection
- Table extraction from PDFs
- Multi-page table stitching
- Financial table classification
- Numeric reconstruction and cleaning

### Financial Analysis

Automatically computes:

- Debt-to-Equity Ratio
- Net Profit Margin
- Return on Assets (ROA)
- Revenue Growth
- Profit Growth

### IPO Ranking Engine

Ranks IPOs using a composite financial score based on:

- Profitability
- Asset Efficiency
- Revenue Growth
- Profit Growth
- Financial Leverage

### Automated Insights

Generates rule-based insights such as:

- Profitability assessment
- Growth analysis
- Debt risk evaluation
- Asset utilization commentary

### Visualization Dashboard

Interactive Streamlit dashboard featuring:

- IPO explorer
- Financial trend analysis
- Ratio visualization
- Ranking comparison
- Downloadable outputs

## System Architecture

```bash
RHP PDF
   │
   ▼
Financial Page Detection
   │
   ▼
Table Extraction
   │
   ▼
Table Stitching
   │
   ▼
Financial Data Extraction
   │
   ▼
Ratio Computation
   │
   ▼
Final Financial Table
   │
   ▼
IPO Comparison
   │
   ▼
Scoring & Ranking
   │
   ▼
Insights Generation
   │
   ▼
Dashboard Visualization
```

## Project Structure

```bash
IPO-RHP-Analyzer/
│
├── app.py                         # Streamlit Dashboard
├── main_pipeline.py               # Main pipeline orchestrator
├── config.py                      # Configuration settings
│
├── modules/
│   ├── extractor.py
│   ├── page_detector.py
│   ├── page_number_mapper.py
│   ├── section_splitter.py
│   ├── table_dumper.py
│   ├── table_filter.py
│   ├── table_stitcher.py
│   ├── financial_classifier.py
│   ├── financial_extractor.py
│   ├── analysis_engine.py
│   ├── final_table_builder.py
│   ├── comparison_engine.py
│   ├── scoring_engine.py
│   ├── insight_engine.py
│   ├── visualization_engine.py
│   └── utils.py
│
├── rhp_inputs/                    # Input PDFs
│
├── outputs/
│   ├── processed_ipos/
│   └── comparison/
│
├── dashboard_overrides.json
├── requirements.txt
└── README.md
```

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/your-username/IPO-RHP-Analyzer.git
cd IPO-RHP-Analyzer
```

### 2. Create Virtual Environment

Windows

```bash
python -m venv venv
venv\Scripts\activate
```

Linux / Mac

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Required Libraries

- pandas
- numpy
- pdfplumber
- rapidfuzz
- matplotlib
- streamlit
- python-dotenv
- requests

## Environment Variables

Create a .env file:

```bash
GEMINI_API_KEY=your_api_key_here
```

## Running the Project

### Option 1: Run Full Pipeline

```bash
python main_pipeline.py
```

The pipeline will:

1. Detect financial pages
2. Extract tables
3. Stitch fragmented tables
4. Extract financial metrics
5. Compute ratios
6. Build comparison dataset
7. Rank IPOs
8. Generate insights
9. Create visualizations

### Option 2: Launch Dashboard

```bash
streamlit run app.py
```

## Output Files

### 1. Per IPO

```bash
outputs/
└── processed_ipos/
    └── IPO_NAME/
        ├── financials.csv
        ├── ratios.csv
        ├── final_table.csv
        ├── financials_debug.json
        ├── stitched_tables/
        └── dumped_tables/
```

### 2. financials.csv

```bash
Year
Revenue
Profit
TotalAssets
TotalLiabilities
Equity
TotalDebt
```

### 3. ratios.csv

```bash
DebtEquityRatio
NetProfitMargin
ROA
RevenueGrowth
ProfitGrowth
```

### 4. Comparison Outputs

```bash
outputs/comparison/

├── master_final_table_by_year.csv
├── ipo_summary_for_scoring.csv
├── scored_ipo_comparison.csv
├── ipo_interpretation.txt
├── composite_score.png
├── revenue_growth.png
└── net_profit_margin.png
```

## Scoring Methodology

Composite Score:

```bash
Score =
0.30 × Net Profit Margin
+ 0.25 × ROA
+ 0.15 × Revenue Growth
+ 0.10 × Profit Growth
- 0.20 × Debt-to-Equity
```

Additional processing:

- Missing value handling
- Outlier clipping (5th–95th percentile)
- Quantile-based categorization

Categories:

- Better
- Moderate
- Not Recommended

## Use Cases

### Retail Investors

Compare multiple IPOs using objective financial metrics.

### Financial Analysts

Reduce manual effort in extracting financial statements from RHPs.

### Research & Academia

Study IPO financial health and performance trends.

### FinTech Applications

Integrate automated IPO analysis into investment platforms.

## Future Enhancements

- LLM-powered financial insights
- Risk factor extraction from RHPs
- Sentiment analysis
- RAG-based IPO Q&A system
- Industry benchmarking
- Predictive IPO scoring using Machine Learning
- Automated investment recommendation engine
- Multi-document financial comparison

## Tech Stack

### Backend

- Python
- Pandas
- NumPy

### PDF Processing

- pdfplumber
- RapidFuzz

### Visualization

- Matplotlib

### Dashboard

- Streamlit

### AI/LLM (Future Scope)

- Gemini API
- RAG Pipelines
- Financial NLP

## License

This project is developed for educational, research, and financial analytics purposes.
