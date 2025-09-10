#!/usr/bin/env python3
import os
import time
import shutil
import pandas as pd
import regex as re
import undetected_chromedriver as uc
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import dropbox
from dropbox.files import WriteMode

# ======== CONFIG ========
EXCEL_PATH = '/Users/zachklopping/Desktop/John List/MHT/Fully_Downloaded_RESTUD_2000-2025.xlsx'

# Chrome download sink (temporary)
download_folder = '/Users/zachklopping/Desktop/John List/MHT/RESTUD Downloads'
os.makedirs(download_folder, exist_ok=True)

# ======== Dropbox (optional; set env var DROPBOX_TOKEN) ========
DROPBOX_TOKEN = ''

DROPBOX_FOLDER_DATASET = "/MHT/RESTUD Replication Packages/Zenodo"
DROPBOX_FOLDER_SUPP    = "/MHT/RESTUD Replication Packages/Supplementary"

if not DROPBOX_TOKEN:
    raise RuntimeError("Missing DROPBOX_TOKEN for Dropbox API (set env var or paste a token string).")

dbx = dropbox.Dropbox(DROPBOX_TOKEN)
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB

def _ensure_dropbox_folder(folder_path: str):
    folder_path = (folder_path or "/").rstrip("/") or "/"
    if folder_path == "/":
        return
    try:
        dbx.files_create_folder_v2(folder_path)
    except dropbox.exceptions.ApiError:
        # ignore if already exists
        pass

def _upload_file_to_dropbox(local_path: str, dropbox_folder: str, dest_name: str) -> str:
    """Upload file (chunked if large). Returns the Dropbox path (string)."""
    dropbox_folder = dropbox_folder.rstrip("/")
    if not dropbox_folder.startswith("/"):
        dropbox_folder = "/" + dropbox_folder
    dropbox_path = f"{dropbox_folder}/{dest_name}"
    size = os.path.getsize(local_path)

    with open(local_path, "rb") as f:
        if size <= CHUNK_SIZE:
            dbx.files_upload(
                f.read(),
                dropbox_path,
                mode=WriteMode("add"),
                autorename=True,
                mute=True
            )
        else:
            start = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
            cursor = dropbox.files.UploadSessionCursor(session_id=start.session_id, offset=f.tell())
            commit = dropbox.files.CommitInfo(
                path=dropbox_path,
                mode=WriteMode("add"),
                autorename=True,
                mute=True
            )
            while f.tell() < size:
                if (size - f.tell()) <= CHUNK_SIZE:
                    dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                else:
                    dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                    cursor.offset = f.tell()
    return dropbox_path

# Ensure the target folders exist
_ensure_dropbox_folder(DROPBOX_FOLDER_DATASET)
_ensure_dropbox_folder(DROPBOX_FOLDER_SUPP)

# ======== Browser setup ========
options = uc.ChromeOptions()
prefs = {
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "application/pdf"
}
options.add_experimental_option("prefs", prefs)
driver = uc.Chrome(options=options, version_main=139)  # match your Chrome major version

# ======== Data load ========
journal_data = pd.read_excel(EXCEL_PATH)

# Ensure coverDate is datetime, then extract year
journal_data['coverDate'] = pd.to_datetime(journal_data['coverDate'], errors='coerce')
journal_data['year'] = journal_data['coverDate'].dt.year

# Ensure 'replication_package' column exists
if 'replication_package' not in journal_data.columns:
    journal_data['replication_package'] = 0
if 'supplementary_package' not in journal_data.columns:
    journal_data['supplementary_package'] = 0

# Only rows where replication_package == 0 and year >= 2012
to_download = journal_data[
    (journal_data['replication_package'].fillna(0).astype(int) == 0)
    & (journal_data['year'] >= 2024)
]

# ======== Helpers ========
def wait_for_file(download_dir: str, exts=(".zip",), timeout: int = 240) -> str | None:
    """Wait until a new file with desired extension(s) appears (ignore .crdownload)."""
    start = time.time()
    seen = {os.path.join(download_dir, f) for f in os.listdir(download_dir)}
    while time.time() - start < timeout:
        if any(f.endswith(".crdownload") for f in os.listdir(download_dir)):
            time.sleep(1)
            continue

        candidates = []
        for f in os.listdir(download_dir):
            p = os.path.join(download_dir, f)
            if p in seen:
                continue
            if not f.lower().endswith(exts):
                continue
            candidates.append(p)

        if candidates:
            return max(candidates, key=os.path.getctime)

        time.sleep(1)
    return None

def clean_title_for_filename(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(title)).strip("_")
    return s[:150]

def is_zip_url(href: str) -> bool:
    if not isinstance(href, str):
        return False
    return href.lower().split("?", 1)[0].endswith(".zip")

