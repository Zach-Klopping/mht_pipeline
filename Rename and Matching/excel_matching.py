#!/usr/bin/env python3
import os
from pathlib import Path
import re
import pandas as pd
from rapidfuzz import fuzz
import numpy as np

# ---------- Config ----------
PDF_FOLDER = '/Users/zachklopping/Desktop/John List/MHT/papers_pdfs/ECMA'
EXCEL_FILE = '/Users/zachklopping/Desktop/John List/MHT/Cleaned Excels/Econometrica_2000-2025.xlsx'
OUT_EXCEL  = '/Users/zachklopping/Desktop/John List/MHT/Fixed Data/Fully_Downloaded_Econometrica_2000-2025.xlsx'
UNMATCHED_PDFS_CSV = '/Users/zachklopping/Desktop/John List/MHT/Fixed Data/Econometrica_unmatched_pdfs.csv'
THRESHOLD = 90
# ----------------------------

def list_pdfs(folder: Path):
    return sorted([f for f in os.listdir(folder) if f.lower().endswith('.pdf')])

def norm_text(s: str) -> str:
    s = str(s).lower()
    s = re.sub(r'[_\-]+', ' ', s)       # unify separators into space
    s = re.sub(r'[^\w\s]', '', s)       # drop punctuation (keep letters, digits, underscores, spaces)
    s = re.sub(r'_', ' ', s)            # turn underscores into spaces
    s = re.sub(r'\s+', ' ', s).strip()  # collapse spaces
    return s

def clean_pdf_title(filename: str) -> str:
    return norm_text(Path(filename).stem)

def clean_excel_title(title: str) -> str:
    return norm_text(title)

def build_score_matrix(pdf_names, excel_titles):
    P, E = len(pdf_names), len(excel_titles)
    S = np.zeros((P, E), dtype=np.float32)
    for i, p in enumerate(pdf_names):
        p_clean = clean_pdf_title(p)
        for j, t in enumerate(excel_titles):
            t_clean = clean_excel_title(t)
            S[i, j] = fuzz.token_set_ratio(p_clean, t_clean)
    return S

def hungarian_assignment(scores, threshold):
    """Optimal 1-1 assignment using Hungarian (if SciPy available)."""
    try:
        from scipy.optimize import linear_sum_assignment
    except Exception:
        return None  # signal to use greedy

    cost = 100.0 - scores
    cost = np.where(scores >= threshold, cost, 1e6)

    row_ind, col_ind = linear_sum_assignment(cost)
    pairs = []
    for r, c in zip(row_ind, col_ind):
        score = float(scores[r, c])
        if score >= threshold and cost[r, c] < 1e6:
            pairs.append((r, c, score))
    return pairs

def greedy_assignment(scores, threshold):
    """Greedy fallback: pick highest remaining score >= threshold without conflicts."""
    P, E = scores.shape
    flat = [ (float(scores[i, j]), i, j) for i in range(P) for j in range(E) if scores[i, j] >= threshold ]
    flat.sort(reverse=True)
    used_p, used_e, pairs = set(), set(), []
    for score, i, j in flat:
        if i not in used_p and j not in used_e:
            pairs.append((i, j, score))
            used_p.add(i)
            used_e.add(j)
    return pairs

def main():
    pdf_dir = Path(PDF_FOLDER).expanduser().resolve()
    xlsx = Path(EXCEL_FILE).expanduser().resolve()

    df = pd.read_excel(xlsx)
    if "title" not in df.columns:
        raise ValueError("Excel file must have a 'title' column.")

    excel_titles = df["title"].astype(str).tolist()
    pdf_files = list_pdfs(pdf_dir)

    scores = build_score_matrix(pdf_files, excel_titles)

    pairs = hungarian_assignment(scores, THRESHOLD)
    if pairs is None:
        pairs = greedy_assignment(scores, THRESHOLD)

    downloaded = [0] * len(df)
    matched_pdfs = set()

    for pi, ej, sc in pairs:
        downloaded[ej] = 1
        matched_pdfs.add(pi)

    unmatched_pdfs = [pdf_files[i] for i in range(len(pdf_files)) if i not in matched_pdfs]

    # Write updated Excel
    df_out = df.copy()
    df_out["downloaded"] = downloaded
    df_out.to_excel(OUT_EXCEL, index=False)

    # Write unmatched PDFs CSV
    pd.DataFrame({"pdf_file": unmatched_pdfs}).to_csv(UNMATCHED_PDFS_CSV, index=False)

    print(f"Matched pairs: {len(pairs)} (threshold >= {THRESHOLD})")
    print(f"PDFs total: {len(pdf_files)} | unmatched PDFs: {len(unmatched_pdfs)}")
    print(f"Excel rows: {len(excel_titles)}")
    print(f"Wrote:\n  {OUT_EXCEL}\n  {UNMATCHED_PDFS_CSV}")

if __name__ == "__main__":
    main()
