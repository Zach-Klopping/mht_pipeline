import os
import shutil
import pandas as pd

# ==== CONFIG ====
CSV_PATH      = '/Users/zachklopping/Desktop/John List/MHT/Fixed Data/Econometrica_unmatched_pdfs.csv'         # CSV with a 'title' column
SOURCE_FOLDER = '/Users/zachklopping/Desktop/John List/MHT/papers_pdfs/ECMA'     # where PDFs are now
DEST_FOLDER   = '/Users/zachklopping/Desktop/John List/MHT/ECMA WE DONT WANT' # where to move them

# Make sure destination exists
os.makedirs(DEST_FOLDER, exist_ok=True)

# Load titles (assume they include the .pdf extension)
df = pd.read_csv(CSV_PATH)
titles = df["pdf_file"].dropna().tolist()

# Move matching PDFs
moved_count = 0
for title in titles:
    src_path = os.path.join(SOURCE_FOLDER, title)
    dest_path = os.path.join(DEST_FOLDER, title)

    if os.path.isfile(src_path):
        shutil.move(src_path, dest_path)
        print(f"✅ Moved: {title}")
        moved_count += 1
    else:
        print(f"⚠️ Not found: {title}")

print(f"\nDone! {moved_count} files moved to {DEST_FOLDER}")
