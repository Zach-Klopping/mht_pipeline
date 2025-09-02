#!/usr/bin/env python3
import pandas as pd

# ========= CONFIG =========
input_excel  = '/Users/zachklopping/Desktop/John List/MHT/Raw Excels/ReSTUD_2000-2025.xlsx'   # path to your Excel file
output_excel = '/Users/zachklopping/Desktop/John List/MHT/Cleaned Excels/Restud_2000-2025.xlsx'  # path for saving the cleaned version
# ==========================

# Load the Excel file
df = pd.read_excel(input_excel)

# Drop rows where subtypeDescription == "Erratum"
df_cleaned = df[~df['subtypeDescription'].isin(["Erratum", "Retracted", "Note", "Editorial"])]

title_norm = df_cleaned['title'].astype(str).str.strip().str.lower()
df_cleaned = df_cleaned[
    ~(
        title_norm.str.startswith(('a comment on', 'reply to', 'the econometric society', 'comment'))
        | title_norm.str.endswith((': comment', ': reply', 'comment', 'Reply†', 'Comment†'))
    )
]

# Save cleaned dataframe back to Excel
df_cleaned.to_excel(output_excel, index=False)

print(f"Saved cleaned Excel file to {output_excel}")
