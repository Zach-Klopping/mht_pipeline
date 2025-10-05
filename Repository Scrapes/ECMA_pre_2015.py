#!/usr/bin/env python3
"""
ECONOMETRICA (ECMA) supplemental ZIP downloader — Dropbox integrated
Workflow:
- Reads an Excel file tracking articles with columns: ['title', 'url', 'coverDate', 'replication_package', 'supplementary_package'].
- Filters for rows where replication_package == 0 and supplementary_package == 0 and year < 2016.
- Visits each article landing page to locate supplemental ZIP files.
    - If a direct .zip link is found, downloads the file.
    - Attempts to match title with Excel file title.
- Uploads each downloaded ZIP to the appropriate Dropbox folder.
- Updates the Excel file to mark completed rows so future runs skip them.
Install:
    pip install pandas beautifulsoup4 regex rapidfuzz undetected-chromedriver selenium dropbox openpyxl

Note:
    Requires Chrome (matching CHROME_MAJOR), a valid Dropbox token,
    and an Excel file with article metadata.
"""

import time
import os
import shutil
import pandas as pd
import regex as re
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import dropbox
from dropbox.files import WriteMode
from rapidfuzz import process

# =========================
# CONFIG (edit these to run)
# =========================
EXCEL_PATH        = "set path here"       
CHROME_MAJOR      = 141                   
DROPBOX_TOKEN     = "your_dropbox_oauth_token"  # Dropbox API token

# TEMP local staging folder (downloads land here)
DOWNLOAD_FOLDER   = "set download folder" # e.g., "/Users/you/Desktop/MHT/Scrapes/ECMA Downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# =========================
# Already Set Config (do NOT edit below)
# =========================
URL_COL           = "url"                  # Excel column with article landing page URL
TITLE_COL         = "title"                # Excel column with article title
FLAG_SUPP_COL     = "supplementary_package" # 0 = needs supplemental zip, 1 = done
START_YEAR        = 2000                  # first year to scan
END_YEAR          = 2015                  # last year to scan
DROPBOX_FOLDER    = "/MHT/ECMA Pre 2015 Supplementary Packages"       # Dropbox destination root (must start with "/")

if not DROPBOX_TOKEN:
    raise RuntimeError("Missing DROPBOX_TOKEN")

dbx = dropbox.Dropbox(DROPBOX_TOKEN)
CHUNK_SIZE = 8 * 1024 * 1024

def _ensure_dropbox_folder(folder_path: str):
    folder_path = (folder_path or "/").rstrip("/") or "/"
    if folder_path == "/": return
    try:
        dbx.files_create_folder_v2(folder_path)
    except dropbox.exceptions.ApiError:
        pass
_ensure_dropbox_folder(DROPBOX_FOLDER)

def _upload_file_to_dropbox(local_path: str, dropbox_folder: str, dest_name: str) -> str:
    dropbox_folder = dropbox_folder.rstrip("/")
    if not dropbox_folder.startswith("/"):
        dropbox_folder = "/" + dropbox_folder
    dropbox_path = f"{dropbox_folder}/{dest_name}"
    size = os.path.getsize(local_path)
    with open(local_path, "rb") as f:
        if size <= CHUNK_SIZE:
            dbx.files_upload(f.read(), dropbox_path, mode=WriteMode("add"), autorename=True, mute=True)
        else:
            start = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
            cursor = dropbox.files.UploadSessionCursor(session_id=start.session_id, offset=f.tell())
            commit = dropbox.files.CommitInfo(path=dropbox_path, mode=WriteMode("add"), autorename=True, mute=True)
            while f.tell() < size:
                if (size - f.tell()) <= CHUNK_SIZE:
                    dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                else:
                    dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                    cursor.offset = f.tell()
    return dropbox_path

# =========================
# Browser
# =========================
options = uc.ChromeOptions()
prefs = {"download.default_directory": DOWNLOAD_FOLDER}
options.add_experimental_option("prefs", prefs)
driver = uc.Chrome(options=options, version_main=141)

# =========================
# Data
# =========================
journal_data = pd.read_excel(EXCEL_PATH)
journal_data["coverDate"] = pd.to_datetime(journal_data["coverDate"], errors="coerce")
journal_data["year"] = journal_data["coverDate"].dt.year
if FLAG_SUPP_COL not in journal_data.columns:
    journal_data[FLAG_SUPP_COL] = 0

to_download = journal_data[
    journal_data[FLAG_SUPP_COL].fillna(0).astype(int) == 0
]

# =========================
# Helpers
# =========================
def clean_title_for_filename(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(t)).strip("_") or "untitled"

