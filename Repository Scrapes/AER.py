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

# =========================
# CONFIG (edit paths/colnames)
# =========================
EXCEL_PATH       = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Combined Data/Download_AER_2000-2025.xlsx'
DOWNLOAD_FOLDER  = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Scraped Papers/AER Scraped Papers'
URL_COL          = 'url'       # Excel column with article landing page URL
TITLE_COL        = 'title'     # Excel column with article title
FLAG_COL         = 'replication_package'  # 0 = needs download, 1 = done

# ICPSR credentials (set here for simplicity)
# ICPSR_USER = "zachary-klopping@uiowa.edu"
# ICPSR_PASS = "PurpleRockies64$"
# Alternatively, use env vars:
ICPSR_USER = os.getenv("ICPSR_USER", "")
ICPSR_PASS = os.getenv("ICPSR_PASS", "")

# =========================
# SETUP
# =========================
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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

    # 1) Wait for any new file (including .crdownload) to appear
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

    # 3) Of the files that are NEW, pick the newest finished one and wait until size stabilizes
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
for index, row in to_download.iterrows():
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

        # 4) Follow the "Download this project/file" link (it's a normal <a>)
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
        #    Snapshot BEFORE triggering the final click so we wait for a brand-new file.
        before = set([f for f in os.listdir(DOWNLOAD_FOLDER) if not f.startswith('.')])

        try:
            agree_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "downloadButton"))
            )
            print("☑️ Clicking final 'Download' / 'I Agree'…")
            agree_btn.click()
        except Exception:
            # Some pages start downloading automatically upon visiting download_href.
            print("ℹ️ No explicit 'I Agree' button; expecting auto-start download.")

        # 6) Wait for a NEW file (since snapshot) to finish downloading
        file_path = wait_for_download_since(DOWNLOAD_FOLDER, before_set=before, timeout=900)
        if not file_path:
            print("❌ Download failed or timed out.")
            continue

        # 7) Rename and mark complete
        article_title = sanitize_for_filename(title)
        ext = os.path.splitext(file_path)[1] or ".zip"
        new_name = f"Replication_AER_{article_title}{ext}"
        new_path = os.path.join(DOWNLOAD_FOLDER, new_name)
        shutil.move(file_path, new_path)
        print(f"✅ Downloaded: {new_name}")

        journal_data.at[index, FLAG_COL] = 1
        journal_data.to_excel(EXCEL_PATH, index=False)

        time.sleep(1.0)

    except Exception as e:
        print(f"❌ Unexpected error at index {index}: {e}")
        continue

# =========================
# TEARDOWN
# =========================
driver.quit()
print("Done.")
