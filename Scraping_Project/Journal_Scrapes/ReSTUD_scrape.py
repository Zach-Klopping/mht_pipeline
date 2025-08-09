import time
import os
import shutil
import pandas as pd
import regex as re
import undetected_chromedriver as uc

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from bs4 import BeautifulSoup

# --------------------------
# Set download directory (update as needed)
# --------------------------
download_folder = '/Users/zachklopping/Desktop/List 25/List Scraping Project/RESTUD Scraped Papers'

# --------------------------
# Configure Chrome options
# --------------------------
options = uc.ChromeOptions()
prefs = {
    "download.default_directory": download_folder,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "applications/pdf"
}
options.add_experimental_option("prefs", prefs)

# --------------------------
# Initialize undetected ChromeDriver
# --------------------------
driver = uc.Chrome(options=options, headless=False)

# --------------------------
# Load journal metadata
# --------------------------
journal_data = pd.read_excel("/Users/zachklopping/Desktop/GitHub/JL_Summer_25/Scraping_Project/Data_fix/Combined Data/ReStud_2000-2025.xlsx")

# Step 1: Find the cover date column
journal_data['coverDate'] = pd.to_datetime(journal_data['coverDate'], errors='coerce')

# Step 2: Define the threshold date
threshold_date = pd.to_datetime("2022-01-01")

# Step 3: Filter the DataFrame
journal_data = journal_data[journal_data['coverDate'] >= threshold_date]

# --------------------------
# Main scraping loop
# --------------------------
for index, row in journal_data.iterrows():
    print(f"\nProcessing article {index}: {row['title']}")
    driver.get(row['url'])

    # Attempt to accept cookies if the banner appears
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="accept-button"]'))
        ).click()
        print("✅ Cookies banner accepted.")
        time.sleep(1)
    except (TimeoutException, NoSuchElementException):
        print("ℹ️ Cookies banner did not appear.")

    # Pause if Cloudflare challenge page is detected
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "cf-challenge-running"))
        )
        print("🛑 Cloudflare challenge detected. Please resolve it manually.")
        input("⏸ Press ENTER once you've completed the Cloudflare check...")
    except TimeoutException:
        print("✅ No Cloudflare challenge detected.")

    time.sleep(3)

    # Get page HTML and parse it
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    # Find the direct PDF download button and construct full URL
    try:
        pdf_button = soup.find("a", class_="al-link pdf article-pdfLink")
        if not pdf_button:
            raise ValueError("PDF button not found.")
        pdf_link = "https://academic.oup.com" + pdf_button["href"]
    except Exception as e:
        print(f"❌ Could not find PDF link for article {index}. Error: {e}")
        continue

    # Go to PDF link
    driver.get(pdf_link)
    time.sleep(4)

    # Clean article title for file naming
    article_title = re.sub('[^A-Za-z0-9]+', '_', row['title'])

    # Wait for the PDF to download
    time.sleep(25)

    # Find the most recently downloaded file
    try:
        filename = max([os.path.join(download_folder, f) for f in os.listdir(download_folder)],
                       key=os.path.getctime)
        new_filename = os.path.join(download_folder, f"ReSTUD_{index}_{article_title}.pdf")
        shutil.move(filename, new_filename)
        print(f"✅ File saved as {new_filename}")
    except Exception as e:
        print(f"❌ Error renaming/moving file for article {index}: {e}")

    time.sleep(10)

# --------------------------
# Close browser
# --------------------------
driver.quit()
print("\n🎉 All articles processed.")