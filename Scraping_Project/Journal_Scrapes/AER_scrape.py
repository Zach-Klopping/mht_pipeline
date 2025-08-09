import time
import os
import shutil
import pandas as pd
import regex as re

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# INSTANTIATE THE SELENIUM DRIVER.

options = webdriver.ChromeOptions()

# ----------------------------------------------
# CHANGE DOWNLOAD FOLDER TO MATCH WHERE YOU WANT THE FILES TO DOWNLOAD TO
# ----------------------------------------------

download_folder = '/Users/zachklopping/Desktop/List 25/List Scraping Project/AER Scraped Papers'

profile = {
    "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "applications/pdf"
}

options = Options()
options.add_experimental_option("prefs", profile)

# ----------------------------------------------
# DOWNLOAD CHROME DRIVER AND PUT IT IN A FOLDER, THEN CHANGE
# TO WHERE YOU PUT THE CHROMEDRIVER IN.
# LINK: https://chromedriver.chromium.org/downloads
# ----------------------------------------------

service = Service('/Users/zachklopping/Desktop/List 25/List Scraping Project/chromedriver-mac-arm64/chromedriver')

# READ THE EXCEL FOR THE JOURNAL TO RETRIEVE THE LINKS

# ----------------------------------------------
# CHANGE DIRECTORY TO MATCH LOCATION OF EXCEL FILE.
# ----------------------------------------------
journal_data = pd.read_excel('/Users/zachklopping/Desktop/GitHub/JL_Summer_25/Scraping_Project/Data_fix/Combined Data/AER_2000-2025.xlsx')

# Step 1: Find the cover date column
journal_data['coverDate'] = pd.to_datetime(journal_data['coverDate'], errors='coerce')

# Step 2: Define the threshold date
threshold_date = pd.to_datetime("2022-01-01")

# Step 3: Filter the DataFrame
journal_data = journal_data[journal_data['coverDate'] >= threshold_date]

journal_data.reset_index()

# -------------------
# MAIN LOOP
# -------------------

driver = webdriver.Chrome(service=service, options=options)

for index, row in journal_data.iterrows():
    try:
        print(f"Processing index {index}: {row['title']}")

        # 1. Open article page
        driver.get(row['url'])
        time.sleep(5)

        # 2. Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, features="lxml")
        m = soup.find_all("section", {"primary article-detail journal-article"})

        if not m:
            print("Skipping: article-detail section not found.")
            continue

        links = m[0].find_all('a', {'class': 'button'})
        if not links:
            print("Skipping: no download button found.")
            continue

        tail = links[0].get('href')
        if not tail:
            print("Skipping: button has no href.")
            continue

        # 3. Visit the actual PDF download page
        pdf_url = 'https://www.aeaweb.org' + tail
        driver.get(pdf_url)
        time.sleep(4)

        # 4. Clean title for filename
        article_title = re.sub('[^A-Za-z0-9]+', '_', row['title'])

        # 5. Wait for download to appear
        timeout = 60
        start_time = time.time()
        filename = None

        while time.time() - start_time < timeout:
            pdfs = [f for f in os.listdir(download_folder) if f.endswith(".pdf")]
            if pdfs:
                filename = max([os.path.join(download_folder, f) for f in pdfs], key=os.path.getctime)
                break
            time.sleep(1)

        if not filename:
            print("Download failed or timed out.")
            continue

        # 6. Rename downloaded file
        new_filename = f"AER_{index}_{article_title}.pdf"
        shutil.move(filename, os.path.join(download_folder, new_filename))
        print(f"Downloaded: {new_filename}")

        time.sleep(10)

    except Exception as e:
        print(f"Error at index {index}: {e}")
        continue

driver.quit()

