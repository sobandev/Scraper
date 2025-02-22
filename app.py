import time
import random
import logging
from flask import Flask, render_template, request, send_file
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv
import os

app = Flask(__name__)

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="scraper.log", filemode="a")

# User-Agent Rotation (Helps Avoid Detection)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

# Proxy List (Optional)
PROXIES = [
    # "http://proxy1.example.com:8080",
    # "http://proxy2.example.com:8080",
    # "http://proxy3.example.com:8080"
]

def scrape_and_upload(url):
    # Selenium Configuration
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Headless Mode
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid Bot Detection
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")  # Rotate User Agent

    # Use a random proxy if available
    if PROXIES:
        chrome_options.add_argument(f"--proxy-server={random.choice(PROXIES)}")

    # Start WebDriver
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        logging.error(f"Error starting WebDriver: {e}")
        return f"Error starting WebDriver: {e}", []

    logging.info(f"Opening {url}")

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)

        # Wait for the page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Parse Content with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Extract Data
        data = []
        headings = ["Tag", "Content"]
        for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
            text = tag.get_text(strip=True)
            if text:
                data.append([tag.name, text])

        logging.info(f"Extracted {len(data)} items.")

    except Exception as e:
        logging.error(f"Error scraping website: {e}")
        return f"Error scraping website: {e}", []

    finally:
        driver.quit()

    # Google Sheets API Setup
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
    except Exception as e:
        logging.error(f"Error setting up Google Sheets API: {e}")
        return f"Error setting up Google Sheets API: {e}", []

    # Open Google Sheet
    try:
        sheet = client.open("Web Scraping Data").sheet1
    except Exception as e:
        logging.error(f"Error opening Google Sheet: {e}")
        return f"Error opening Google Sheet: {e}", []

    # Insert Data into Google Sheets
    if data:
        try:
            sheet.append_rows([headings] + data, value_input_option="RAW")
            logging.info("Data successfully added to Google Sheets!")
            return "Data successfully added to Google Sheets!", data
        except Exception as e:
            logging.error(f"Error adding data to Google Sheets: {e}")
            return f"Error adding data to Google Sheets: {e}", []
    else:
        logging.warning("No data extracted to upload.")
        return "No data extracted to upload.", []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.form['url']
    result, data = scrape_and_upload(url)
    return render_template('result.html', result=result, data=data)

@app.route('/download')
def download():
    # Generate CSV file
    data = request.args.getlist('data')
    data = [eval(item) for item in data]  # Convert string representation of list back to list
    csv_file = 'scraped_data.csv'
    with open(csv_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Tag', 'Content'])
        writer.writerows(data)
    
    return send_file(csv_file, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
