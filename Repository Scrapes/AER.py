import os
import time
import shutil
import pandas as pd
import regex as re
from bs4 import BeautifulSoup

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

# Dropbox
import dropbox
from dropbox.files import WriteMode

# =========================
# CONFIG (edit paths/colnames)
# =========================
EXCEL_PATH       = '/Users/zachklopping/Desktop/John List/MHT/Fixed Data/Fully_Downloaded_AER_2000-2025.xlsx'
URL_COL          = 'url'       # Excel column with article landing page URL
TITLE_COL        = 'title'     # Excel column with article title
FLAG_COL         = 'replication_package'  # 0 = needs download, 1 = done

# TEMP local staging folder (downloads land here, then get uploaded to Dropbox)
DOWNLOAD_FOLDER  = '/tmp/aer_downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ICPSR credentials (best via env vars)
ICPSR_USER = os.getenv("ICPSR_USER", "")
ICPSR_PASS = os.getenv("ICPSR_PASS", "")

# =========================
# DROPBOX CONFIG
# =========================
DROPBOX_TOKEN  = 'sl.u.AF8iDfgAuI8ZLoUQKQ_H6eJJfs4WOqtt4b5Yw47O_AktFqlv003Ff8aXQE_2yQbjnWNPuILD6S_XN5_WBOiizcmzvnPevEZ6M5TbWZDkKrknH4hPFge3BuvCk5n21xpzQo4jludXcxz9BFtgoADcrr-Hcr9daK-Jpouvck0f27iFDIU2brGZaburEp4U_EMFbnLIdEUqSpBhOgaPaJDmAFjgDctO8M1jbKG825pjDlz4N29BSGZdxMNf3t5PB37Dgy-d1pFXEmZ9WA-bV3HgoqSJxllIAcJkneeRNh65GtJtlki6irPgSZpBu-8M8b9KQekqHUgDDQ_v_r9rSHOdPssgHG9CFWHjZBJ_WZKeULTf50wVSUnghmg6c6VgBJmkjGcnmN7cm5db_e1jdsNMVMnYFDtvXXuMPiEDVbGU1X2XdtWQHIXUmqEcyIP-rNUGbKDo6qOmc1qfWGgTyceGV5b_a3c5u_8yVEojLxh50u_SgprIzVTTvd2KuckjeDxiyt3vLGiKw0Z3ufqD39BqWwj_EzNfCEPf-yxC0nNs09yCiQETRbK3cCwYKSPvkwbc_aWekhh_d2qA4XFVkpN4wZne5NwfdxMjycy4-q0l1ctDcEXTfIxw4eTssSSdfAoJwXLZYsT9chAjUuway8TQpOQ_Cu3LoBk9YJQ0Hm6_lC7Wc0IumvKsodMSqi37bE8LucbK-PfX_y8-uQFQqWLVhycogqCDDxldkV_MgtB6fUeiBFADbJDmNx_Hi8ypq9ls6XogFzpkmV9GHo0SdwPiL4yhC2iamnaYVDdFzlqoYFAJfLufhu8UwzfNr0OAlSp8grjLyTFBsNuPt6QFIMjYaWWSCbMiK5371Hc1NtQljCzuZiBPNFS470ggy4j8-FwouAwFr0mpKirKagrTZY-0E2sLqvnuRBmm70g5YCsQ8eaufC6WPszc9ndqoUaFm_2O2An-PwFByKEhMCsGzWKQAPSXbpGRNlJhPSN7cN6f74rZ5gXx4_Ix9wprC8NLKnQ1t99EKFwofigm3LkOnTxiCQD23KIXprYEtT3qPs93WSqzvaqpMC8zi6Kr7yZu2l3SbEYHRhGjdNGJAKAjbTw4U7qkh3rIo5DzGA6ry-W_lckb-dxraw00NcQGBOFJhipacpNqJlOkFZkDHaNQkYGErwcqL8N-u7gH6D3YZ2NLOTVfDLfdsFaKcU0hZfadaQKR3MrFpJgZ58x2M_MrM8i4txhKmXGvqSn4AM-TiEOuseKrzyK7aTgqrN68hXhF5kfMrwQ6YAugZ_zAfOmBsXzgTYTDGyhVPVZVyG7sQIGMXFoAEiyhWGplyltv41QJzXRme-UDJCzuTWT_0Z2jXDgW0mpxblHIfTaNL-b77CjKYfOZPLLmSPw5_2CNxvdiT5an45TPo71a09sSzt3iqSLX4IJxYUnmwOhK8FZOez9uv37l2A'
DROPBOX_FOLDER = "/MHT/AER Replication Packages"  # must start with "/"

