import os
import json
from collections import defaultdict

folder = '/Users/zachklopping/Desktop/List 25/Paper Outputs/table_output/batch_6'
output_folder = '/Users/zachklopping/Desktop/List 25/Paper Outputs/table_output_named/batch_2'

paper_quotes = defaultdict(list)

# Walk through all subfolders and files
for root, dirs, files in os.walk(folder):
    for fname in files:
        if fname.endswith(".txt"):
            file_path = os.path.join(root, fname)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw = f.read()
                    cleaned = "\n".join(
                        line for line in raw.splitlines()
                        if line.strip() not in ("```json", "```")
                    )
                    data = json.loads(cleaned)
                    for entry in data:
                        paper = entry["paper"]
                        quote = entry["quote"]
                        table = entry.get("table")
                        if table:
                            paper_quotes[paper].append(f"{table}: {quote}")
                        else:
                            paper_quotes[paper].append(quote)
            except Exception as e:
                print(f"Skipping {file_path}: {e}")

# Write all quotes to corresponding {paper}.txt files
for paper, quotes in paper_quotes.items():
    out_path = os.path.join(output_folder, f"{paper}.txt")
    with open(out_path, "a", encoding="utf-8") as outf:  # Change "a" to "w" to overwrite
        outf.write(f"Paper: {paper}\n\n")
        for q in quotes:
            outf.write(q + "\n\n")
    print(f"Wrote {len(quotes)} quotes to {out_path}")

print("Done!")
