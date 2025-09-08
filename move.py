#!/usr/bin/env python3
import pandas as pd

# ===== CONFIG =====
input_excel  = '/Users/zachklopping/Desktop/John List/MHT/Fixed Data/Fully_Downloaded_Econometrica_2000-2025.xlsx'
output_excel = '/Users/zachklopping/Desktop/John List/MHT/Cleaned Excels/1_Econometrica_2000-2025.xlsx'
# ==================

# Load Excel
df = pd.read_excel(input_excel)

# Drop rows where 'downloaded' == 0
df_clean = df[df['downloaded'] != 0]

# Save cleaned Excel
df_clean.to_excel(output_excel, index=False)

print(f"Done. Cleaned file saved to {output_excel}")
