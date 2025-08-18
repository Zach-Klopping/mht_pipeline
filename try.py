#!/usr/bin/env python3
# Batch JPE downloader (proxy-safe + Excel loop)
# - Reads URLs from Excel where downloaded == 0
# - Forces/maintains UIowa EZproxy on all navigations
# - Logs in if prompted (fields: name="user1", name="pass")
# - ePDF → Download menu → Direct download
# - Saves as JPE_<title-from-excel>.pdf
# - Updates Excel 'downloaded' column to 1 after success

import os
import time
import shutil
import pandas as pd
import regex as re
from urllib.parse import urlparse, urlunparse, urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver import ActionChains
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# =========================
# CONFIG (edit these)
# =========================
EXCEL_PATH = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Combined Data/Download_JPE_2000-2025.xlsx'
download_folder = '/Users/zachklopping/Desktop/List 25/MHT/Scrapes/Scraped Papers/JPE Scraped Papers'
os.makedirs(download_folder, exist_ok=True)

# ---- Login credentials ----
# Safer to set env vars: export UIOWA_USER="..." ; export UIOWA_PASS="..."
USERNAME   = os.getenv('UIOWA_USER') or 'zklopping'
PASSWORD   = os.getenv('UIOWA_PASS') or 'PurpleRockies64$'
USER_FIELD = 'user1'
PASS_FIELD = 'pass'

HEADLESS = False

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
if HEADLESS:
    options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")

driver = uc.Chrome(options=options)

# =========================
# Helpers
# =========================
def is_proxied_host(host: str) -> bool:
    return host.endswith('.proxy.lib.uiowa.edu')

def hyphenate_host(host: str) -> str:
    # journals.uchicago.edu -> journals-uchicago-edu
    return host.replace('.', '-')

def to_proxied_url(url: str, current_host: str) -> str:
    """
    If the current page is proxied and `url` isn't, rewrite it into EZproxy form:
    <hyphenated-origin>.proxy.lib.uiowa.edu
    """
    try:
        if not is_proxied_host(current_host):
            return url  # Not currently on proxy; leave as-is
        u = urlparse(url)
        if not u.netloc:
            return url  # Relative is fine (inherits current proxied host)
        if is_proxied_host(u.netloc):
            return url  # Already proxied
        proxied_host = f"{hyphenate_host(u.netloc)}.proxy.lib.uiowa.edu"
        return urlunparse((u.scheme or 'https', proxied_host, u.path, u.params, u.query, u.fragment))
    except Exception:
        return url

def force_proxied_start(url: str) -> str:
    """
    If starting URL is not proxied and is absolute, force it through UIowa EZproxy.
    """
    u = urlparse(url)
    if not u.netloc:
        return url  # relative; caller should resolve against a proxied page
    if is_proxied_host(u.netloc):
        return url
    proxied_host = f"{hyphenate_host(u.netloc)}.proxy.lib.uiowa.edu"
    return urlunparse((u.scheme or 'https', proxied_host, u.path, u.params, u.query, u.fragment))

def ensure_proxied_current(fallback_url: str):
    """
    If we ever fall off the proxy, re-enter via the proxied fallback URL.
    """
    cur_host = urlparse(driver.current_url).netloc
    if is_proxied_host(cur_host):
        return
    print("⚠️ Proxy missing; reloading via proxy…")
    driver.get(force_proxied_start(fallback_url))
    print(f"↪️ Re-proxied to: {driver.current_url}")

def wait_for_pdf(download_dir: str, timeout: int = 180) -> str | None:
    start = time.time()
    while time.time() - start < timeout:
        if any(name.endswith(".crdownload") for name in os.listdir(download_dir)):
            time.sleep(1); continue
        pdfs = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.lower().endswith(".pdf")]
        if pdfs:
            return max(pdfs, key=os.path.getctime)
        time.sleep(1)
    return None

def clean_title_for_filename(title: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(title)).strip("_")
    return s or "JPE_Article"

def accept_cookies_if_present():
    tried = False
    try:
        tried = True
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="cookie-notice"]/p[3]/a[2]'))
        ).click()
        print("✅ Cookie banner accepted (xpath A).")
        time.sleep(1); return
    except Exception:
        pass
    for sel in ["#onetrust-accept-btn-handler",
                "button[aria-label='accept cookies']",
                "button[aria-label='Accept Cookies']",
                "button#accept-cookies"]:
        try:
            tried = True
            btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
            btn.click(); print(f"✅ Cookie banner accepted ({sel}).")
            time.sleep(1); return
        except Exception:
            continue
    if tried:
        print("ℹ️ No clickable cookie banner matched.")

