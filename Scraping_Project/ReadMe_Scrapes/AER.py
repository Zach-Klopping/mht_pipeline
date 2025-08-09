import time
import os
import shutil
import pandas as pd
import regex as re
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ----------------------------------------------
# CONFIGURATION
# ----------------------------------------------
download_folder = '/Users/zachklopping/Desktop/List 25/List Scraping Project/AER Scraped README'

profile = {
    "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "applications/pdf"
}

options = Options()
options.add_experimental_option("prefs", profile)

service = Service('/Users/zachklopping/Desktop/List 25/List Scraping Project/chromedriver-mac-arm64/chromedriver')

journal_data = pd.read_excel('/Users/zachklopping/Desktop/GitHub/JL_Summer_25/Scraping_Project/Data_fix/Combined Data/AER_2000-2025.xlsx')

journal_data['coverDate'] = pd.to_datetime(journal_data['coverDate'], errors='coerce')
threshold_date = pd.to_datetime("2022-01-01")
journal_data = journal_data[journal_data['coverDate'] >= threshold_date]
journal_data.reset_index(drop=True, inplace=True)

# ----------------------------------------------
# MAIN LOOP
# ----------------------------------------------
driver = webdriver.Chrome(service=service, options=options)

for index, row in journal_data.iterrows():
    try:
        print(f"\n📄 Processing {index}: {row['title']}")

        driver.get(row['url'])
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "lxml")
        article_section = soup.find("section", {"primary article-detail journal-article"})

        if not article_section:
            print("⚠️  Skipping: article section not found.")
            continue

        icpsr_links = article_section.find_all("a", class_="track-icpsr")
        if not icpsr_links:
            print("⚠️  Skipping: ICPSR download link not found.")
            continue

        pdf_redirect_url = icpsr_links[0].get("href")
        if not pdf_redirect_url:
            print("⚠️  Skipping: download link has no href.")
            continue

        driver.get(pdf_redirect_url)
        time.sleep(4)
        soup = BeautifulSoup(driver.page_source, "lxml")

        # Collect all candidate links (PDFs or containing "readme")
        candidate_links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True).lower()
            if (
                href.lower().endswith(".pdf")
                or "pdf" in text
                or "readme" in href.lower()
                or "readme" in text
            ):
                candidate_links.append(urljoin(driver.current_url, href))

        # Fallback: Check folder for matches
        if not candidate_links:
            for link in soup.find_all("a", href=True):
                if "type=folder" in link["href"]:
                    folder_url = urljoin(driver.current_url, link["href"])
                    print("📂 Navigating into folder...")
                    driver.get(folder_url)
                    time.sleep(3)
                    soup = BeautifulSoup(driver.page_source, "lxml")
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        text = link.get_text(strip=True).lower()
                        if (
                            href.lower().endswith(".pdf")
                            or "pdf" in text
                            or "readme" in href.lower()
                            or "readme" in text
                        ):
                            candidate_links.append(urljoin(driver.current_url, href))
                    break

        if not candidate_links:
            print("❌ No matching files found.")
            continue

        for file_url in candidate_links:
            try:
                print(f"🔗 Attempting download: {file_url}")
                driver.get(file_url)
                time.sleep(3)

                # Click download button
                try:
                    print("📥 Clicking 'Download this file'...")
                    download_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "downloadButton"))
                    )
                    download_button.click()
                    time.sleep(4)

                    if "login" in driver.current_url.lower():
                        print("🔐 Login required. Attempting login...")
                        email_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.ID, "kc-emaillogin"))
                        )
                        email_button.click()
                        time.sleep(2)

                        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "username")))
                        driver.find_element(By.NAME, "username").send_keys("zachary-klopping@uiowa.edu")
                        driver.find_element(By.NAME, "password").send_keys("PurpleRockies64$")
                        driver.find_element(By.XPATH, "//input[@type='submit']").click()
                        print("✅ Login submitted.")
                        time.sleep(5)
                    else:
                        print("✅ No login required.")
                except Exception as e:
                    print(f"❌ Error clicking download/login: {e}")
                    continue

                try:
                    print("☑️ Clicking 'I Agree' to download...")
                    agree_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "downloadButton"))
                    )
                    agree_button.click()
                    time.sleep(5)
                except Exception as e:
                    print(f"❌ Failed to click 'I Agree': {e}")
                    continue

                article_title = re.sub(r"[^A-Za-z0-9]+", "_", row["title"])
                timeout = 60
                start_time = time.time()
                filename = None

                while time.time() - start_time < timeout:
                    files = os.listdir(download_folder)
                    files = [f for f in files if not f.startswith('.') and os.path.isfile(os.path.join(download_folder, f))]
                    if files:
                        filename = max([os.path.join(download_folder, f) for f in files], key=os.path.getctime)
                        break
                    time.sleep(1)

                if not filename:
                    print("❌ Download failed or timed out.")
                    continue

                file_ext = os.path.splitext(filename)[1]
                source_base = os.path.splitext(os.path.basename(file_url).split("?")[0])[0]
                new_filename = f"README_AER_{index}_{article_title}_{source_base}{file_ext}"
                shutil.move(filename, os.path.join(download_folder, new_filename))
                print(f"✅ Downloaded: {new_filename}")
                time.sleep(10)

            except Exception as e:
                print(f"❌ Error downloading file: {file_url} | {e}")
                continue

    except Exception as e:
        print(f"❌ Unexpected error at index {index}: {e}")
        continue

driver.quit()