if not DROPBOX_TOKEN:
    raise RuntimeError("Missing DROPBOX_TOKEN env var for Dropbox API.")

# =========================
# SELENIUM SETUP
# =========================
options = uc.ChromeOptions()
prefs = {
    "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    "download.default_directory": DOWNLOAD_FOLDER,
    "download.prompt_for_download": False,
    "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "application/pdf",
}
options.add_experimental_option("prefs", prefs)
options.add_argument("--disable-blink-features=AutomationControlled")
driver = uc.Chrome(options=options)

# =========================
# HELPERS
# =========================
def sanitize_for_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_")

def wait_for_download_since(dir_path, before_set, timeout=900):
    """
    Wait for a new download that started after we took `before_set`.
    - Waits for a new *.crdownload or a new file to appear
    - Then waits until all *.crdownload files disappear
    - Then waits until the newest new file's size stabilizes
    Returns: full path to the finished file, or None on timeout.
    """
    end = time.time() + timeout

    def list_all():
        return [f for f in os.listdir(dir_path) if not f.startswith('.')]

    def list_new():
        return [f for f in list_all() if f not in before_set]

    # 1) Wait for any new file
    while time.time() < end:
        if list_new():
            break
        time.sleep(0.25)
    if time.time() >= end:
        return None

    # 2) Wait until no .crdownload files remain
    while time.time() < end:
        any_cr = any(name.endswith('.crdownload') for name in list_all())
        if not any_cr:
            break
        time.sleep(0.25)
    if time.time() >= end:
        return None

    # 3) Pick the newest finished one and wait for size stabilization
    new_finished = [f for f in list_new() if not f.endswith('.crdownload')]
    if not new_finished:
        return None

    paths = [os.path.join(dir_path, f) for f in new_finished]
    target = max(paths, key=os.path.getctime)

    while time.time() < end:
        s1 = os.path.getsize(target)
        time.sleep(1.0)
        s2 = os.path.getsize(target)
        if s1 == s2:
            return target
    return None

# =========================
# DROPBOX CLIENT & HELPERS
# =========================
dbx = dropbox.Dropbox(DROPBOX_TOKEN)
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB

def ensure_dropbox_folder(folder_path: str):
    """Create folder if it doesn't exist; ignore if already exists."""
    folder_path = folder_path.rstrip("/") or "/"
    if folder_path == "/":
        return
    try:
        dbx.files_create_folder_v2(folder_path)
    except dropbox.exceptions.ApiError as e:
        # Ignore folder-already-exists errors
        if not (hasattr(e, "error") and getattr(e.error, "is_path", False)):
            pass

def upload_file_to_dropbox(local_path: str, dropbox_folder: str, dest_name: str) -> str:
    """
    Uploads file at `local_path` to Dropbox folder `dropbox_folder` with name `dest_name`.
    Uses chunked upload for large files. Returns the Dropbox path.
    """
    dropbox_folder = dropbox_folder.rstrip("/")
    if not dropbox_folder.startswith("/"):
        dropbox_folder = "/" + dropbox_folder
    dropbox_path = f"{dropbox_folder}/{dest_name}"
    file_size = os.path.getsize(local_path)

    with open(local_path, "rb") as f:
        if file_size <= CHUNK_SIZE:
            dbx.files_upload(
                f.read(), dropbox_path,
                mode=WriteMode("add"), mute=True, autorename=True
            )
        else:
            session_start = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
            cursor = dropbox.files.UploadSessionCursor(
                session_id=session_start.session_id, offset=f.tell()
            )
            commit = dropbox.files.CommitInfo(
                path=dropbox_path, mode=WriteMode("add"), autorename=True, mute=True
            )
            while f.tell() < file_size:
                if (file_size - f.tell()) <= CHUNK_SIZE:
                    dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                else:
                    dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                    cursor.offset = f.tell()
    return dropbox_path

def get_or_create_shared_link(dbx_path: str) -> str | None:
    try:
        meta = dbx.sharing_create_shared_link_with_settings(dbx_path)
        return meta.url
    except dropbox.exceptions.ApiError:
        try:
            links = dbx.sharing_list_shared_links(path=dbx_path, direct_only=True).links
            if links:
                return links[0].url
        except Exception:
            return None
    return None

# Ensure target folder exists in Dropbox
ensure_dropbox_folder(DROPBOX_FOLDER)

