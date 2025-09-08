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
EXCEL_PATH = '/Users/zachklopping/Desktop/John List/MHT/Fully_Downloaded_QJE_2000-2025.xlsx'
download_folder = '/Users/zachklopping/Desktop/John List/MHT/QJE Scrapes'
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
driver = uc.Chrome(options=options, version_main=139)  # 👈 match your Chrome major version

# =========================
# Load data & filter
# =========================
journal_data = pd.read_excel(EXCEL_PATH)

# Ensure coverDate is datetime, then extract year
journal_data['coverDate'] = pd.to_datetime(journal_data['coverDate'], errors='coerce')
journal_data['year'] = journal_data['coverDate'].dt.year

# Ensure 'replication_package' column exists
if 'replication_package' not in journal_data.columns:
    journal_data['replication_package'] = 0

# Only rows where replication_package == 0
to_download = journal_data[
    (journal_data['replication_package'].fillna(0).astype(int) == 0)
    & (journal_data['year'] >= 2017)
]
# =========================
# Helpers
# =========================
def wait_for_file(download_dir: str, exts=(".pdf", ".zip"), timeout: int = 240) -> str | None:
    """Wait for a new file with one of the given extensions to appear (ignores partials and already-renamed QJE_*.pdf)."""
    start = time.time()
    seen = {os.path.join(download_dir, f) for f in os.listdir(download_dir)}
    while time.time() - start < timeout:
        # ignore active partials
        if any(f.endswith('.crdownload') for f in os.listdir(download_dir)):
            time.sleep(1)
            continue

        candidates = []
        for f in os.listdir(download_dir):
            p = os.path.join(download_dir, f)
            if p in seen:
                continue
            if not f.lower().endswith(exts):
                continue
            if f.startswith("QJE_"):  # ignore already-renamed article PDFs
                continue
            candidates.append(p)

        if candidates:
            return max(candidates, key=os.path.getctime)

        time.sleep(1)
    return None

def clean_title_for_filename(title: str) -> str:
    s = re.sub(r'[^A-Za-z0-9]+', '_', str(title)).strip('_')
    return s

# =========================
# Main scraping loop
# =========================
for orig_idx, row in to_download.iloc[::-1].iterrows():
    try:
        title = row.get('title', f'idx_{orig_idx}')
        url = row.get('url')
        if not isinstance(url, str) or not url.startswith('http'):
            print(f"[{orig_idx}] Skipping: bad/missing URL for '{title}'")
            continue

        print(f"\n[{orig_idx}] Processing: {title}")
        driver.get(url)

        # Cookies banner (if present)
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="accept-button"]'))
            ).click()
            print("✅ Cookies banner accepted.")
            time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            print("Cookies banner did not appear.")

        # Cloudflare challenge check (if present)
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "cf-challenge-running"))
            )
            print("🛑 Cloudflare challenge detected. Please resolve it manually.")
            input("⏸ Press ENTER once you've completed the Cloudflare check...")
        except TimeoutException:
            print("✅ No Cloudflare challenge detected.")

        time.sleep(3)

        # Parse the article page for the "Data Availability" heading
        soup = BeautifulSoup(driver.page_source, "html.parser")
        heading = soup.find("h2", string=lambda t: t and "data availability" in t.lower())
        if not heading:
            print("❌ Could not find 'Data Availability' heading.")
            continue

        # Find the next <a> after the heading that looks like a DOI link
        doi_link = heading.find_next("a", href=True)
        if not (doi_link and isinstance(doi_link.get("href"), str) and doi_link["href"].startswith("https://doi.org")):
            print("❌ No DOI link found after Data Availability.")
            continue

        doi_url = doi_link["href"]
        print("🔗 Found DOI:", doi_url)

        # Go to DOI (Dataverse landing page expected)
        driver.get(doi_url)

        # --- On the Dataverse landing page: click "Access Dataset", then click a download item ---
        try:
            access_button = WebDriverWait(driver, 12).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-access-dataset"))
            )
            access_button.click()
            print("✅ Clicked 'Access Dataset' button.")

            # Click the FIRST btn-download link (minimal)
            first_download = WebDriverWait(driver, 12).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-download"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", first_download)
            try:
                first_download.click()  # native click
            except Exception:
                driver.execute_script("arguments[0].click();", first_download)  # JS fallback
            print("✅ Clicked first btn-download link")

            # Wait specifically for a ZIP (dataset) to land
            dataset_path = wait_for_file(download_folder, exts=(".zip",), timeout=240)
            if dataset_path and os.path.exists(dataset_path):
                print(f"📥 Dataset saved: {dataset_path}")
                safe_title = clean_title_for_filename(title)
                new_filename = f"QJE_{safe_title}.zip"
                target_path = os.path.join(download_folder, new_filename)
                shutil.move(dataset_path, target_path)
                print(f"📥 Dataset saved as {target_path}")
                # Mark as having replication package and persist
                journal_data.at[orig_idx, 'replication_package'] = 1
                journal_data.to_excel(EXCEL_PATH, index=False)
            else:
                print("❌ Dataset download did not appear in time.")

        except TimeoutException:
            print("❌ Could not find the 'Access Dataset' button.")
            continue

        time.sleep(2)

    except Exception as e:
        print(f"[{orig_idx}] ❌ Error: {e}")
        continue

# =========================
# Cleanup
# =========================
driver.quit()
print("\n🎉 All articles processed.")
