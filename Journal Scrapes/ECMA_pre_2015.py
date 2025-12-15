import time
import os
import shutil
import pandas as pd
import regex as re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# =========================
# CONFIG
# =========================
EXCEL_PATH = '/Users/zachklopping/Desktop/John List/MHT/Fixed Data/Fully_Downloaded_Econometrica_2000-2025.xlsx'
download_folder = '/Users/zachklopping/Desktop/John List/MHT/ECMA Old Scraped Papers'
os.makedirs(download_folder, exist_ok=True)

# =========================
# Chrome options
# =========================
options = uc.ChromeOptions()
profile = {
    "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "applications/pdf"
}
options.add_experimental_option("prefs", profile)

# Start undetected Chrome driver
driver = uc.Chrome(options=options, version_main=139)  # match your Chrome version

# =========================
# Load and filter data
# =========================
journal_data = pd.read_excel(EXCEL_PATH)

# Ensure 'downloaded' column exists
if 'downloaded' not in journal_data.columns:
    journal_data['downloaded'] = 0

# # Parse coverDate and filter before Mar 1, 2015
# journal_data['coverDate'] = pd.to_datetime(
#     journal_data['coverDate'], errors='coerce', infer_datetime_format=True
# )

# cutoff = pd.Timestamp('2015-03-01')
# eligible = journal_data[journal_data['coverDate'].notna() & (journal_data['coverDate'] < cutoff)]

# # Only rows where downloaded == 0 (treat NaN as 0)
# to_download = eligible[eligible['downloaded'].fillna(0).astype(int) == 0]

to_download = journal_data[journal_data['downloaded'].fillna(0).astype(int) == 0]


# =========================
# Helpers
# =========================
def clean_title_for_filename(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(title)).strip("_")
    return s

def wait_for_pdf(download_dir: str, timeout: int = 180) -> str | None:
    """
    Wait until a new PDF appears (ignoring finalized ECMA_*.pdf and partials).
    Returns newest raw PDF path or None on timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        # If any partial downloads still present, wait
        if any(f.endswith('.crdownload') for f in os.listdir(download_dir)):
            time.sleep(1)
            continue

        pdfs = []
        for f in os.listdir(download_dir):
            if not f.lower().endswith('.pdf'):
                continue
            if f.startswith("ECMA_"):   # 👈 ignore already-renamed files
                continue
            pdfs.append(os.path.join(download_dir, f))

        if pdfs:
            return max(pdfs, key=os.path.getctime)  # newest raw PDF

        time.sleep(1)
    return None


# =========================
# Main loop
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

        # Accept cookie banner if it appears
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="cookie-notice"]/p[3]/a[2]'))
            ).click()
            print("Cookie banner accepted.")
            time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            print("No cookie banner appeared.")

        time.sleep(5)

        # Parse page for ePDF link
        try:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            pdf_link_tag = soup.find(
                "a",
                href=re.compile(r"^/doi/epdf/"),
            )
            pdf_url = "https://onlinelibrary.wiley.com" + pdf_link_tag["href"]
            print(f"🔗 ePDF URL found: {pdf_url}")
            driver.get(pdf_url)
        except Exception as e:
            print(f" Could not find ePDF link: {e}")
            continue

        # Click download menu and then direct download
        try:
            # (Keep this—good to ensure the viewer overlay is gone)
            WebDriverWait(driver, 15).until(
                EC.invisibility_of_element_located((By.CLASS_NAME, "overlay-screen"))
            )

            # Click the direct PDF download link (no menu needed)
            link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "navbar-download"))
            )
            link.click()
            print("✅ Clicked direct PDF download link.")
        except Exception as e:
            print(f"❌ Could not click direct PDF link: {e}")
            continue

        # Wait for PDF to be fully downloaded
        downloaded_path = wait_for_pdf(download_folder, timeout=180)
        
        if not downloaded_path or not os.path.exists(downloaded_path):
            print(f"[{orig_idx}] ❌ Download failed or timed out.")
            continue

        # Rename PDF
        safe_title = clean_title_for_filename(title)
        new_filename = f"ECMA_{safe_title}.pdf"
        target_path = os.path.join(download_folder, new_filename)
        shutil.move(downloaded_path, target_path)
        print(f"[{orig_idx}] ✅ Saved as {target_path}")

        # Mark as downloaded and save to Excel
        journal_data.at[orig_idx, "downloaded"] = 1
        journal_data.to_excel(EXCEL_PATH, index=False)

        time.sleep(2)

    except Exception as e:
        print(f"[{orig_idx}] Error: {e}")
        continue

# =========================
# Cleanup
# =========================
driver.quit()
print("Done.")
