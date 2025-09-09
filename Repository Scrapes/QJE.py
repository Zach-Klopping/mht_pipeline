#!/usr/bin/env python3
import time
import os
import shutil
import pandas as pd
import regex as re
import undetected_chromedriver as uc
import json

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# Dropbox
import dropbox
from dropbox.files import WriteMode

# =========================
# CONFIG
# =========================
EXCEL_PATH = '/Users/zachklopping/Desktop/John List/MHT/Fully_Downloaded_QJE_2000-2025.xlsx'

download_folder = '/Users/zachklopping/Desktop/John List/MHT/QJE Scrapes/QJE Dataverse'
os.makedirs(download_folder, exist_ok=True)

supplementary_folder = '/Users/zachklopping/Desktop/John List/MHT/QJE Scrapes/QJE Supplementary'
os.makedirs(supplementary_folder, exist_ok=True)

# =========================
# DROPBOX CONFIG
# =========================
# Prefer using an env var:
DROPBOX_TOKEN  = 'sl.u.AF8iDfgAuI8ZLoUQKQ_H6eJJfs4WOqtt4b5Yw47O_AktFqlv003Ff8aXQE_2yQbjnWNPuILD6S_XN5_WBOiizcmzvnPevEZ6M5TbWZDkKrknH4hPFge3BuvCk5n21xpzQo4jludXcxz9BFtgoADcrr-Hcr9daK-Jpouvck0f27iFDIU2brGZaburEp4U_EMFbnLIdEUqSpBhOgaPaJDmAFjgDctO8M1jbKG825pjDlz4N29BSGZdxMNf3t5PB37Dgy-d1pFXEmZ9WA-bV3HgoqSJxllIAcJkneeRNh65GtJtlki6irPgSZpBu-8M8b9KQekqHUgDDQ_v_r9rSHOdPssgHG9CFWHjZBJ_WZKeULTf50wVSUnghmg6c6VgBJmkjGcnmN7cm5db_e1jdsNMVMnYFDtvXXuMPiEDVbGU1X2XdtWQHIXUmqEcyIP-rNUGbKDo6qOmc1qfWGgTyceGV5b_a3c5u_8yVEojLxh50u_SgprIzVTTvd2KuckjeDxiyt3vLGiKw0Z3ufqD39BqWwj_EzNfCEPf-yxC0nNs09yCiQETRbK3cCwYKSPvkwbc_aWekhh_d2qA4XFVkpN4wZne5NwfdxMjycy4-q0l1ctDcEXTfIxw4eTssSSdfAoJwXLZYsT9chAjUuway8TQpOQ_Cu3LoBk9YJQ0Hm6_lC7Wc0IumvKsodMSqi37bE8LucbK-PfX_y8-uQFQqWLVhycogqCDDxldkV_MgtB6fUeiBFADbJDmNx_Hi8ypq9ls6XogFzpkmV9GHo0SdwPiL4yhC2iamnaYVDdFzlqoYFAJfLufhu8UwzfNr0OAlSp8grjLyTFBsNuPt6QFIMjYaWWSCbMiK5371Hc1NtQljCzuZiBPNFS470ggy4j8-FwouAwFr0mpKirKagrTZY-0E2sLqvnuRBmm70g5YCsQ8eaufC6WPszc9ndqoUaFm_2O2An-PwFByKEhMCsGzWKQAPSXbpGRNlJhPSN7cN6f74rZ5gXx4_Ix9wprC8NLKnQ1t99EKFwofigm3LkOnTxiCQD23KIXprYEtT3qPs93WSqzvaqpMC8zi6Kr7yZu2l3SbEYHRhGjdNGJAKAjbTw4U7qkh3rIo5DzGA6ry-W_lckb-dxraw00NcQGBOFJhipacpNqJlOkFZkDHaNQkYGErwcqL8N-u7gH6D3YZ2NLOTVfDLfdsFaKcU0hZfadaQKR3MrFpJgZ58x2M_MrM8i4txhKmXGvqSn4AM-TiEOuseKrzyK7aTgqrN68hXhF5kfMrwQ6YAugZ_zAfOmBsXzgTYTDGyhVPVZVyG7sQIGMXFoAEiyhWGplyltv41QJzXRme-UDJCzuTWT_0Z2jXDgW0mpxblHIfTaNL-b77CjKYfOZPLLmSPw5_2CNxvdiT5an45TPo71a09sSzt3iqSLX4IJxYUnmwOhK8FZOez9uv37l2A'

DROPBOX_FOLDER_DATASET = "/MHT/QJE Replication Packages/Dataverse"
DROPBOX_FOLDER_SUPP    = "/MHT/QJE Replication Packages/Supplementary"

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
    """
    Upload file (chunked if large). Returns the Dropbox path (string).
    """
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