def wait_for_file(download_dir: str, exts=(".zip",), timeout=600) -> str | None:
    start = time.time()
    seen = {os.path.join(download_dir, f) for f in os.listdir(download_dir)}
    while time.time() - start < timeout:
        if any(f.endswith(".crdownload") for f in os.listdir(download_dir)):
            time.sleep(1); continue
        new_files = []
        for f in os.listdir(download_dir):
            p = os.path.join(download_dir, f)
            if p in seen: continue
            if f.lower().endswith(exts):
                new_files.append(p)
        if new_files:
            newest = max(new_files, key=os.path.getctime)
            # check stability
            size1 = os.path.getsize(newest); time.sleep(3)
            size2 = os.path.getsize(newest)
            if size1 == size2:
                return newest
        time.sleep(2)
    return None

# =========================
# Main loop (year-month)
# =========================
for year in range(START_YEAR, END_YEAR + 1):
    for month in range(1, 13, 2):  # odd months
        url = f"https://www.econometricsociety.org/publications/econometrica/browse/supplemental-materials/issue-supplemental-materials/{year}/{month:02d}"
        print(f"\nProcessing {year}-{month:02d}: {url}")
        driver.get(url)
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="cookie-notice"]/p[3]/a[2]'))
            ).click()
            print("✅ Cookie banner accepted.")
            time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            pass

        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        zips = []
        for a in soup.find_all("a", href=True):
            if not a["href"].lower().endswith(".zip"):
                continue
            h3 = a.find_previous("h3")
            heading = h3.get_text(strip=True) if h3 else "untitled"
            zip_url = urljoin(driver.current_url, a["href"])
            zips.append({"heading": heading, "zip_url": zip_url})

        if not zips:
            print("❌ No ZIP files found")
            continue

        for rec in zips:
            driver.get(rec["zip_url"])  # <---- you must go to the ZIP link first!
            start_url = driver.current_url
            file_path = wait_for_file(DOWNLOAD_FOLDER, exts=(".zip",), timeout=10)  # short early wait

            if not file_path:
                # still on the same page and no download started
                time.sleep(2)
                if driver.current_url == start_url:
                    print(f"❌ No download triggered and still on {start_url} — skipping.")
                    driver.back()
                    time.sleep(2)
                    continue
                else:
                    # If URL changed maybe redirect to an error page — we can inspect or just skip
                    print(f"❌ Redirected but no file for {rec['heading']} — skipping.")
                    driver.back()
                    time.sleep(2)
                    continue

            safe = clean_title_for_filename(rec["heading"])
            new_name = f"ECMA_{safe}.zip"
            target = os.path.join(DOWNLOAD_FOLDER, new_name)
            shutil.move(file_path, target)
            print(f"📥 Saved: {target}")

            def normalize(s: str) -> str:
                s = str(s).lower()
                s = re.sub(r'[_\-]+', ' ', s)       # underscores and hyphens to spaces
                s = re.sub(r'[^\w\s]', '', s)       # drop punctuation
                s = re.sub(r'\s+', ' ', s).strip()  # collapse spaces
                return s

            # --- fuzzy match ---
            parsed = normalize(rec["heading"])
            choices = [normalize(t) for t in journal_data["title"].astype(str)]
            best = process.extractOne(parsed, choices)

            # choose the Dropbox destination depending on match
            if best and best[1] >= 90:
                match_str, score, idx = best
                norm_titles = journal_data["title"].astype(str).apply(normalize)
                journal_data.loc[norm_titles == match_str, FLAG_SUPP_COL] = 1
                print(f"✅ Marked supplementary for '{match_str}' (score {score})")
                dropbox_dest = DROPBOX_FOLDER
            else:
                print(f"⚠️ No good match for: {parsed}")
                # create /No Match subfolder inside your main ECMA folder
                dropbox_dest = f"{DROPBOX_FOLDER}/No Match"
                _ensure_dropbox_folder(dropbox_dest)

            # upload to the chosen Dropbox folder
            try:
                dbx_path = _upload_file_to_dropbox(target, dropbox_dest, new_name)
                print(f"✅ Uploaded to Dropbox: {dbx_path}")
                os.remove(target)
            except Exception as e:
                print(f"Dropbox upload failed: {e}")

            # only save Excel if we matched
            if best and best[1] >= 90:
                journal_data.to_excel(EXCEL_PATH, index=False)
            time.sleep(2)

# =========================
# Cleanup
# =========================
driver.quit()
print("\n🎉 All ECMA supplemental materials processed.")
