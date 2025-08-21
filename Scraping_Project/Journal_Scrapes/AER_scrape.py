#!/usr/bin/env python3
import time
import os
import shutil
import pandas as pd
import regex as re

from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# =========================
# CONFIG
# =========================
EXCEL_PATH = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Combined Data/Download_AER_2000-2025.xlsx'
download_folder = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Scraped Papers/AER Scraped Papers'
os.makedirs(download_folder, exist_ok=True)

# =========================
# SELENIUM SETUP (undetected-chromedriver)
# =========================
options = uc.ChromeOptions()
prefs = {
    "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    "download.default_directory": download_folder,
    "download.prompt_for_download": False,
    "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "application/pdf"
}
options.add_experimental_option("prefs", prefs)

options.add_argument("--disable-blink-features=AutomationControlled")

driver = uc.Chrome(options=options)

# =========================
# LOAD DATA & FILTER
# =========================
journal_data = pd.read_excel(EXCEL_PATH)

if 'downloaded' not in journal_data.columns:
    journal_data['downloaded'] = 0

to_download = journal_data[journal_data['downloaded'].fillna(0).astype(int) == 0]

# =========================
# HELPERS
# =========================
def wait_for_pdf(download_dir: str, timeout: int = 120) -> str | None:
    start = time.time()
    newest_pdf = None
    while time.time() - start < timeout:
        pdfs = [os.path.join(download_dir, f) for f in os.listdir(download_dir)
                if f.lower().endswith('.pdf')]
        crs = [f for f in os.listdir(download_dir) if f.endswith('.crdownload')]
        if pdfs and not crs:
            newest_pdf = max(pdfs, key=os.path.getctime)
            break
        time.sleep(1)
    return newest_pdf

def clean_title_for_filename(title: str) -> str:
    s = re.sub(r'[^A-Za-z0-9]+', '_', str(title)).strip('_')
    return s or "untitled"

# =========================
# MAIN
# =========================
try:
    for orig_idx, row in to_download.iterrows():
        try:
            title = row.get('title', f'idx_{orig_idx}')
            url = row.get('url')
            if not isinstance(url, str) or not url.startswith('http'):
                print(f"[{orig_idx}] Skipping: bad/missing URL for '{title}'")
                continue

            print(f"[{orig_idx}] Processing: {title}")
            driver.get(url)
            time.sleep(5)

            soup = BeautifulSoup(driver.page_source, "lxml")

            # Find the main article section
            article_section = soup.select_one("section.primary.article-detail.journal-article")
            if not article_section:
                print(f"[{orig_idx}] Skipping: article-detail section not found.")
                continue

            # Find <section class="download"> inside, then <a class="button">
            download_section = article_section.select_one("section.download")
            if not download_section:
                print(f"[{orig_idx}] Skipping: no <section class=download> found.")
                continue

            link = download_section.select_one("a.button")
            if not link or not link.has_attr("href"):
                print(f"[{orig_idx}] Skipping: no <a class=button> inside download section.")
                continue

            tail = link["href"]
            pdf_url = tail if tail.startswith("http") else ("https://www.aeaweb.org" + tail)

            driver.get(pdf_url)
            time.sleep(4)

            filename = wait_for_pdf(download_folder, timeout=180)
            if not filename or not os.path.exists(filename):
                print(f"[{orig_idx}] Download failed or timed out.")
                continue

            article_title = clean_title_for_filename(title)
            new_filename = f"AER_{article_title}.pdf"
            target_path = os.path.join(download_folder, new_filename)
            shutil.move(filename, target_path)
            print(f"[{orig_idx}] Downloaded: {new_filename}")

            journal_data.at[orig_idx, "downloaded"] = 1
            journal_data.to_excel(EXCEL_PATH, index=False)

            time.sleep(2)

        except Exception as e:
            print(f"[{orig_idx}] Error: {e}")
            continue

finally:
    driver.quit()
    print("Done.")
