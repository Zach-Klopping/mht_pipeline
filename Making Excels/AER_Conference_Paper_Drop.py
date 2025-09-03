import pandas as pd

# ==== CONFIG ====
INPUT_EXCEL  = '/Users/zachklopping/Desktop/John List/MHT/Cleaned Excels/AER_2000-2025.xlsx'     # original file
OUTPUT_EXCEL = '/Users/zachklopping/Desktop/John List/MHT/Cleaned Excels/AER_2000-2025.xlsx'   # new file
SHEET_NAME   = 0  # 0 = first sheet, or put the sheet name in quotes

# ==== SCRIPT ====
# Load Excel
df = pd.read_excel(INPUT_EXCEL, sheet_name=SHEET_NAME)

# Drop rows where subtypeDescription == "Conference"
df_cleaned = df[df["subtypeDescription"] != "Conference Paper"]

# Save to new Excel file
df_cleaned.to_excel(OUTPUT_EXCEL, index=False)

print(f"✅ Cleaned file saved as: {OUTPUT_EXCEL}")