# =========================
# LOAD DATA & FILTER
# =========================
journal_data = pd.read_excel(EXCEL_PATH)
if FLAG_COL not in journal_data.columns:
    journal_data[FLAG_COL] = 0

to_download = journal_data[journal_data[FLAG_COL].fillna(0).astype(int) == 0].copy()
print(f"Rows remaining: {len(to_download)}")

# =========================
# MAIN LOOP
# =========================
for index, row in to_download[::-1].iterrows():
    try:
        title = row.get(TITLE_COL, "")
        url = row.get(URL_COL, "")
        print(f"\n📄 Processing index={index}: {title}")

        if not isinstance(url, str) or not url.strip():
            print("⚠️  Skipping: URL missing.")
            continue

        # 1) Open AER landing page
        driver.get(url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.0)

        # 2) Find the ICPSR link within the article section
        soup = BeautifulSoup(driver.page_source, "lxml")
        article_section = soup.select_one("section.primary.article-detail.journal-article")
        if not article_section:
            print("⚠️  Skipping: article section not found.")
            continue

        icpsr_links = article_section.find_all("a", class_="track-icpsr")
        if not icpsr_links:
            print("⚠️  Skipping: ICPSR link not found on page.")
            continue

        icpsr_url = icpsr_links[0].get("href")
        if not icpsr_url:
            print("⚠️  Skipping: ICPSR link has no href.")
            continue

        # 3) Go to ICPSR landing (project/file page)
        driver.get(icpsr_url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.0)

        # 4) Follow the "Download this project/file" link (normal <a>)
        print("📥 Following 'Download' href…")
        download_a = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "downloadButton"))
        )
        download_href = download_a.get_attribute("href")
        if not download_href:
            print("❌ No href on download button.")
            continue
        driver.get(download_href)
        time.sleep(1.0)

        # 4b) If redirected to login, handle it
        if "login" in driver.current_url.lower() and (ICPSR_USER and ICPSR_PASS):
            print("🔐 Login required. Attempting login…")
            try:
                email_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "kc-emaillogin"))
                )
                email_button.click()
                time.sleep(0.5)
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "username")))
                driver.find_element(By.NAME, "username").send_keys(ICPSR_USER)
                driver.find_element(By.NAME, "password").send_keys(ICPSR_PASS)
                driver.find_element(By.XPATH, "//input[@type='submit']").click()
                time.sleep(2.0)
            except Exception as e:
                print(f"❌ Login flow failed: {e}")
                continue

        # 5) Terms page often reuses id=downloadButton for final "I Agree"/download.
        before = set([f for f in os.listdir(DOWNLOAD_FOLDER) if not f.startswith('.')])

        try:
            agree_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "downloadButton"))
            )
            print("☑️ Clicking final 'Download' / 'I Agree'…")
            agree_btn.click()
        except Exception:
            print("ℹ️ No explicit 'I Agree' button; expecting auto-start download.")

        # 6) Wait for a NEW file (since snapshot) to finish downloading
        file_path = wait_for_download_since(DOWNLOAD_FOLDER, before_set=before, timeout=900)
        if not file_path:
            print("❌ Download failed or timed out.")
            continue

        # 7) Rename locally → upload to Dropbox → delete local
        article_title = sanitize_for_filename(title)
        ext = os.path.splitext(file_path)[1] or ".zip"
        new_name = f"Replication_AER_{article_title}{ext}"
        new_path = os.path.join(DOWNLOAD_FOLDER, new_name)
        shutil.move(file_path, new_path)

        print(f"📤 Uploading to Dropbox: {new_name}")
        try:
            dropbox_dest = upload_file_to_dropbox(new_path, DROPBOX_FOLDER, new_name)
            print(f"✅ Uploaded to Dropbox: {dropbox_dest}")
            # Optional: free up disk
            try:
                os.remove(new_path)
            except Exception:
                pass

            # (Optional) create or fetch shared link
            link = get_or_create_shared_link(dropbox_dest)
            if link:
                print(f"🔗 Dropbox link: {link}")

            # Mark row complete
            journal_data.at[index, FLAG_COL] = 1
            journal_data.to_excel(EXCEL_PATH, index=False)
        except Exception as e:
            print(f"❌ Dropbox upload failed; keeping local file: {e}")
            # You may choose to not mark complete in this case

        time.sleep(1.0)

    except Exception as e:
        print(f"❌ Unexpected error at index {index}: {e}")
        continue

# =========================
# TEARDOWN
# =========================
driver.quit()
print("Done.")
