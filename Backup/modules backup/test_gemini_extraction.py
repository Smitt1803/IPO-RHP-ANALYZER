from google import genai
from google.genai import types
import json
import re

# import your config
from config import GEMINI_API_KEY1

if not GEMINI_API_KEY1:
    raise EnvironmentError("GEMINI_API_KEY1 not set in config.py")

client = genai.Client(api_key=GEMINI_API_KEY1)


# ----------------------------------------
# Trim Financial Section Before Sending
# ----------------------------------------
def trim_financial_section(text):

    keywords = [
        "Revenue from operations",
        "Profit/(loss) for the period",
        "Profit for the year",
        "Total assets",
        "Total liabilities"
    ]

    lines = text.split("\n")
    collected = []

    for i, line in enumerate(lines):
        for keyword in keywords:
            if keyword.lower() in line.lower():

                # capture this line + next 6 lines
                block = lines[i:i+7]
                collected.extend(block)

    return "\n".join(collected)


# ----------------------------------------
# Load Financial Section
# ----------------------------------------
with open(
    r"E:\\404found\\Projects\\PBL Final\\IPO_Automation_System\\outputs\\processed_ipos\\Groww Billionbrains Garage Ventures Limited - RHP\\sections\\financials.txt",
    "r",
    encoding="utf-8"
) as f:
    financial_text = f.read()


trimmed_text = trim_financial_section(financial_text)


# ----------------------------------------
# Prompt
# ----------------------------------------
prompt = f"""
You are a strict financial data extraction engine.

DO NOT summarize.
DO NOT interpret.
DO NOT calculate.
DO NOT hallucinate.

Extract ONLY values from 31 March 2025 column.

Return EXACT numbers.

If value not clearly found, return 0.

Return ONLY valid JSON in this format:

{{
  "revenue": number,
  "profit": number,
  "assets": number,
  "liabilities": number
}}

Financial Data:
{trimmed_text}
"""


# ----------------------------------------
# Gemini Call
# ----------------------------------------
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=[
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ],
)

print("\nRAW RESPONSE:\n")
print(response.text)


# ----------------------------------------
# Safe JSON Parsing
# ----------------------------------------
try:
    # Extract JSON block safely using regex
    json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
    if json_match:
        data = json.loads(json_match.group())
        print("\nPARSED JSON:\n", data)
    else:
        print("\n❌ JSON block not found.")
except Exception as e:
    print("\n❌ JSON parsing failed:", e)
