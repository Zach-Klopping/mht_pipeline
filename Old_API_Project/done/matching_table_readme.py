import os
import re
from rapidfuzz import fuzz

readme_folder = '/Users/zachklopping/Desktop/List 25/Paper Outputs/Read Me/AER_txt'
table_folder = '/Users/zachklopping/Desktop/List 25/Paper Outputs/table_output_named'
output_file = "/Users/zachklopping/Desktop/List 25/Paper Outputs/Match One/matches.txt"
filtered_output_file = "/Users/zachklopping/Desktop/List 25/Paper Outputs/Match One/matches_gt85.txt"

def get_all_files_recursive(folder):
    """Recursively collects all files (with paths) in a folder."""
    filepaths = []
    for root, _, files in os.walk(folder):
        for f in files:
            filepaths.append(os.path.join(root, f))
    return filepaths

def extract_title_fingerprint(fname, is_table=False):
    name = fname
    if is_table and name.endswith(".pdf.txt"):
        name = name[:-len(".pdf.txt")]
    if not is_table and name.upper().startswith("README_"):
        name = name[len("README_"):]
    if not is_table and name.upper().endswith("_READ-ME.TXT"):
        name = name[:-len("_READ-ME.TXT")]
    name = re.sub(r"^[A-Z]+_\d+_", "", name)
    return name

def normalize_title(s):
    s = s.lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

# Gather all README and TABLE files from all subfolders
readme_files = get_all_files_recursive(readme_folder)
table_files = get_all_files_recursive(table_folder)

# Build a normalized list for READMEs (keys and file paths)
readme_keys = []
for f in readme_files:
    fname = os.path.basename(f)
    key = normalize_title(extract_title_fingerprint(fname))
    readme_keys.append((key, f))  # f is full path

matches = []

for t in table_files:
    tname = os.path.basename(t)
    table_key = normalize_title(extract_title_fingerprint(tname, is_table=True))
    best_score = 0
    best_readme = "NO_MATCH"
    best_rkey = ""
    for rkey, rfile in readme_keys:
        score = fuzz.partial_ratio(table_key, rkey)
        if score > best_score:
            best_score = score
            best_readme = rfile
            best_rkey = rkey
    matches.append((t, best_readme, best_score, best_rkey))

# Sort matches by score (descending)
matches.sort(key=lambda x: x[2], reverse=True)

print(f"Total TABLE files: {len(table_files)}")
print(f"  Matches found:   {sum(1 for m in matches if m[2] > 0)}")
print(f"  No matches:      {sum(1 for m in matches if m[2] == 0)}")

# Output to txt file (all matches)
with open(output_file, "w", encoding="utf-8") as out:
    for t, r, score, rkey in matches:
        out.write(f"TABLE:  {os.path.relpath(t, table_folder)}\n")
        out.write(f"README: {os.path.relpath(r, readme_folder) if r != 'NO_MATCH' else r}\n")
        out.write(f"SCORE:  {score}\n")
        out.write(f"README_KEY: {rkey}\n")
        out.write("\n" + "="*60 + "\n\n")

print(f"Done! Matches written to {output_file}")

# Output to txt file (filtered: score > 85)
count_gt85 = sum(1 for t, r, score, rkey in matches if score > 85)

with open(filtered_output_file, "w", encoding="utf-8") as out:
    for t, r, score, rkey in matches:
        if score > 85:
            out.write(f"TABLE:  {os.path.relpath(t, table_folder)}\n")
            out.write(f"README: {os.path.relpath(r, readme_folder) if r != 'NO_MATCH' else r}\n")
            out.write(f"SCORE:  {score}\n")
            out.write(f"README_KEY: {rkey}\n")
            out.write("\n" + "="*60 + "\n\n")

print(f"Done! High-score matches written to {filtered_output_file}")
print(f"Total matches with score > 85: {count_gt85}")
