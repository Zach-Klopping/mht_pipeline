import os
import tiktoken

# Path to your folder with txt files
folder = "/Users/zachklopping/Desktop/List 25/Paper Outputs/Match One/combined_files"
token_limit = 18000

# Choose your model (so the correct tokenizer is used)
encoding = tiktoken.encoding_for_model("gpt-4")  # or "gpt-3.5-turbo" etc.

count = 0
over_limit_files = []

for filename in os.listdir(folder):
    if not filename.lower().endswith('.txt'):
        continue
    file_path = os.path.join(folder, filename)
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    tokens = encoding.encode(content)
    num_tokens = len(tokens)
    if num_tokens > token_limit:
        count += 1
        over_limit_files.append((filename, num_tokens))

print(f"\nFiles over {token_limit} tokens: {count}")
if count > 0:
    print("These files are over the limit:")
    for fname, ntok in over_limit_files:
        print(f"  {fname}: {ntok} tokens")
else:
    print("No files are over the token limit!")
