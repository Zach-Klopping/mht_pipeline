#!/usr/bin/env python3
import os
import pymupdf  # install with: pip install pymupdf

# ========== CONFIG ==========
pdf_dir = '/Users/zachklopping/Desktop/John List/MHT/Bad/AER WE DONT WANT'# change to your folder

# ========== SCRIPT ==========
count_less_than_10 = 0
total_pdfs = 0

for fname in os.listdir(pdf_dir):
    if not fname.lower().endswith(".pdf"):
        continue
    total_pdfs += 1
    path = os.path.join(pdf_dir, fname)

    try:
        doc = pymupdf.open(path)
        n_pages = doc.page_count
        doc.close()

        if n_pages < 10:
            count_less_than_10 += 1

    except Exception as e:
        print(f"⚠️ Could not read {fname}: {e}")

print(f"Total PDFs scanned: {total_pdfs}")
print(f"PDFs with < 10 pages: {count_less_than_10}")
