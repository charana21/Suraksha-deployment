"""Read and extract all text from the Telugu States 2026 Holidays PDF."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

PDF_PATH = r"c:\Users\harshini\Documents\crowd-backend\Telugu_States_2026_Holidays_and_Festivals.pdf"

# Try PyMuPDF (fitz) first
try:
    import fitz  # PyMuPDF
    doc = fitz.open(PDF_PATH)
    text = ""
    for page_num, page in enumerate(doc):
        text += f"\n===== PAGE {page_num + 1} =====\n"
        text += page.get_text()
    print(text)
    sys.exit(0)
except ImportError:
    pass

# Try pdfplumber
try:
    import pdfplumber
    with pdfplumber.open(PDF_PATH) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"\n===== PAGE {i + 1} =====")
            print(page.extract_text())
    sys.exit(0)
except ImportError:
    pass

# Try pypdf
try:
    from pypdf import PdfReader
    reader = PdfReader(PDF_PATH)
    for i, page in enumerate(reader.pages):
        print(f"\n===== PAGE {i + 1} =====")
        print(page.extract_text())
    sys.exit(0)
except ImportError:
    pass

# Try pdfminer
try:
    from pdfminer.high_level import extract_text
    text = extract_text(PDF_PATH)
    print(text)
    sys.exit(0)
except ImportError:
    pass

print("ERROR: No PDF library found. Install: pip install pymupdf OR pdfplumber OR pypdf")
