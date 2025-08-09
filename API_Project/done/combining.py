import os

table_folder = '/Users/zachklopping/Desktop/List 25/Paper Outputs/table_output_named'
readme_folder = "/Users/zachklopping/Desktop/List 25/Paper Outputs/Read Me/AER_txt"
matches_file = "/Users/zachklopping/Desktop/List 25/Paper Outputs/Match One/matches_gt85.txt"
output_folder = "/Users/zachklopping/Desktop/List 25/Paper Outputs/Match One/combined_files"
os.makedirs(output_folder, exist_ok=True)

def safe_read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        print(f"❌ UnicodeDecodeError: {path}")
        return None
    except Exception as e:
        print(f"❌ Error reading {path}: {e}")
        return None

# Read and parse matches file
with open(matches_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

pairs = []
table_file = None
readme_file = None
readme_key = None

for line in lines:
    if line.startswith("TABLE:"):
        table_file = line.split("TABLE:")[1].strip()
    elif line.startswith("README:"):
        readme_file = line.split("README:")[1].strip()
    elif line.startswith("README_KEY:"):
        readme_key = line.split("README_KEY:")[1].strip()
    elif line.strip() == "" and table_file and readme_file and readme_key:
        pairs.append((table_file, readme_file, readme_key))
        table_file, readme_file, readme_key = None, None, None

count = 0
for table_fn, readme_fn, rkey in pairs:
    table_path = os.path.join(table_folder, table_fn)
    readme_path = os.path.join(readme_folder, readme_fn)
    if not os.path.exists(table_path):
        print(f"Table file missing: {table_fn}")
        continue
    if not os.path.exists(readme_path):
        print(f"README file missing: {readme_fn}")
        continue
    table_content = safe_read(table_path)
    readme_content = safe_read(readme_path)
    if table_content is None or readme_content is None:
        print(f"⏭️ Skipping pair: {table_fn}, {readme_fn}")
        continue
    nice_key = rkey.title().replace(" ", "_")
    combined_name = f"{nice_key}.txt"
    combined_path = os.path.join(output_folder, combined_name)
    with open(combined_path, "w", encoding="utf-8") as outfile:
        outfile.write(table_content)
        outfile.write("\n\n" + "="*40 + "\n\n")
        outfile.write(readme_content)
    count += 1

print("✅ All high-score pairs combined!")
print(f"Total combined files: {count}")
