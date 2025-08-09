#!/usr/bin/env python3
import time
import os
import shutil
import pandas as pd
import regex as re

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# =========================
# CONFIG
# =========================
EXCEL_PATH = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Combined Data/Download_AER_2000-2025.xlsx'
download_folder = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Scraped Papers/AER Scraped Papers'
chromedriver_path = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/chromedriver-mac-arm64/chromedriver'

os.makedirs(download_folder, exist_ok=True)

# =========================
# SELENIUM SETUP
# =========================
prefs = {
    "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "applications/pdf"
}

options = Options()
options.add_experimental_option("prefs", prefs)
# Uncomment if you want to run headless:
# options.add_argument("--headless=new")

service = Service(chromedriver_path)

# =========================
# LOAD DATA & FILTER
# =========================
journal_data = pd.read_excel(EXCEL_PATH)

# Ensure the 'downloaded' column exists (treat missing as 0)
if 'downloaded' not in journal_data.columns:
    journal_data['downloaded'] = 0

# Only process rows where downloaded == 0 (treat NaN as 0)
to_download = journal_data[journal_data['downloaded'].fillna(0).astype(int) == 0]

# =========================
# HELPERS
# =========================
def wait_for_pdf(download_dir: str, timeout: int = 120) -> str | None:
    """
    Waits for a PDF to appear in download_dir and for any .crdownload to finish.
    Returns the full path to the newest PDF, or None on timeout.
    """
    start = time.time()
    newest_pdf = None

    while time.time() - start < timeout:
        # Exclude temp files
        pdfs = [os.path.join(download_dir, f) for f in os.listdir(download_dir)
                if f.lower().endswith('.pdf')]
        # If any .crdownload exists, keep waiting
        crs = [f for f in os.listdir(download_dir) if f.endswith('.crdownload')]
        if pdfs and not crs:
            newest_pdf = max(pdfs, key=os.path.getctime)
            break
        time.sleep(1)

    return newest_pdf

def clean_title_for_filename(title: str) -> str:
    # Keep it simple and safe; collapse non-alnum to underscore
    s = re.sub(r'[^A-Za-z0-9]+', '_', str(title)).strip('_')
    # Avoid super long filenames
    return s

# =========================
# MAIN
# =========================
driver = webdriver.Chrome(service=service, options=options)

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

        soup = BeautifulSoup(driver.page_source, features="lxml")

        # Find the main article section (robust CSS selector)
        article_section = soup.select_one("section.primary.article-detail.journal-article")
        if not article_section:
            # fallback: try any section containing a download button
            article_section = soup.find('section')
        if not article_section:
            print(f"[{orig_idx}] Skipping: article-detail section not found.")
            continue

        # Find a download button/link
        # Often buttons have class 'button' and the href points to the PDF or PDF page.
        link = None
        for a in article_section.find_all('a', href=True):
            text = (a.get_text(strip=True) or '').lower()
            classes = ' '.join(a.get('class', [])).lower()
            href = a['href']
            # Heuristics to find the pdf download action
            if ('pdf' in text) or ('download' in text) or ('pdf' in href) or ('button' in classes):
                link = a
                break

        if not link:
            print(f"[{orig_idx}] Skipping: no download link found.")
            continue

        tail = link.get('href', '')
        if not tail:
            print(f"[{orig_idx}] Skipping: link has no href.")
            continue

        pdf_url = tail if tail.startswith('http') else ('https://www.aeaweb.org' + tail)
        driver.get(pdf_url)
        time.sleep(4)

        # Wait for the PDF to fully download
        filename = wait_for_pdf(download_folder, timeout=180)
        if not filename or not os.path.exists(filename):
            print(f"[{orig_idx}] Download failed or timed out.")
            continue

        # Rename the downloaded file
        article_title = clean_title_for_filename(title)
        new_filename = f"AER_{article_title}.pdf"
        target_path = os.path.join(download_folder, new_filename)
        shutil.move(filename, target_path)
        print(f"[{orig_idx}] Downloaded: {new_filename}")

        # Mark as downloaded and persist
        journal_data.at[orig_idx, 'downloaded'] = 1
        journal_data.to_excel(EXCEL_PATH, index=False)

        time.sleep(2)

    except Exception as e:
        print(f"[{orig_idx}] Error: {e}")
        continue

driver.quit()
print("Done.")
