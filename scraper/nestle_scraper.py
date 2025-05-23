import json
import os
import time
import random
from typing import Dict, List, Any, Set
import logging
import re

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('nestle_scraper')

def setup_driver():
    """Setup and return an undetected Chrome webdriver to bypass detection."""
    try:
        options = uc.ChromeOptions()
        # Don't use headless mode as it's more easily detected
        # options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Add user agent to appear more like a real browser
        options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
        
        # Additional options to make the browser more realistic
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        
        # Initialize the undetected Chrome driver with a specific version
        driver = uc.Chrome(options=options)
        
        # Set window size to appear like a real browser
        driver.set_window_size(1920, 1080)
        
        return driver
    except Exception as e:
        logger.error(f"Failed to setup undetected Chrome driver: {e}")
        raise

def scroll_to_bottom(driver, pause_time=1.0, max_attempts=30):
    """
    Scrolls to the bottom of the page, waiting for new content to load.
    Stops if no new content is loaded after several attempts.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0
    while attempts < max_attempts:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            attempts += 1
            if attempts >= 3:  # Try 3 more times after no change
                break
        else:
            attempts = 0
            last_height = new_height

def extract_page_block(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """
    Extract all content from a page and group it as a single block.
    """
    block = {
        "url": url,
        "headings": [],
        "paragraphs": [],
        "list_items": [],
        "links": [],
        "images": [],
        "tables": []
    }
    # Headings
    for tag in ['h1', 'h2', 'h3', 'h4']:
        for element in soup.find_all(tag):
            if element.text.strip():
                block["headings"].append({
                    "type": tag,
                    "text": element.text.strip()
                })
    # Paragraphs
    for p in soup.find_all('p'):
        if p.text.strip():
            block["paragraphs"].append(p.text.strip())
    # List items
    for li in soup.find_all('li'):
        if li.text.strip():
            block["list_items"].append(li.text.strip())
    # Links
    for a in soup.find_all('a'):
        href = a.get('href')
        text = a.text.strip()
        if href and text:
            if href.startswith('/'):
                href = f"https://www.madewithnestle.ca{href}"
            block["links"].append({
                "text": text,
                "href": href
            })
    # Images
    for img in soup.find_all('img'):
        alt = img.get('alt', '')
        src = img.get('src', '')
        if src:
            if src.startswith('/'):
                src = f"https://www.madewithnestle.ca{src}"
            block["images"].append({
                "alt": alt,
                "src": src
            })
    # Tables
    for table in soup.find_all('table'):
        table_data = {"headers": [], "rows": []}
        for th in table.find_all('th'):
            table_data["headers"].append(th.text.strip())
        for tr in table.find_all('tr'):
            row = []
            for td in tr.find_all('td'):
                row.append(td.text.strip())
            if row:
                table_data["rows"].append(row)
        if table_data["headers"] or table_data["rows"]:
            block["tables"].append(table_data)
    return block

def extract_internal_links(soup: BeautifulSoup, base_url: str) -> Set[str]:
    """
    Extract all internal links from a page.
    
    Args:
        soup: BeautifulSoup object of the page
        base_url: Base URL of the site
        
    Returns:
        Set of internal URLs
    """
    internal_links = set()
    
    for a in soup.find_all('a'):
        href = a.get('href')
        
        if not href:
            continue
            
        # Skip javascript links
        if 'javascript:void' in href:
            continue
            
        # Make relative URLs absolute
        if href.startswith('/'):
            href = f"{base_url.rstrip('/')}{href}"
            
        # Only include links to the same domain
        if href.startswith(base_url):
            internal_links.add(href)
    
    logger.info(f"Extracted {len(internal_links)} unique internal links")
    return internal_links

def scrape_nestle_website() -> List[Dict[str, Any]]:
    """
    Scrape content from the Nestlé website homepage and all internal links.
    Returns a list of page blocks.
    """
    base_url = "https://www.madewithnestle.ca"
    driver = None
    try:
        logger.info(f"Starting to scrape: {base_url}")
        driver = setup_driver()
        page_blocks = []

        # Visit homepage
        logger.info("Visiting homepage to extract internal links...")
        driver.get(base_url)
        time.sleep(10)
        logger.info("Scrolling to bottom of homepage...")
        scroll_to_bottom(driver)
        homepage_soup = BeautifulSoup(driver.page_source, 'html.parser')
        logger.info("Extracting homepage content...")
        homepage_block = extract_page_block(homepage_soup, base_url)
        page_blocks.append(homepage_block)

        # Extract internal links
        internal_links = extract_internal_links(homepage_soup, base_url)
        visited_links = {base_url}

        # Visit each internal link
        for link in internal_links:
            if link in visited_links:
                continue
            logger.info(f"Visiting: {link}")
            try:
                driver.get(link)
                time.sleep(2)
                logger.info("Scrolling to bottom of page...")
                scroll_to_bottom(driver)
                page_soup = BeautifulSoup(driver.page_source, 'html.parser')
                page_block = extract_page_block(page_soup, link)
                page_blocks.append(page_block)
                visited_links.add(link)
                logger.info(f"Successfully scraped: {link}")
            except Exception as e:
                logger.error(f"Error scraping {link}: {e}")
            time.sleep(1)
        logger.info(f"Scraping completed. Visited {len(visited_links)} pages.")
        return page_blocks
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        return []
    finally:
        if driver:
            driver.quit()
            logger.info("Browser closed")

def save_to_json(data: List[Dict[str, Any]], filename: str) -> None:
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
        output_file = "scraper/nestle_full_data.json"
        data = scrape_nestle_website()
        save_to_json(data, output_file)
        logger.info("Scraping process completed")
    except Exception as e:
        logger.error(f"An error occurred in the main process: {e}")

if __name__ == "__main__":
    main() 