#!/usr/bin/env python3
# QJE: rename PDFs using ALL-CAPS multi-line title on page 1
# - Saves to a "renamed" subfolder
# - Adds numeric suffix on collisions (no overwrite)
# - Prints ONLY when a suffix was added
# - Logs old -> new to rename_log.txt
# Procedural only — no OOP

import os
import re
import shutil
import pymupdf  # keep as pymupdf

# ========= CONFIG =========
input_dir = "/Users/zachklopping/Desktop/List 25/MHT/QJE copy"
output_dir = os.path.join(input_dir, "renamed")
prefix = "QJE_"
dry_run = False
log_file = os.path.join(input_dir, "rename_log.txt")

LINE_TOL       = 1.5    # pts: spans are same line if |y0 diff| <= LINE_TOL
TITLE_BAND_PT  = 2.0    # pts: subsequent ALL-CAPS lines allowed within this of first line's font size
TITLE_CONT_GAP = 14.0   # pts: stop title if vertical gap to next ALL-CAPS line exceeds this
LEFT_MARGIN    = 18.0   # pts: ignore near-left
RIGHT_MARGIN_FRAC = 0.97  # ignore near-right vertical strings
# ==========================

os.makedirs(output_dir, exist_ok=True)

def clean_title_for_filename(title: str) -> str:
    s = re.sub(r"\s+", " ", str(title)).strip()
    s = re.sub(r"[^A-Za-z0-9 _\-\(\)]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s  # no shortening

def build_target_path(folder: str, base: str) -> str:
    return os.path.join(folder, f"{prefix}{base}.pdf")

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

def is_all_caps(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    return bool(letters) and all(ch.isupper() for ch in letters)

def extract_title_first_page(pdf_path: str) -> str | None:
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        print(f"  ⚠️ Cannot open PDF: {e}")
        return None
    if len(doc) == 0:
        doc.close()
        return None

    page = doc[0]
    W = page.rect.width
    right_cutoff = W * RIGHT_MARGIN_FRAC
    data = page.get_text("dict")

    # collect ALL-CAPS spans
    spans = []  # (y0, x0, size, text)
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = (span.get("text") or "").strip()
                if not txt or not is_all_caps(txt):
                    continue
                x0, y0, x1, _ = span.get("bbox", (0, 0, 0, 0))
                if x0 < LEFT_MARGIN or x1 > right_cutoff:
                    continue
                size = float(span.get("size") or 0.0)
                spans.append((y0, x0, size, txt))

    if not spans:
        doc.close()
        return None

    # sort by y, then x
    spans.sort(key=lambda r: (round(r[0], 3), round(r[1], 3)))

    # group into lines using LINE_TOL
    lines = []  # list of dicts: {"y": y_ref, "texts": [...], "sizes": [...]}
    for y0, x0, size, txt in spans:
        if not lines:
            lines.append({"y": y0, "texts": [txt], "sizes": [size]})
            continue
        if abs(y0 - lines[-1]["y"]) <= LINE_TOL:
            lines[-1]["texts"].append(txt)
            lines[-1]["sizes"].append(size)
        else:
            lines.append({"y": y0, "texts": [txt], "sizes": [size]})

    # representative size per line (median is stable)
    for ln in lines:
        sizes = sorted(ln["sizes"])
        m = sizes[len(sizes)//2] if sizes else 0.0
        ln["size"] = float(m)

    # take the top ALL-CAPS line as anchor
    first = lines[0]
    anchor_size = first["size"]

    # accumulate consecutive ALL-CAPS lines (banded by size and gap)
    pieces = [" ".join(first["texts"])]
    prev_y = first["y"]

    for ln in lines[1:]:
        if (ln["y"] - prev_y) > TITLE_CONT_GAP:
            break
        if abs(ln["size"] - anchor_size) <= TITLE_BAND_PT:
            pieces.append(" ".join(ln["texts"]))
            prev_y = ln["y"]
        else:
            break

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

        # Base target in the output folder
        base_target = build_target_path(output_dir, safe)

        # If already correctly named *and* already in output folder, skip
        if os.path.abspath(src) == os.path.abspath(base_target):
            continue

        # Collision-safe path (adds suffix if needed)
        final_target = unique_path(base_target)
        new_name = os.path.basename(final_target)

        # Only print if a suffix was required (collision)
        if final_target != base_target:
            print(f"⚠️ Name collision; saving with suffix: {os.path.basename(base_target)} -> {new_name}")
            log.write(f"{fname} -> {new_name}  (SUFFIX)\n")
        else:
            log.write(f"{fname} -> {new_name}\n")

        if not dry_run:
            try:
                shutil.move(src, final_target)
                renamed += 1
            except Exception as e:
                print(f"  ❌ Rename failed for {fname}: {e}")
                skipped += 1

print(f"\nDone. Renamed: {renamed}, Skipped: {skipped}, Total: {len(pdfs)}")
print(f"Log saved to: {log_file}")
print(f"Renamed files are in: {output_dir}")
