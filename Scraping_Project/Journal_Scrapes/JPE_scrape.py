import time
import os
import shutil
import pandas as pd
import regex as re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import undetected_chromedriver as uc


# Setup download folder
download_folder = "/Users/zachklopping/Desktop/List 25/List Scraping Project/JPE Scraped Papers"

# Chrome options
options = uc.ChromeOptions()
profile = {
    "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "applications/pdf"
}
options.add_experimental_option("prefs", profile)

# Start undetected Chrome driver
driver = uc.Chrome(options=options)

# Load journal data
journal_data = pd.read_excel(
    "/Users/zachklopping/Desktop/GitHub/JL_Summer_25/Scraping_Project/Data_fix/Combined Data/JPE_2000-2025.xlsx"
)

# Step 1: Find the cover date column
journal_data['coverDate'] = pd.to_datetime(journal_data['coverDate'], errors='coerce')

# Step 2: Define the threshold date
threshold_date = pd.to_datetime("2022-01-01")

# Step 3: Filter the DataFrame
journal_data = journal_data[journal_data['coverDate'] >= threshold_date]

# Main loop
for index, row in journal_data.iterrows():
    print(f"\nProcessing article {index}: {row['title']}")

    driver.get(row['url'])

    # Try to click cookie banner button
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="cookie-notice"]/p[3]/a[2]'))
        ).click()
        print("✅ Cookie banner accepted.")
        time.sleep(1)
    except (TimeoutException, NoSuchElementException):
        print("ℹ️ No cookie banner appeared.")

    time.sleep(5)

    # Parse the page and look for the PDF link
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    try:
        pdf_link_tag = soup.find("a", href=re.compile(r"^/doi/epdf/"))
        if not pdf_link_tag:
            raise ValueError("No se encontró el botón con enlace al epdf.")

        pdf_url = "https://www.journals.uchicago.edu" + pdf_link_tag["href"]
        print(f"🔗 ePDF URL found: {pdf_url}")
        driver.get(pdf_url)
    except Exception as e:
        print(f"❌ Could not find ePDF link for article {index}: {e}")
        continue

    try:
        WebDriverWait(driver, 15).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "overlay-screen"))
        )
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="new-download-btn"]'))
        ).click()
        print("✅ Opened download menu.")

        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="app-navbar"]/div[3]/div[3]/div/div[1]/div/ul[1]/li[1]/a'))
        ).click()
        print("✅ Clicked direct download button.")
    except Exception as e:
        print(f"❌ Error trying to download from epdf view: {e}")
        continue

    time.sleep(20) 

    article_title = re.sub('[^A-Za-z0-9]+', '_', row['title'])

    try:
        filename = max(
            [os.path.join(download_folder, f) for f in os.listdir(download_folder)],
            key=os.path.getctime
        )
        new_filename = os.path.join(download_folder, f"JPE_{index}_{article_title}.pdf")
        shutil.move(filename, new_filename)
        print(f"✅ Saved as {new_filename}")
    except Exception as e:
        print(f"❌ Error moving/renaming file for article {index}: {e}")

    time.sleep(10)

driver.quit()
print("\n🎉 All done.")


