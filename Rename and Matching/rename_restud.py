#!/usr/bin/env python3
# Rename PDFs using largest-font spans on page 1 (ReSTUD)
# Procedural only — no OOP, no argparse
# - Saves renamed files into a "renamed" subfolder
# - On collision, adds a numeric suffix (_1, _2, ...) instead of overwriting
# - Prints only when a suffix is added
# - Logs old -> new filename to rename_log.txt

import os
import re
import shutil
import pymupdf  # use as pymupdf everywhere

# ========= CONFIG =========
input_dir = '/Users/zachklopping/Desktop/John List/MHT/RESTUD Scraped Papers'
output_dir = os.path.join(input_dir, "renamed")   # destination folder for renamed PDFs
prefix = "ReSTUD_"     # prefix for renamed files
dry_run = False        # True = only record actions, don't rename
log_file = os.path.join(input_dir, "rename_log.txt")
FONT_TOL = 0.05        # accept spans within this size tolerance of the max (in pt)
# ==========================

# prepare output folder
os.makedirs(output_dir, exist_ok=True)

def clean_title_for_filename(title: str) -> str:
    s = re.sub(r"\s+", " ", str(title)).strip()
    # allow only letters, digits, space, underscore, hyphen, parentheses
    s = re.sub(r"[^A-Za-z0-9 _\-\(\)]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s  # no shortening

def build_target_path(folder: str, base: str) -> str:
    """Base target path (without collision handling)."""
    return os.path.join(folder, f"{prefix}{base}.pdf")

def unique_path(path: str) -> str:
    """
    If 'path' exists, append _1, _2, ... before the extension until it's unique.
    Returns the first non-existing path.
    """
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    n = 1
    while True:
        candidate = f"{root}_{n}{ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1

def extract_title_first_page(pdf_path: str) -> str | None:
    """
    Open PDF, inspect ONLY page 1.
    1) Find the maximum span font size on the page.
    2) Collect ALL spans at that size (within FONT_TOL).
    3) Sort by (y0, x0) and join with spaces to reconstruct multi-line titles.
    """
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        print(f"  ⚠️ Cannot open PDF: {e}")
        return None
    if len(doc) == 0:
        doc.close()
        return None

    page = doc[0]
    data = page.get_text("dict")

    spans = []
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = (span.get("text") or "").strip()
                if not txt:
                    continue
                size = float(span.get("size") or 0.0)
                x0, y0, _, _ = span.get("bbox", (0, 0, 0, 0))
                spans.append((size, y0, x0, txt))

    if not spans:
        doc.close()
        return None

    # 1) max font size
    max_size = max(s for (s, _, _, _) in spans)

    # 2) keep all spans at that size within tolerance
    keep = [(s, y, x, t) for (s, y, x, t) in spans if abs(s - max_size) <= FONT_TOL]
    if not keep:
        doc.close()
        return None

    # 3) sort top-to-bottom, then left-to-right, then join
    keep.sort(key=lambda r: (round(r[1], 3), round(r[2], 3)))  # stabilize order
    pieces = [t for (_, _, _, t) in keep]
    title = " ".join(pieces)
    title = re.sub(r"\s+", " ", title).strip()

    doc.close()
    return title if title else None

# =========================
# MAIN PROCEDURAL LOGIC
# =========================
if not os.path.isdir(input_dir):
    raise SystemExit(f"Input dir not found: {input_dir}")

pdfs = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
print(f"Found {len(pdfs)} PDFs in: {input_dir}")

renamed, skipped = 0, 0

with open(log_file, "w", encoding="utf-8") as log:
    for fname in pdfs:
        src = os.path.join(input_dir, fname)

        title = extract_title_first_page(src)
        if not title:
            skipped += 1
            continue

        safe = clean_title_for_filename(title)
        if not safe:
            skipped += 1
            continue

        # base target in the output folder
        base_target = build_target_path(output_dir, safe)

        # if already correctly named *and* already in output folder, skip
        if os.path.abspath(src) == os.path.abspath(base_target):
            continue

        # collision-safe target with numeric suffix if needed
        final_target = unique_path(base_target)
        new_name = os.path.basename(final_target)

        # Only print if a suffix was required (i.e., collision would have overwritten)
        if final_target != base_target:
            print(f"⚠️ Name collision; saving with suffix: {os.path.basename(base_target)} -> {new_name}")
            log.write(f"{fname} -> {new_name}  (SUFFIX)\n")
        else:
            log.write(f"{fname} -> {new_name}\n")

        if not dry_run:
            try:
                # move into output folder with the unique name
                shutil.move(src, final_target)
                renamed += 1
            except Exception as e:
                print(f"  ❌ Rename failed for {fname}: {e}")
                skipped += 1

print(f"\nDone. Renamed: {renamed}, Skipped: {skipped}, Total: {len(pdfs)}")
print(f"Log saved to: {log_file}")
print(f"Renamed files are in: {output_dir}")