def login_if_prompted(timeout: int = 15):
    # quick probe for username field
    try:
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.NAME, USER_FIELD)))
    except TimeoutException:
        return
    try:
        print("🔐 Login form detected — logging in…")
        user_input = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.NAME, USER_FIELD)))
        pass_input = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.NAME, PASS_FIELD)))
        user_input.clear(); user_input.send_keys(USERNAME)
        pass_input.clear(); pass_input.send_keys(PASSWORD)
        try:
            submit = driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
            submit.click()
        except NoSuchElementException:
            pass_input.submit()
        WebDriverWait(driver, 20).until(lambda d: "login" not in d.current_url.lower())
        time.sleep(1)
        print(f"🔓 Logged in. URL: {driver.current_url}")
    except Exception as e:
        print(f"❌ Login attempt failed: {e}")

def robust_download_click():
    # 1) Wait for any overlay to disappear
    try:
        WebDriverWait(driver, 15).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "overlay-screen"))
        )
    except Exception:
        pass

    # 2) Open the download menu
    for _ in range(2):
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#new-download-btn, button#new-download-btn"))
            )
        except TimeoutException:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="new-download-btn"]'))
            )
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'})", btn)
            try:
                btn.click()
            except Exception:
                ActionChains(driver).move_to_element(btn).click().perform()
            break
        except StaleElementReferenceException:
            continue
    print("✅ Opened download menu.")

    # 3) Click “Direct download” (several fallbacks)
    selectors = [
        (By.XPATH, '//*[@id="app-navbar"]/div[3]/div[3]/div/div[1]/div/ul[1]/li[1]/a'),
        (By.CSS_SELECTOR, 'div#app-navbar ul li a[href*="download"]'),
        (By.XPATH, "//a[contains(., 'Direct download') or contains(., 'Direct Download')]"),
    ]
    link = None
    for by, sel in selectors:
        try:
            link = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((by, sel)))
            break
        except TimeoutException:
            continue
    if not link:
        raise TimeoutException("Direct download link not found.")

    existing_tabs = set(driver.window_handles)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", link)
    try:
        link.click()
    except Exception:
        driver.execute_script("arguments[0].click();", link)
    time.sleep(1)

    # If a new tab opened, switch into it so the download starts
    new_tabs = set(driver.window_handles) - existing_tabs
    if new_tabs:
        driver.switch_to.window(list(new_tabs)[0])
        print("↪️ Switched to new tab for download.")

# =========================
# Load and filter data
# =========================
journal_data = pd.read_excel(EXCEL_PATH)
if "downloaded" not in journal_data.columns:
    journal_data["downloaded"] = 0
to_download = journal_data[journal_data["downloaded"].fillna(0).astype(int) == 0]

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
        start_url = force_proxied_start(url)
        driver.get(start_url)
        print("URL:", driver.current_url)

        accept_cookies_if_present()
        login_if_prompted()
        time.sleep(1)
        ensure_proxied_current(start_url)

        # ---- Find/open the ePDF (proxy-safe) ----
        try:
            epdf_link_elem = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='/doi/epdf/']"))
            )
            epdf_href = epdf_link_elem.get_attribute("href") or epdf_link_elem.get_attribute("data-url") or ""
            epdf_abs = urljoin(driver.current_url, epdf_href)
            epdf_abs = to_proxied_url(epdf_abs, current_host=urlparse(driver.current_url).netloc)
            print(f"🔗 ePDF URL (resolved): {epdf_abs}")
            driver.get(epdf_abs)
        except Exception:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            tag = soup.find("a", href=re.compile(r"/doi/epdf/")) or soup.find("a", href=re.compile(r"https?://.*/doi/epdf/"))
            if not tag:
                raise ValueError("No ePDF button found on the article page.")
            href = tag.get("href", "")
            epdf_abs = urljoin(driver.current_url, href)
            epdf_abs = to_proxied_url(epdf_abs, current_host=urlparse(driver.current_url).netloc)
            print(f"🔗 ePDF URL (soup): {epdf_abs}")
            driver.get(epdf_abs)

        print("URL:", driver.current_url)
        accept_cookies_if_present()
        login_if_prompted()
        ensure_proxied_current(start_url)

        # ---- Download via viewer menu ----
        robust_download_click()

        # ---- Wait for PDF, then rename using Excel title ----
        downloaded_path = wait_for_pdf(download_folder, timeout=180)
        if not downloaded_path or not os.path.exists(downloaded_path):
            print(f"[{orig_idx}] ❌ Download failed or timed out.")
            continue

        safe_title = clean_title_for_filename(title)
        new_filename = f"JPE_{safe_title}.pdf"
        target_path = os.path.join(download_folder, new_filename)
        shutil.move(downloaded_path, target_path)
        print(f"[{orig_idx}] ✅ Saved as {target_path}")

        # ---- Mark as downloaded and save Excel ----
        journal_data.at[orig_idx, "downloaded"] = 1
        journal_data.to_excel(EXCEL_PATH, index=False)

        time.sleep(2)

    except Exception as e:
        print(f"[{orig_idx}] ❌ Error: {e}")
        continue

# =========================
# Cleanup
# =========================
driver.quit()
print("\n🎉 All done.")
