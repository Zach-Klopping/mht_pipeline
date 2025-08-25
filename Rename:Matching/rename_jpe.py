#!/usr/bin/env python3
# JPE: rename PDFs using largest-font BOLD title on page 1
# - Saves to a "renamed" subfolder
# - Adds numeric suffix on collisions (no overwrite)
# - Prints ONLY when a suffix was added
# - Logs old -> new to rename_log.txt
# Procedural only — no OOP

import os
import re
import shutil
import pymupdf  # keep as pymupdf everywhere

# ========= CONFIG =========
input_dir = "/Users/zachklopping/Desktop/List 25/MHT/JPE_New"
output_dir = os.path.join(input_dir, "renamed")
prefix = "JPE_"        # prefix for renamed files
dry_run = False        # True = only record actions, don't move
log_file = os.path.join(input_dir, "rename_log.txt")

FONT_BAND   = 0.1      # keep spans within ± this many pt of max title size
LINE_TOL    = 1.5      # spans are same line if |y0 diff| <= LINE_TOL
TOP_FRACTION = 0.2     # only consider spans in the top 20% of the page
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

def is_bold(span_font: str, span_flags: int | None) -> bool:
    # Heuristic: font name indicates boldness
    return isinstance(span_font, str) and any(k in span_font.lower() for k in ("bold", "black", "demi", "semibold"))

def extract_title_first_page_jpe(pdf_path: str) -> str | None:
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        print(f"  ⚠️ Cannot open PDF: {e}")
        return None
    if len(doc) == 0:
        doc.close()
        return None

    page = doc[0]
    page_h = page.rect.height
    y_cut = page_h * TOP_FRACTION

    data = page.get_text("dict")

    # Collect spans from the TOP of the page only
    spans = []  # (size, y0, x0, text, font, flags)
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = (span.get("text") or "").strip()
                if not txt:
                    continue
                x0, y0, _, _ = span.get("bbox", (0, 0, 0, 0))
                if y0 > y_cut:
                    continue  # ignore below the top region
                size  = float(span.get("size") or 0.0)
                font  = span.get("font")
                flags = span.get("flags")
                spans.append((size, y0, x0, txt, font, flags))

    if not spans:
        doc.close()
        return None

    # Find maximum font size in the top region
    max_size = max(s for (s, _, _, _, _, _) in spans)

    # Keep spans in size band
    band_spans = [(s, y, x, t, f, fl) for (s, y, x, t, f, fl) in spans if abs(s - max_size) <= FONT_BAND]
    if not band_spans:
        doc.close()
        return None

    # Prefer BOLD spans within the band; if none bold, use the whole band
    bold_spans = [r for r in band_spans if is_bold(r[4], r[5])]
    keep = bold_spans if bold_spans else band_spans

    # Sort and group into lines
    keep.sort(key=lambda r: (round(r[1], 3), round(r[2], 3)))  # sort by y, then x
    lines = []  # list of [y_ref, [texts]]
    for s, y, x, t, f, fl in keep:
        if not lines:
            lines.append([y, [t]])
            continue
        y_ref, texts = lines[-1]
        if abs(y - y_ref) <= LINE_TOL:
            texts.append(t)
        else:
            lines.append([y, [t]])

    # Join lines => title
    pieces = [" ".join(texts) for (y_ref, texts) in lines]
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

        title = extract_title_first_page_jpe(src)
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

        # Make collision-safe path (adds suffix if needed)
        final_target = unique_path(base_target)
        new_name = os.path.basename(final_target)

        # Only print if a suffix was required
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
