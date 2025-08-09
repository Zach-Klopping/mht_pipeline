import pymupdf
import os
import tiktoken

# === CONFIGURATION ===
pdf_folder = '/Users/zachklopping/Desktop/List 25/Paper Outputs/Read Me/AER_pdf 2'
output_dir = '/Users/zachklopping/Desktop/List 25/Paper Outputs/Read Me/AER_txt2'

os.makedirs(output_dir, exist_ok=True)
encoding = tiktoken.encoding_for_model("gpt-4")

all_pdfs = sorted([f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")])

for filename in all_pdfs:
    file_path = os.path.join(pdf_folder, filename)
    base_name = os.path.splitext(filename)[0]
    try:
        doc = pymupdf.open(file_path)
        text = ""
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n"
        header = f"=== {filename} ===\n"
        full_text = header + text.strip() + "\n"
        
        # Prepend 'readme_' if not already at the front
        if not base_name.lower().startswith("readme"):
            out_base = "readme_" + base_name
        else:
            out_base = base_name
        out_path = os.path.join(output_dir, f"{out_base}.txt")
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"✅ {filename}: Saved as {out_base}.txt")
    except Exception as e:
        print(f"❌ Error processing {filename}: {e}")
