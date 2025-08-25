#!/usr/bin/env python3
import time
import os
import shutil
import pandas as pd
import regex as re
import undetected_chromedriver as uc

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# =========================
# CONFIG
# =========================
EXCEL_PATH = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Combined Data/Download_RESTUD_2000-2025.xlsx'
download_folder = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Scraped Papers/RESTUD Scraped Papers'
os.makedirs(download_folder, exist_ok=True)

# =========================
# Browser setup
# =========================
options = uc.ChromeOptions()
prefs = {
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "applications/pdf"
}
options.add_experimental_option("prefs", prefs)
driver = uc.Chrome(options=options, headless=False)

# =========================
# Load data & filter
# =========================
journal_data = pd.read_excel(EXCEL_PATH)

# Ensure 'downloaded' column exists
if "downloaded" not in journal_data.columns:
    journal_data["downloaded"] = 0

# Only rows where downloaded == 0 (treat NaN as 0)
to_download = journal_data[journal_data["downloaded"].fillna(0).astype(int) == 0]

# =========================
# Helpers
# =========================
def wait_for_pdf(download_dir: str, timeout: int = 180) -> str | None:
    """
    Wait until a PDF appears in download_dir and any .crdownload files finish.
    Returns newest PDF path, or None on timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        # If any partial downloads present, wait
        if any(name.endswith(".crdownload") for name in os.listdir(download_dir)):
            time.sleep(1)
            continue
        pdfs = [os.path.join(download_dir, f)
                for f in os.listdir(download_dir)
                if f.lower().endswith(".pdf")]
        if pdfs:
            return max(pdfs, key=os.path.getctime)
        time.sleep(1)
    return None

def clean_title_for_filename(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(title)).strip("_")
    return s[:150]

# =========================
# Main scraping loop
# =========================
for orig_idx, row in to_download.iterrows():
    try:
        title = row.get("title", f"idx_{orig_idx}")
        url = row.get("url")
        if not isinstance(url, str) or not url.startswith("http"):
            print(f"[{orig_idx}] Skipping: bad/missing URL for '{title}'")
            continue

        print(f"\n[{orig_idx}] Processing: {title}")
        driver.get(url)

        # Attempt to accept cookies if the banner appears
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="accept-button"]'))
            ).click()
            print("✅ Cookies banner accepted.")
            time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            print("" \
            "Cookies banner did not appear.")

        # Pause if Cloudflare challenge page is detected
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "cf-challenge-running"))
            )
            print("🛑 Cloudflare challenge detected. Please resolve it manually.")
            input("⏸ Press ENTER once you've completed the Cloudflare check...")
        except TimeoutException:
            print("✅ No Cloudflare challenge detected.")

        time.sleep(3)

        # Parse article page to find PDF button
        soup = BeautifulSoup(driver.page_source, "html.parser")
        try:
            pdf_button = soup.find("a", class_="al-link pdf article-pdfLink")
            if not pdf_button or not pdf_button.has_attr("href"):
                raise ValueError("PDF button not found.")
            pdf_link = "https://academic.oup.com" + pdf_button["href"]
            print(f"🔗 PDF link: {pdf_link}")
        except Exception as e:
            print(f"[{orig_idx}] ❌ Could not find PDF link: {e}")
            continue

        # Go to the PDF link (should trigger download)
        driver.get(pdf_link)

        # Wait for the PDF to finish downloading
        downloaded_path = wait_for_pdf(download_folder, timeout=180)
        if not downloaded_path or not os.path.exists(downloaded_path):
            print(f"[{orig_idx}] ❌ Download failed or timed out.")
            continue

        # Rename the downloaded file
        safe_title = clean_title_for_filename(title)
        new_filename = f"ReSTUD_{safe_title}.pdf"
        target_path = os.path.join(download_folder, new_filename)
        shutil.move(downloaded_path, target_path)
        print(f"[{orig_idx}] ✅ File saved as {target_path}")

        # Mark as downloaded and persist immediately
        journal_data.at[orig_idx, "downloaded"] = 1
        journal_data.to_excel(EXCEL_PATH, index=False)

        time.sleep(2)

    except Exception as e:
        print(f"[{orig_idx}] ❌ Error: {e}")
        continue

# =========================
# Cleanup
# =========================
driver.quit()
print("\n🎉 All articles processed.")
