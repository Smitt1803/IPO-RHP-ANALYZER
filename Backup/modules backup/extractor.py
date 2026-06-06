import os
import fitz  # PyMuPDF

# Auto-detect project base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extract_text_from_pdf(pdf_path, output_folder):

    doc = fitz.open(pdf_path)
    full_text = []
    for page in doc:
        text = page.get_text("text")  # Use "text" mode for better structure
        full_text.append(text)
    full_text = "\n".join(full_text)

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Open PDF
    doc = fitz.open(pdf_path)
    full_text = ""

    for page in doc:
        full_text += page.get_text()

    # Save raw text inside IPO-specific folder
    raw_path = os.path.join(output_folder, "raw_text.txt")

    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    return full_text
