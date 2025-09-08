#!/usr/bin/env python3
import os
import re
import shutil
import pymupdf  # keep as pymupdf everywhere

# ========= CONFIG (edit these paths) =========
input_dir  = '/Users/zachklopping/Desktop/John List/MHT/papers_pdfs/ECMA Done'
notes_dir  = '/Users/zachklopping/Desktop/John List/MHT/ECMA Notes and Comments'
dry_run    = False                                           # True = preview only
log_file   = '/Users/zachklopping/Desktop/John List/MHT/ECMA Notes and Comments/notes_and_comments_log.txt'

# Detection region (top portion of page 1 to scan)
TOP_FRACTION = 0.5   # check top 50% of page 1
# ============================================

os.makedirs(notes_dir, exist_ok=True)

def unique_path(path: str) -> str:
    """Return a non-existing path; add _1, _2, ... before extension if needed."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    n = 1
    while True:
        cand = f"{root}_{n}{ext}"
        if not os.path.exists(cand):
            return cand
        n += 1

def looks_like_notes_and_comments(pdf_path: str, top_fraction: float = TOP_FRACTION) -> bool:
    """
    Returns True if 'NOTES AND COMMENTS' (or 'NOTES & COMMENTS') appears in the
    top portion of page 1.
    """
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        return False

    if len(doc) == 0:
        doc.close()
        return False

    try:
        page = doc[0]
        page_h = page.rect.height
        y_cut = page_h * top_fraction

        data = page.get_text("dict")
        target_re = re.compile(r"\bnotes\s*(?:&|and)\s*comments\b", re.I)

        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = (span.get("text") or "").strip()
                    if not txt:
                        continue
                    _, y0, _, _ = span.get("bbox", (0, 0, 0, 0))
                    if y0 > y_cut:
                        continue
                    if target_re.search(txt):
                        doc.close()
                        return True
    except Exception:
        pass

    doc.close()
    return False

# =========================
# MAIN (only move Notes & Comments)
# =========================
if not os.path.isdir(input_dir):
    raise SystemExit(f"Input dir not found: {input_dir}")

pdfs = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
print(f"Scanning {len(pdfs)} PDFs in: {input_dir}")

moved, skipped = 0, 0

with open(log_file, "w", encoding="utf-8") as log:
    for fname in pdfs:
        src = os.path.join(input_dir, fname)

        if looks_like_notes_and_comments(src):
            dest = unique_path(os.path.join(notes_dir, fname))
            try:
                if not dry_run:
                    shutil.move(src, dest)
                log.write(f"{fname} -> NOTES_AND_COMMENTS/{os.path.basename(dest)}\n")
                moved += 1
            except Exception as e:
                print(f"  ❌ Move failed for {fname}: {e}")
                skipped += 1
        else:
            # Not a Notes & Comments article: leave it untouched
            skipped += 1

print(f"\nDone. Moved (Notes & Comments): {moved}, Left untouched: {skipped}, Total scanned: {len(pdfs)}")
print(f"Log saved to: {log_file}")
print(f"Notes & Comments files are in: {notes_dir}")
