import pymupdf
import re
import os
import tiktoken
from collections import defaultdict

# === CONFIGURATION ===
pdf_folder = "/Users/zachklopping/Desktop/List 25/papers_pdfs/AER_New2"
output_dir = "/Users/zachklopping/Desktop/Paper Outputs Old/Chunks/batch_6"
MAX_TOKENS = 15_000 # GPT-4 Turbo safe input size

os.makedirs(output_dir, exist_ok=True)
encoding = tiktoken.encoding_for_model("gpt-4")  # or gpt-3.5-turbo

# Regex patterns
label_pattern = re.compile(r'\b(Table)\s+\d+\b')
sentence_splitter = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

# === Step 1: Extract data from up to MAX_PDFS PDFs ===
all_pdfs = sorted([f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")])
papers = []

for filename in all_pdfs:
    file_path = os.path.join(pdf_folder, filename)
    grouped_mentions = defaultdict(list)

    try:
        doc = pymupdf.open(file_path)

        for page_number, page in enumerate(doc, start=1):
            text = page.get_text()
            if not text:
                continue

            sentences = sentence_splitter.split(text.replace("\n", " "))

            for idx, sentence in enumerate(sentences):
                for match in label_pattern.findall(sentence):
                    raw_label = re.search(r'\b(Table)\s+[A-Za-z]?\d+\b', sentence)
                    if raw_label:
                        label_text = re.sub(r'\s+', ' ', raw_label.group().replace('\u00A0', ' ')).strip()
                        raw_context = sentences[max(0, idx - 2): idx + 3]

                        clean_context = []
                        for s in raw_context:
                            s = s.strip()
                            if 10 < len(s) < 500 and not re.search(r'\.{3,}|\s{5,}', s):
                                clean_context.append(s)

                        context = " ".join(clean_context).strip()
                        grouped_mentions[label_text].append((page_number, context))
    except Exception as e:
        print(f"❌ Error processing {filename}: {e}")
        continue

    # Build full output text for this PDF
    paper_text = f"=== {filename} ===\n"
    for label, occurrences in sorted(grouped_mentions.items()):
        paper_text += f"\n=== {label} ===\n"
        for page_num, context in occurrences:
            paper_text += f"Page {page_num}: {context}\n\n"

    papers.append((filename, paper_text))
    print(f"{filename}: {sum(len(v) for v in grouped_mentions.values())} total labeled matches found.")

# === Step 2: Chunk papers together without breaking them ===
chunks = []
current_chunk = []
current_token_count = 0

for filename, content in papers:
    token_len = len(encoding.encode(content))

    if current_token_count + token_len > MAX_TOKENS and current_chunk:
        chunks.append(current_chunk)
        current_chunk = []
        current_token_count = 0

    current_chunk.append((filename, content))
    current_token_count += token_len

if current_chunk:
    chunks.append(current_chunk)

# === Step 3: Save chunk files ===
for i, chunk in enumerate(chunks):
    # Calculate the subfolder index (starting from 1)
    folder_idx = i // 100 + 1
    subfolder = os.path.join(output_dir, f"batch_{folder_idx}")
    os.makedirs(subfolder, exist_ok=True)  # Create subfolder if it doesn't exist
    
    out_path = os.path.join(subfolder, f"chunk_{i+1}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        for filename, content in chunk:
            f.write(content + "\n")
    print(f"✅ Saved {out_path} ({len(chunk)} papers)")

print(f"\n✅ Finished. Total chunks created: {len(chunks)}")
total_tokens = sum(len(encoding.encode(content)) for _, content in papers)
print(f"\n🔢 Total tokens across all papers: {total_tokens:,}")
