import os
import re
import shutil
import pymupdf  # keep as pymupdf everywhere

# ========= CONFIG (edit these paths) =========
input_dir  = '/Users/zachklopping/Desktop/John List/MHT/ECMA Old Scraped Papers'
output_dir = os.path.join(input_dir, "renamed")
prefix     = "ECMA_"          # filename prefix
dry_run    = False            # True = record-only; do not move files
log_file   = os.path.join(input_dir, "rename_log.txt")

# Heuristics tuned for Econometrica layout/typography
FONT_BAND     = 1.0           # keep spans within ± this many pt of max title size
LINE_TOL      = 1.8           # spans are same line if |y0 diff| <= LINE_TOL
TOP_FRACTION1 = 0.35          # top region of page 1 to consider (title sits below masthead)
TOP_FRACTION2 = 0.35          # same for page 2 if we need a fallback
# ============================================

os.makedirs(output_dir, exist_ok=True)

def clean_title_for_filename(title: str) -> str:
    """Conservative filename sanitizer; keep basic ASCII and a few safe symbols."""
    s = re.sub(r"\s+", " ", str(title)).strip()
    s = re.sub(r"[^A-Za-z0-9 _\-\(\)]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s  # no truncation

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

def looks_like_header(t: str) -> bool:
    """Filter out masthead and boilerplate on ECMA page 1 (and sometimes 2)."""
    tl = t.lower()
    if "econometrica" in tl:
        return True
    if "vol." in tl or "no." in tl:
        return True
    if re.search(r"\b(19|20)\d{2}\b", tl):  # years
        return True
    if re.match(r"^\s*by\b", tl):  # author line
        return True
    if re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", tl):
        return True
    return False

def is_boldish(span_font: str, span_flags: int | None, text: str) -> bool:
    """
    ECMA titles are often NOT 'bold'. Treat a span as 'title-like' if:
    - the font name hints at bold OR
    - the text is all caps (at least 3 letters).
    """
    if isinstance(span_font, str) and any(k in span_font.lower() for k in ("bold", "black", "demi", "semibold")):
        return True
    letters = re.sub(r"[^A-Za-z]", "", text)
    return len(letters) >= 3 and letters.upper() == letters

def collect_top_spans(page, top_fraction: float):
    """Return spans from the top portion of a page: (size, y0, x0, text, font, flags)."""
    page_h = page.rect.height
    y_cut = page_h * top_fraction
    data = page.get_text("dict")
    out = []
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = (span.get("text") or "").strip()
                if not txt:
                    continue
                x0, y0, _, _ = span.get("bbox", (0, 0, 0, 0))
                if y0 > y_cut:
                    continue
                size  = float(span.get("size") or 0.0)
                font  = span.get("font")
                flags = span.get("flags")
                out.append((size, y0, x0, txt, font, flags))
    return out

def spans_to_title(spans):
    """From a list of candidate spans, pick the largest-size band, prefer 'boldish', merge lines, and clean."""
    if not spans:
        return None
    # Drop masthead/boilerplate
    spans = [(s,y,x,t,f,fl) for (s,y,x,t,f,fl) in spans if not looks_like_header(t)]
    if not spans:
        return None

    max_size = max(s for (s,_,_,_,_,_) in spans)
    band = [(s,y,x,t,f,fl) for (s,y,x,t,f,fl) in spans if abs(s - max_size) <= FONT_BAND]
    if not band:
        return None

    # Prefer 'boldish' within the band
    pref = [r for r in band if is_boldish(r[4], r[5], r[3])]
    keep = pref if pref else band

    # Sort and merge by line proximity
    keep.sort(key=lambda r: (round(r[1], 3), round(r[2], 3)))  # by y, then x
    lines = []  # [y_ref, [texts]]
    for s,y,x,t,f,fl in keep:
        if not lines:
            lines.append([y, [t]])
            continue
        y_ref, texts = lines[-1]
        if abs(y - y_ref) <= LINE_TOL:
            texts.append(t)
        else:
            lines.append([y, [t]])

    # Join lines -> title
    pieces = [" ".join(texts) for (_, texts) in lines]
    title = " ".join(pieces)
    title = re.sub(r"\s+", " ", title).strip()
    # Trim trailing "by ..." fragments if any slipped in
    title = re.sub(r"\s+\bby\b.*$", "", title, flags=re.I).strip()
    return title or None

def extract_title_first_pages_ecma(pdf_path: str) -> str | None:
    """Try page 1; if it fails, try page 2 (some ECMA PDFs push title after front matter)."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        print(f"  ⚠️ Cannot open PDF: {e}")
        return None
    if len(doc) == 0:
        doc.close()
        return None

    # Page 1
    try:
        spans1 = collect_top_spans(doc[0], TOP_FRACTION1)
        t1 = spans_to_title(spans1)
        if t1:
            doc.close()
            return t1
    except Exception:
        pass

    # Page 2 (fallback)
    if len(doc) >= 2:
        try:
            spans2 = collect_top_spans(doc[1], TOP_FRACTION2)
            t2 = spans_to_title(spans2)
            if t2:
                doc.close()
                return t2
        except Exception:
            pass

    doc.close()
    return None

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

        title = extract_title_first_pages_ecma(src)
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
