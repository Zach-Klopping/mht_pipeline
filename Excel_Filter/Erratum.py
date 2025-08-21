#!/usr/bin/env python3
import pandas as pd

# ========= CONFIG =========
input_excel  = '/Users/zachklopping/Desktop/List 25/MHT/Fixed_Data/Download_RESTUD_2000-2025.xlsx'     # path to your Excel file
output_excel = '/Users/zachklopping/Desktop/List 25/MHT/Fixed_Data/Cleaned_RESTUD_2000-2025.xlsx'   # path for saving the cleaned version
# ==========================

# Load the Excel file
df = pd.read_excel(input_excel)

# Drop rows where subtypeDescription == "Erratum"
df_cleaned = df[~df['subtypeDescription'].isin(["Erratum", "Retracted"])]

# Save cleaned dataframe back to Excel
df_cleaned.to_excel(output_excel, index=False)

print(f"Saved cleaned Excel file to {output_excel}")
