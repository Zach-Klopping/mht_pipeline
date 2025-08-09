import openai
import os
import tiktoken 

# === CONFIGURATION ===
client = openai.OpenAI(api_key="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")  # Set your OpenAI API key here
input_folder = '/Users/zachklopping/Desktop/List 25/Paper Outputs/Match One/combined_files'
output_folder = '/Users/zachklopping/Desktop/List 25/Paper Outputs/Match One/combined_analysis'
model = "gpt-4.1"
temperature = 0.1  # keep it deterministic
max_tokens = 10000  # output cap, tweak as needed

# === CUSTOM PROMPT ===
system_prompt = "You are an assistant helping a researcher identify tables that can be reproduced with publically available data."
user_prompt_intro = """
Here is the extracted output from a readme file as well as the tables above that I care about. Read the entire text. Only use what is written—do not speculate or infer beyond the provided text.

Each section begins with a header like === AER_78_Revealing_Choice_Bracketing.pdf ===, indicating the start of a new paper. Tables are denoted by === Table X ===, where X is the table number. Each table is followed by the surrounding text, including descriptions and results. Read each paper and each table. 

Your task is to identify which tables **clearly report treatment effects**, defined as **empirical estimates** of how an **intervention** affects an **outcome**.

You may include tables that:
- Use observed data (not simulations),
- Measure **effects**, **impacts**, or **responses** of an intervention or policy,
- Provide evidence based on methods like regressions, differences-in-differences, experiments, instrumental variables, or other statistical inference.

**Note**: The intervention must be a policy, incentive, treatment, or other causal action. Estimates of correlations, associations, or group differences without a clear intervention do **not** count as treatment effects.

Ignore tables that include:
- Structural model counterfactuals, even when the model is estimated/calibrated using real data
- Model simulations or theoretical counterfactuals
- Calibrated or structural model parameters
- Descriptive summary statistics
- Pure correlations without evidence of causality

This is designed to help screen tables for inclusion in a **Multiple Hypothesis Testing (MHT) correction**.

For each table you do select, briefly quote the **specific phrase or sentence** that justifies your decision.

Please output your results in the following format:

For each table that clearly reports a treatment effect, list:

- The paper name (from the header like === AER_78_Revealing_Choice_Bracketing.pdf ===)
- The table number (e.g., Table 3)
- A **short quote** or phrase from the text that justifies the inclusion

Please output the results in the following JSON format:

```json
[
  {
    "paper": "AER_78_Revealing_Choice_Bracketing.pdf",
    "table": "Table 3",
    "quote": "We begin by performing the direct revealed preference tests of bracketing developed in Section I…"
  },
  {
    "paper": "AER_79_Spending_and_Job_Finding_Impacts.pdf",
    "table": "Table 1",
    "quote": "Table-1 shows that we find an MPC of 0.31 at the expiration of $600…"
  }
]
"""
 # Make sure you import this at the top!

encoding = tiktoken.encoding_for_model(model)  # This should match your API model
TOKEN_LIMIT = 20000

# === LOOP OVER TXT FILES ===
for root, dirs, files in os.walk(input_folder):
    for filename in files:
        if filename.endswith(".txt"):
            input_file = os.path.join(root, filename)
            print(f"\nProcessing: {filename}")

            # === READ FILE ===
            with open(input_file, "r", encoding="utf-8") as f:
                chunk_text = f.read()

            # === TOKEN CHECK ===
            tokens = encoding.encode(chunk_text)
            if len(tokens) > TOKEN_LIMIT:
                print(f"Skipping {filename}: {len(tokens)} tokens (over {TOKEN_LIMIT})")
                continue

            # === CALL GPT ===
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt_intro.strip() + "\n\n" + chunk_text}
                ]
            )

            output_text = response.choices[0].message.content

            # === Get relative path from input_folder ===
            rel_dir = os.path.relpath(root, input_folder)  # e.g., 'batch_3'
            output_subfolder = os.path.join(output_folder, rel_dir)
            os.makedirs(output_subfolder, exist_ok=True)

            # === SAVE OUTPUT TO NEW FOLDER ===
            output_file = os.path.join(
                output_subfolder, filename.replace(".txt", "_mht_output.txt")
            )
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"Saved output to: {output_file}")