def upload_and_cleanup(local_path: str, dropbox_folder: str):
    if not dbx:
        return None
    name = os.path.basename(local_path)
    try:
        dbx_path = _upload_file_to_dropbox(local_path, dropbox_folder, name)
        print(f"✅ Uploaded to Dropbox: {dbx_path}")
        try:
            os.remove(local_path)
        except Exception:
            pass
        return dbx_path
    except Exception as e:
        print(f"❌ Dropbox upload failed; keeping local file: {e}")
        return None

# ======== Main loop ========
for orig_idx, row in to_download.iterrows():
    try:
        title = row.get("title", f"idx_{orig_idx}")
        url = row.get("url")
        if not isinstance(url, str) or not url.startswith("http"):
            print(f"[{orig_idx}] Skipping: bad/missing URL for '{title}'")
            continue

        print(f"\n[{orig_idx}] Processing: {title}")
        driver.get(url)

        # Cookies banner (best-effort)
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="accept-button"]'))
            ).click()
            print("✅ Cookies banner accepted.")
            time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            pass

        # Cloudflare challenge?
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "cf-challenge-running"))
            )
            print("🛑 Cloudflare challenge detected. Resolve it manually.")
            input("⏸ Press ENTER when complete…")
        except TimeoutException:
            pass

        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # -------- Try Data Availability Statement first --------
        das_url = None
        das_header = soup.find("h2", class_="dataavailabilitystatement-title")
        if not das_header:
            das_header = soup.find("h2", string=lambda t: t and "data availability" in t.lower())

        if das_header:
            for a in das_header.find_all_next("a", href=True, limit=10):
                href = a["href"]
                if href.startswith("https://doi.org"):
                    das_url = href
                    break

        if das_url:
            print(f"🔗 Data Availability link: {das_url}")
            driver.get(das_url)

            # -- Attempt Zenodo "Download all" (a.archive-link) --
            try:
                download_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.archive-link"))
                )
                dl_href = download_button.get_attribute("href")
                print(f"📦 Zenodo archive link: {dl_href}")
                driver.get(dl_href)

                # Wait for a ZIP to land
                dataset_path = wait_for_file(download_folder, exts=(".zip",), timeout=240)
                if dataset_path and os.path.exists(dataset_path):
                    safe_title = clean_title_for_filename(title)
                    renamed_path = os.path.join(download_folder, f"ReSTUD_{safe_title}.zip")
                    shutil.move(dataset_path, renamed_path)
                    print(f"📥 Saved dataset: {renamed_path}")
                    upload_and_cleanup(renamed_path, DROPBOX_FOLDER_DATASET)
                    journal_data.at[orig_idx, "replication_package"] = 1
                    journal_data.to_excel(EXCEL_PATH, index=False)
                    time.sleep(1)
                    continue
                else:
                    print("❌ No ZIP detected after Zenodo click.")
            except TimeoutException:
                pass  # Not Zenodo, try Dataverse style below

        # -------- Fallback: Supplementary data (.zip only) --------
        print(f"[{orig_idx}] ⚠️ DAS path unavailable; trying Supplementary data…")
        soup = BeautifulSoup(driver.page_source, "html.parser")  # refresh in case page changed

        supp_link = None
        # Prefer the site's canonical structure
        supp_header = soup.find("h2", id="supplementary-data")
        if supp_header:
            supp_div = supp_header.find_next("div", class_="dataSuppLink")
            if supp_div:
                a = supp_div.find("a", href=True)
                if a and is_zip_url(a["href"]):
                    supp_link = a["href"]
        if not supp_link:
            print(f"[{orig_idx}] ❌ No Supplementary ZIP link found.")
            continue

        if not supp_link.startswith("http"):
            supp_link = urljoin(driver.current_url, supp_link)

        # Only download if it's a .zip (as requested)
        if not is_zip_url(supp_link):
            print(f"[{orig_idx}] ⏭️ Skipping supplementary (not .zip): {supp_link}")
            continue

        print(f"📦 Supplementary ZIP link")

        # Go directly to the ZIP URL (no Selenium element click needed)
        driver.get(supp_link)

        # Wait for zip, move, upload, mark complete
        dataset_path = wait_for_file(download_folder, exts=(".zip",), timeout=240)
        if dataset_path and os.path.exists(dataset_path):
            safe_title = clean_title_for_filename(title)
            renamed_path = os.path.join(download_folder, f"ReSTUD_{safe_title}.zip")
            shutil.move(dataset_path, renamed_path)
            print(f"📥 Saved dataset: {renamed_path}")
            upload_and_cleanup(renamed_path, DROPBOX_FOLDER_SUPP)
            journal_data.at[orig_idx, 'supplementary_package'] = 1
            journal_data.to_excel(EXCEL_PATH, index=False)
            time.sleep(1)
            continue
        else:
            print(f"[{orig_idx}] ❌ Supplementary ZIP download did not appear in time.")
            continue

    except Exception as e:
        print(f"[{orig_idx}] ❌ Error: {e}")
        continue

# ======== Cleanup ========
driver.quit()
print("\n🎉 All articles processed.")
