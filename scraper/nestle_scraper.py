import json
import os
import time
from typing import Dict, List, Any
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('nestle_scraper')

def setup_driver() -> webdriver.Chrome:
    """Setup and return a Chrome webdriver with appropriate options."""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Initialize the Chrome driver
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        return driver
    except Exception as e:
        logger.error(f"Failed to setup Chrome driver: {e}")
        raise

def scrape_nestle_website() -> Dict[str, Any]:
    """
    Scrape content from the Nestlé website homepage.
    
    Returns:
        Dict containing structured data from the website
    """
    url = "https://www.madewithnestle.ca/"
    driver = None
    
    try:
        logger.info(f"Starting to scrape: {url}")
        driver = setup_driver()
        driver.get(url)
        
        # Wait for JavaScript to fully load
        logger.info("Waiting for page to load completely...")
        time.sleep(5)
        
        # Get the page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract all required content
        data = {
            "headings": [],
            "paragraphs": [],
            "links": [],
            "images": [],
            "tables": []
        }
        
        # Extract headings (h1, h2, h3, h4)
        for tag in ['h1', 'h2', 'h3', 'h4']:
            for element in soup.find_all(tag):
                if element.text.strip():
                    data["headings"].append({
                        "type": tag,
                        "text": element.text.strip()
                    })
        
        # Extract paragraphs
        for p in soup.find_all('p'):
            if p.text.strip():
                data["paragraphs"].append(p.text.strip())
        
        # Extract list items
        for li in soup.find_all('li'):
            if li.text.strip():
                data["paragraphs"].append(f"List item: {li.text.strip()}")
        
        # Extract links
        for a in soup.find_all('a'):
            href = a.get('href')
            text = a.text.strip()
            if href and text:
                # Make relative URLs absolute
                if href.startswith('/'):
                    href = f"{url.rstrip('/')}{href}"
                data["links"].append({
                    "text": text,
                    "href": href
                })
        
        # Extract images
        for img in soup.find_all('img'):
            alt = img.get('alt', '')
            src = img.get('src', '')
            if src:
                # Make relative URLs absolute
                if src.startswith('/'):
                    src = f"{url.rstrip('/')}{src}"
                data["images"].append({
                    "alt": alt,
                    "src": src
                })
        
        # Extract tables
        for table in soup.find_all('table'):
            table_data = {"headers": [], "rows": []}
            
            # Extract headers
            for th in table.find_all('th'):
                table_data["headers"].append(th.text.strip())
            
            # Extract rows
            for tr in table.find_all('tr'):
                row = []
                for td in tr.find_all('td'):
                    row.append(td.text.strip())
                if row:  # Only add non-empty rows
                    table_data["rows"].append(row)
            
            if table_data["headers"] or table_data["rows"]:
                data["tables"].append(table_data)
        
        logger.info("Scraping completed successfully")
        return data
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        return {
            "error": str(e),
            "headings": [],
            "paragraphs": [],
            "links": [],
            "images": [],
            "tables": []
        }
    finally:
        if driver:
            driver.quit()
            logger.info("Browser closed")

def save_to_json(data: Dict[str, Any], filename: str) -> None:
    """Save the scraped data to a JSON file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Data saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to save data to {filename}: {e}")

def main():
    """Main function to run the scraper."""
    try:
        output_file = "scraper/nestle_data.json"
        data = scrape_nestle_website()
        save_to_json(data, output_file)
        logger.info("Scraping process completed")
    except Exception as e:
        logger.error(f"An error occurred in the main process: {e}")

if __name__ == "__main__":
    main() 