# Ensure the target folders exist
_ensure_dropbox_folder(DROPBOX_FOLDER_DATASET)
_ensure_dropbox_folder(DROPBOX_FOLDER_SUPP)

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

# Only rows where replication_package == 0 and year >= 2012
to_download = journal_data[
    (journal_data['replication_package'].fillna(0).astype(int) == 0)
    & (journal_data['year'] >= 2012)
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

def is_zip_url(href: str) -> bool:
    """Return True if href (before query string) ends with .zip"""
    if not isinstance(href, str):
        return False
    return href.lower().split('?', 1)[0].endswith('.zip')

# =========================
# Main scraping loop
# =========================
for orig_idx, row in to_download.iterrows():
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

        # Parse the article page for the "Data Availability" heading, else fallback to a Supplementary Data ZIP link
        soup = BeautifulSoup(driver.page_source, "html.parser")

        doi_url = None
        heading = soup.find("h2", string=lambda t: t and "data availability" in t.lower())
        if heading:
            doi_link = heading.find_next("a", href=True)
            if doi_link and isinstance(doi_link.get("href"), str) and doi_link["href"].startswith("https://doi.org"):
                doi_url = doi_link["href"]

        if doi_url:
            print("🔗 Found DOI:", doi_url)
        else:
            # Fallback: try to find a "Supplementary" .zip link
            candidate = None

            # 1) Prefer anchors whose text includes 'supplement' and whose href is a ZIP
            for a in soup.find_all("a", href=True):
                text = (a.get_text(strip=True) or "").lower()
                if "supplement" in text and is_zip_url(a["href"]):
                    candidate = a
                    break

            # 2) If not found, accept any .zip on page that looks like supplementary
            if not candidate:
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = (a.get_text(strip=True) or "").lower()
                    if is_zip_url(href) and ("supplement" in text or "appendix" in text or "ancillary" in text or "data" in text):
                        candidate = a
                        break

            if candidate:
                supp_href = candidate["href"]
                print(f"🔁 No Data Availability DOI; found supplementary ZIP link: {supp_href}")

                # Click it via Selenium (use exact href match)
                try:
                    el = driver.find_element(By.XPATH, f"//a[@href={json.dumps(supp_href)}]")
                except Exception:
                    # Sometimes relative vs absolute; try a contains fallback
                    el = driver.find_element(By.XPATH, f"//a[contains(@href, {json.dumps(supp_href.split('/')[-1])})]")

                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)

                # Wait for the ZIP to land
                dataset_path = wait_for_file(download_folder, exts=(".zip",), timeout=240)
                if dataset_path and os.path.exists(dataset_path):
                    safe_title = clean_title_for_filename(title)
                    new_filename = f"QJE_{safe_title}.zip"
                    target_path = os.path.join(supplementary_folder, new_filename)
                    shutil.move(dataset_path, target_path)
                    print(f"📥 Supplementary ZIP saved locally: {target_path}")

                    # --- Upload to Dropbox (Supplementary) then delete local ---
                    dest_name = f"QJE_{safe_title}.zip"
                    try:
                        dbx_path = _upload_file_to_dropbox(target_path, DROPBOX_FOLDER_SUPP, dest_name)
                        print(f"✅ Uploaded to Dropbox: {dbx_path}")
                        try:
                            os.remove(target_path)
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"❌ Dropbox upload failed; keeping local file: {e}")

                    journal_data.at[orig_idx, 'replication_package'] = 1
                    journal_data.to_excel(EXCEL_PATH, index=False)
                    time.sleep(2)
                    continue
                else:
                    print("❌ Supplementary ZIP download did not appear in time.")
                    continue
            else:
                print("❌ No Data Availability DOI and no supplementary ZIP link found.")
                continue

        # Go to DOI (Dataverse landing page expected)
        driver.get(doi_url)

        # --- On the Dataverse landing page: click "Access Dataset", then a download item ---
        try:
            access_button = WebDriverWait(driver, 12).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-access-dataset"))
            )
            access_button.click()
            print("✅ Clicked 'Access Dataset' button.")

            # Click the FIRST btn-download link
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

                # --- Upload to Dropbox (Dataverse) then delete local ---
                dest_name = f"QJE_{safe_title}.zip"
                try:
                    dbx_path = _upload_file_to_dropbox(target_path, DROPBOX_FOLDER_DATASET, dest_name)
                    print(f"✅ Uploaded to Dropbox: {dbx_path}")
                    try:
                        os.remove(target_path)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"❌ Dropbox upload failed; keeping local file: {e}")

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
