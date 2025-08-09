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
EXCEL_PATH = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Combined Data/Download_ECMA_2000-2025.xlsx'
download_folder = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Scraped Papers/ECMA Scraped Papers'
os.makedirs(download_folder, exist_ok=True)

# =========================
# Browser setup (undetected-chromedriver)
# =========================
options = uc.ChromeOptions()
prefs = {
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "applications/pdf",
}
options.add_experimental_option("prefs", prefs)
# options.add_argument("--headless=new")  # uncomment if you want headless

driver = uc.Chrome(options=options, headless=False)

# =========================
# Load data & filter
# =========================
journal_data = pd.read_excel(EXCEL_PATH)

# Ensure 'downloaded' column exists
if 'downloaded' not in journal_data.columns:
    journal_data['downloaded'] = 0

# Only rows where downloaded == 0 (treat NaN as 0)
to_download = journal_data[journal_data['downloaded'].fillna(0).astype(int) == 0]

# =========================
# Helpers
# =========================
def wait_for_pdf(download_dir: str, timeout: int = 180) -> str | None:
    """
    Waits up to `timeout` seconds for a PDF to appear in `download_dir`,
    and for any .crdownload files to finish. Returns newest PDF path or None.
    """
    start = time.time()
    while time.time() - start < timeout:
        # if any .crdownload still present, keep waiting
        if any(name.endswith('.crdownload') for name in os.listdir(download_dir)):
            time.sleep(1)
            continue
        # pick newest .pdf
        pdfs = [os.path.join(download_dir, f)
                for f in os.listdir(download_dir)
                if f.lower().endswith('.pdf')]
        if pdfs:
            return max(pdfs, key=os.path.getctime)
        time.sleep(1)
    return None

def clean_title_for_filename(title: str) -> str:
    # collapse non-alnum to underscore and trim length
    s = re.sub(r'[^A-Za-z0-9]+', '_', str(title)).strip('_')
    return s

# =========================
# Main loop
# =========================
for orig_idx, row in to_download.iterrows():
    try:
        title = row.get('title', f'idx_{orig_idx}')
        url = row.get('url')

        if not isinstance(url, str) or not url.startswith('http'):
            print(f"[{orig_idx}] Skipping (bad/missing URL): {title}")
            continue

        print(f"\n[{orig_idx}] Processing: {title}")
        driver.get(url)

        # Try to accept cookies (if present)
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="accept-button"]'))
            ).click()
            print("✅ Cookies banner accepted.")
            time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            print("Cookies banner not shown.")

        # Check Cloudflare challenge (if present)
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "cf-challenge-running"))
            )
            print("🛑 Cloudflare challenge detected. Complete it in the browser.")
            input("⏸ Press ENTER after completing the challenge...")
        except TimeoutException:
            print("✅ No Cloudflare challenge detected.")

        time.sleep(3)

        # Parse landing page
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Find "Institutional Access" (redirects to Wiley)
        try:
            access_button = soup.find("a", href=re.compile(r"/member-authentication/wb\?doi="))
            if not access_button or not access_button.has_attr('href'):
                raise ValueError("Institutional access link not found.")
            access_link = "https://www.econometricsociety.org" + access_button["href"]
            print(f"Found institutional access link: {access_link}")
        except Exception as e:
            print(f"❌ Could not find institutional access link. Error: {e}")
            continue

        driver.get(access_link)
        time.sleep(2)

        # Parse Wiley page; find navbar download link
        soup = BeautifulSoup(driver.page_source, "html.parser")
        try:
            pdf_button = soup.find("a", class_=re.compile(r"navbar-download"))
            if not pdf_button or not pdf_button.has_attr('href'):
                raise ValueError("PDF download link not found on Wiley.")
            pdf_link = "https://onlinelibrary.wiley.com" + pdf_button["href"]
            print(f"Found PDF link: {pdf_link}")
        except Exception as e:
            print(f"❌ Could not find PDF link. Error: {e}")
            continue

        driver.get(pdf_link)
        time.sleep(2)

        # Wait for download completion
        downloaded_path = wait_for_pdf(download_folder, timeout=180)
        if not downloaded_path or not os.path.exists(downloaded_path):
            print(f"[{orig_idx}] ❌ Download failed or timed out.")
            continue

        # Rename file
        safe_title = clean_title_for_filename(title)
        new_filename = f"Econometrica_{safe_title}.pdf"
        target_path = os.path.join(download_folder, new_filename)
        shutil.move(downloaded_path, target_path)
        print(f"[{orig_idx}] ✅ Saved: {target_path}")

        # Mark as downloaded and persist immediately
        journal_data.at[orig_idx, 'downloaded'] = 1
        journal_data.to_excel(EXCEL_PATH, index=False)

        time.sleep(2)

    except Exception as e:
        print(f"[{orig_idx}] ❌ Error: {e}")
        continue

# =========================
# Cleanup
# =========================
driver.quit()
print("\n🎉 Process complete.")
