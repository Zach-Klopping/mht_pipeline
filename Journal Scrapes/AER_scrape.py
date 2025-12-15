import time
import os
import shutil
import re
import pandas as pd
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# Setup paths
excel_path = '' # Set your path to the Excel file here
download_dir = '' # Set your desired download directory here

if not os.path.exists(download_dir):
    os.makedirs(download_dir)

# Chrome options
options = uc.ChromeOptions()
prefs = {
    "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True,
    "download.extensions_to_open": "application/pdf"
}
options.add_experimental_option("prefs", prefs)
options.add_argument("--disable-blink-features=AutomationControlled")

driver = uc.Chrome(options=options, version_main=143)

# Load the sheet
df = pd.read_excel(excel_path)
if 'downloaded' not in df.columns:
    df['downloaded'] = 0

# Filter for rows we haven't done yet
todo = df[df['downloaded'] == 0]

def clean_filename(text):
    # just basic cleaning
    clean = re.sub(r'[^A-Za-z0-9]', '_', str(text))
    return clean.strip('_')

def check_download_folder(folder):
    # wait up to 30 seconds for the file
    start = time.time()
    while time.time() - start < 30:
        files = os.listdir(folder)
        pdfs = [f for f in files if f.endswith('.pdf')]
        # check for temp files
        temp = [f for f in files if f.endswith('.crdownload')]
        
        if pdfs and not temp:
            # return the newest file
            full_paths = [os.path.join(folder, f) for f in pdfs]
            return max(full_paths, key=os.path.getctime)
        time.sleep(1)
    return None

# Loop through the list
for idx, row in todo.iterrows():
    title = row['title']
    url = row['url']
    
    if not isinstance(url, str) or 'http' not in url:
        print(f"Skipping {idx} - bad url")
        continue

    print(f"Processing {idx}: {title}")

    try:
        driver.get(url)
        time.sleep(5) # let it load

        soup = BeautifulSoup(driver.page_source, "lxml")
        
        # Finding the download button
        article_box = soup.find("section", class_="primary article-detail journal-article")
        
        if article_box:
            dl_section = article_box.find("section", class_="download")
            if dl_section:
                btn = dl_section.find("a", class_="button")
                
                if btn and 'href' in btn.attrs:
                    link = btn['href']
                    if not link.startswith('http'):
                        link = "https://www.aeaweb.org" + link
                    
                    # trigger download
                    driver.get(link)
                    
                    # wait for it to finish
                    new_file = check_download_folder(download_dir)
                    
                    if new_file:
                        safe_title = clean_filename(title)
                        final_name = os.path.join(download_dir, f"AER_{safe_title}.pdf")
                        
                        shutil.move(new_file, final_name)
                        print(f"Saved: {title}")
                        
                        # mark as done and save immediately
                        df.at[idx, 'downloaded'] = 1
                        df.to_excel(excel_path, index=False)
                    else:
                        print("Download timed out")
                else:
                    print("No button found")
            else:
                print("No download section")
        else:
            print("Article section not found")
            
    except Exception as e:
        print(f"Error on {idx}: {e}")
        continue

print("Done")
driver.quit()