#!/usr/bin/env python3
# pip install openai==1.* (or the latest SDK)
# export OPENAI_API_KEY=...

from openai import OpenAI
import os, json, pathlib

PDF_PATH = "your-paper.pdf"     # <- change this
MODEL = "gpt-5"                 # try "gpt-4.1" or "gpt-4o" if needed
OUT_SUFFIX = "_analysis.json"

PDF_PATH = '/Users/zachklopping/Desktop/AER_Patent_laws_product_life_cycle_lengths_and_multinational_activity-pages-deleted.pdf'  # <- change this

client = OpenAI(api_key='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')

# --- Upload the PDF ---
with open(PDF_PATH, "rb") as f:
    file_obj = client.files.create(file=f, purpose="user_data")

# --- JSON schema (for the model to follow) ---
schema = {
    "table": {
        "exists": True,
        "page_number": 1,
        "caption_or_title": "string or null",
        "preview_csv": "5x5 CSV or fewer rows/cols, or null"
    },
    "figure": {
        "exists": True,
        "page_number": 1,
        "caption_or_title": "string or null",
        "description": "one sentence or null"
    }
}

# --- Prompt: force strict JSON via instructions (no response_format) ---
instruction = f"""
You are reading a PDF provided as an input file.

Task:
1) Identify the first TABLE in the document.
   - Return: exists (bool), page_number (int|null), caption_or_title (string|null),
     preview_csv (string|null) with up to 5 rows × 5 columns as CSV.
2) Identify the first FIGURE in the document.
   - Return: exists (bool), page_number (int|null), caption_or_title (string|null),
     description (string|null) one sentence.

Rules:
- If something doesn't exist, set exists=false and other fields to null.
- Do NOT invent content that isn't in the PDF.
- Output ONLY a valid JSON object matching exactly this shape (no markdown, no prose):

{{
  "table": {{
    "exists": true|false,
    "page_number": integer|null,
    "caption_or_title": string|null,
    "preview_csv": string|null
  }},
  "figure": {{
    "exists": true|false,
    "page_number": integer|null,
    "caption_or_title": string|null,
    "description": string|null
  }}
}}
"""

# --- Call Responses API (no response_format) ---
resp = client.responses.create(
    model=MODEL,
    instructions="Return ONLY valid JSON. Be concise and accurate.",
    input=[{
        "role": "user",
        "content": [
            {"type": "input_text", "text": instruction},
            {"type": "input_file", "file_id": file_obj.id},
        ],
    }],
)

# --- Extract text safely ---
def get_text(r):
    if getattr(r, "output_text", None):
        return r.output_text
    # fallback
    return r.output[0].content[0].text

raw = get_text(resp).strip()

# --- Parse JSON (with a tiny fallback if the model adds stray text) ---
def parse_json_maybe(raw_text: str):
    try:
        return json.loads(raw_text)
    except Exception:
        # try to salvage the first top-level JSON object
        start = raw_text.find("{")
        end   = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw_text[start:end+1])
        raise

data = parse_json_maybe(raw)

# --- Save next to the PDF ---
stem = pathlib.Path(PDF_PATH).with_suffix("").name
out_path = str(pathlib.Path(PDF_PATH).with_name(stem + OUT_SUFFIX))
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"✅ Saved structured output to: {out_path}")

# --- Quick pretty print ---
tbl, fig = data.get("table", {}), data.get("figure", {})
print("\n=== TABLE ===")
print("Exists:", tbl.get("exists"))
print("Page:", tbl.get("page_number"))
print("Caption:", tbl.get("caption_or_title"))
print("Preview CSV:\n", tbl.get("preview_csv"))

print("\n=== FIGURE ===")
print("Exists:", fig.get("exists"))
print("Page:", fig.get("page_number"))
print("Caption:", fig.get("caption_or_title"))
print("Description:", fig.get("description"))
