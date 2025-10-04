#!/usr/bin/env python3
"""
ECONOMETRICA (ECMA) supplemental ZIP downloader — Dropbox integrated
Pattern matches your working JPE script so downloads finish before page changes.
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
from rapidfuzz import fuzz, process

# =========================
# CONFIG
# =========================
EXCEL_PATH = '/Users/zachklopping/Desktop/John List/MHT/Downloaded Excels/Fully_Downloaded_Econometrica_2000-2025.xlsx'
DOWNLOAD_FOLDER = '/Users/zachklopping/Desktop/John List/MHT/Scrapes/ECMA Downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

DROPBOX_TOKEN = "sl.u.AGDAuPX1JQ_PSMdT2v9HZEbPo0d9UJnKFxDkCFETq6QLp2o5-hy1qd3YG53RGPdb7-1XPSrJVGM8-_yun7UtQjdCVOmrN9n6qqEzsoyKYOejTjZ1fR1eOdSfb8hyoiw9wCrVNE01Lu77AP9KjYbgyFHlnoSKVe2TvauWKVHDqDCpCz5Oa78C1Qkwe4A_DnMDMDLMEKXxSlbWmnTIHvGbo2RlS-6GnUO4s4zMnxN0QsqITghCMU_UCc1t_GSeXWYHA78gl5StLLisO4HsXFQhC5ovO0uoDdeeITUtToCVc9aZ6UoF9dKQEBGC4OKQWwjLOU1zfUD2SNZLw9q_JS-aMlEoFu4BWe8maqYLTpzySYi35tYohNP8PZsnc-6fx1l6FnP2UWGlauhXqd8EfAP7RF0BeNntJWAyIbXjAUCXT9mPeZx3mGeboJYUUKgTDDM1fx-9dk3wb--ey9offhFlbNoR9aPYCXgeCI2c4VPHweV1eliqO-G7z7_CbZFopUHUw1Z9T9bni8F8bwUj5DHeqS9DBF0oKao7K0cCRNkuq_j_bzVWV1wI7hPXt8IXQ1W8tSe09Fnf9QvDHDAvzlaMdsMwwaCrQSuB0fJPBtpzySeShuUQy9QW7ZUsFCT-cCiwhD0KksAovvJjrcQ10SmfXdoiuL54R_C1Qo-kKv-jUW9Z7pV2N46jTekXs9ePb4yKIrtghhF59g23Be90qdZd1BLFyNVVc2LmrjrdkC9FmhPZ2lwe1bRPjFIN7dPtslqwEBNc1AFt8w73lbtP8O1Z8pk8Us8p0-7M5i47w9kyhPkjeSjroZxWOFDUvt76W454h7n4WsPca5Ev6m9HZXVuuaKD9oRklgPjrNkPIlKiOA4T_nYt6s1rJDaeflvFYxeizcdH3YSkXC0gpHfOOJ63j7hl3jJo8viEAEX71-B7dsgciQsEr79-RQ1beUduruuXSo2Mb63zTTqbwZp50s_faWsBIWT4T92MYCTxou6BBty-d2a8TipdoNA47gh0TB4tEOFiqQiZ5hM9IMY6Fp4by-IK3Lbyg4XBb37Sw9g5QZledlPQUu3MWXp07T6WdVBqVO8Lx2uq5VncCD9vnOkfFF6yeO5UWkP0Fw_JsyKDBDKRXNq8sdEoayt1IxuY3Zsh2KItjTckk7JJBT_AOgXS5aB3mHABBXoh666Sr6w9oW4FWktCQXqRAVEcy4H7B7AxuQ7kD6DWiAHkVRqGxG8m8VJjBCg-_IHfueHrFYt79yuinZJAIwVQhaC0jwNmwUfuY-Hc2tThBTLnwueB0E3mdbqHFQnWP93iSdzA0gjSCXIUN5gnBd1lqhfWeIGrr7Dd8duCXh0uHPhpTTmMRRKnDVS22-nOaU2Vr6muTnKq1o6xrxK3Q1L__IWNA9dSACNYwwiR7sOcttQuzVFKtnDYpyP1hnb4L7tabGx9mpsxVfDiPg"  # <-- your token
DROPBOX_FOLDER = "/MHT Data/ECMA"
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
if "supplementary_package" not in journal_data.columns:
    journal_data["supplementary_package"] = 0

to_download = journal_data[
    journal_data["supplementary_package"].fillna(0).astype(int) == 0
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
start_year = 2015
end_year = 2025

for year in range(start_year, end_year + 1):
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

            try:
                dbx_path = _upload_file_to_dropbox(target, DROPBOX_FOLDER, new_name)
                print(f"✅ Uploaded to Dropbox: {dbx_path}")
                os.remove(target)
            except Exception as e:
                print(f"Dropbox upload failed: {e}")

            # Fuzzy match & mark
            parsed = rec["heading"].lower().strip()
            choices = journal_data["title"].astype(str).str.lower().str.strip().tolist()
            best = process.extractOne(parsed, choices)
            if best and best[1] >= 90:
                match_str, score, idx = best
                journal_data.loc[
                    journal_data["title"].str.lower().str.strip() == match_str,
                    "supplementary_package"
                ] = 1
                print(f"✅ Marked supplementary for '{match_str}' (score {score})")
            else:
                print(f"⚠️ No good match for: {parsed}")

            journal_data.to_excel(EXCEL_PATH, index=False)
            time.sleep(2)  # pause before next download

# =========================
# Cleanup
# =========================
driver.quit()
print("\n🎉 All ECMA supplemental materials processed.")
