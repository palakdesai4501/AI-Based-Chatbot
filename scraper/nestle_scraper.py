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

def simulate_human_behavior(driver):
    """Simulate human-like scrolling behavior."""
    # Random scrolling to simulate human behavior
    for i in range(3):
        scroll_amount = random.randint(300, 700)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 1.5))
    
    # Scroll back up
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(random.uniform(0.5, 1))

def extract_page_content(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """
    Extract content from a page.
    
    Args:
        soup: BeautifulSoup object of the page
        url: Source URL of the page
    
    Returns:
        Dict containing structured data from the page
    """
        # Extract all required content
    data = {
            "headings": [],
            "paragraphs": [],
        "list_items": [],
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
                    "text": element.text.strip(),
                    "source_page": url
                    })
        
        # Extract paragraphs
    for p in soup.find_all('p'):
        if p.text.strip():
            data["paragraphs"].append({
                "text": p.text.strip(),
                "source_page": url
            })
        
        # Extract list items
    for li in soup.find_all('li'):
        if li.text.strip():
            data["list_items"].append({
                "text": li.text.strip(),
                "source_page": url
            })
        
        # Extract links
        for a in soup.find_all('a'):
            href = a.get('href')
            text = a.text.strip()
            if href and text:
                # Make relative URLs absolute
                if href.startswith('/'):
                    href = f"https://www.madewithnestle.ca{href}"
                data["links"].append({
                    "text": text,
                "href": href,
                "source_page": url
                })
        
        # Extract images
        for img in soup.find_all('img'):
            alt = img.get('alt', '')
            src = img.get('src', '')
            if src:
                # Make relative URLs absolute
                if src.startswith('/'):
                    src = f"https://www.madewithnestle.ca{src}"
                data["images"].append({
                    "alt": alt,
                "src": src,
                "source_page": url
                })
        
        # Extract tables
        for table in soup.find_all('table'):
            table_data = {"headers": [], "rows": [], "source_page": url}
            
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
        
        return data

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

def scrape_nestle_website() -> Dict[str, Any]:
    """
    Scrape content from the Nestlé website homepage and all internal links.
    
    Returns:
        Dict containing structured data from all pages
    """
    base_url = "https://www.madewithnestle.ca"
    driver = None
    
    try:
        logger.info(f"Starting to scrape: {base_url}")
        driver = setup_driver()
        
        # Combined data from all pages
        combined_data = {
            "headings": [],
            "paragraphs": [],
            "list_items": [],
            "links": [],
            "images": [],
            "tables": []
        }
        
        # First get all internal links from the homepage
        logger.info("Visiting homepage to extract internal links...")
        driver.get(base_url)
        
        # Wait for JavaScript to fully load
        logger.info("Waiting for page to load completely...")
        time.sleep(10)  # Extended initial wait time
        
        # Simulate human behavior to bypass detection
        logger.info("Simulating human behavior...")
        simulate_human_behavior(driver)
        
        # Parse the homepage
        homepage_soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract homepage content
        logger.info("Extracting homepage content...")
        homepage_data = extract_page_content(homepage_soup, base_url)
        
        # Add homepage data to combined data
        for key in combined_data.keys():
            combined_data[key].extend(homepage_data[key])
        
        # Extract internal links to visit
        internal_links = extract_internal_links(homepage_soup, base_url)
        visited_links = {base_url}  # Mark homepage as visited
        
        # Visit each internal link
        for link in internal_links:
            if link in visited_links:
                continue
                
            logger.info(f"Visiting: {link}")
            try:
                driver.get(link)
                time.sleep(1)  # Sleep to avoid rate limiting
                
                # Simulate human behavior
                simulate_human_behavior(driver)
                
                # Parse the page
                page_soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Extract content
                page_data = extract_page_content(page_soup, link)
                
                # Add page data to combined data
                for key in combined_data.keys():
                    combined_data[key].extend(page_data[key])
                    
                # Mark as visited
                visited_links.add(link)
                
                logger.info(f"Successfully scraped: {link}")
            except Exception as e:
                logger.error(f"Error scraping {link}: {e}")
            
            # Add a delay between page visits
            time.sleep(1)
        
        logger.info(f"Scraping completed. Visited {len(visited_links)} pages.")
        return combined_data
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        return {
            "error": str(e),
            "headings": [],
            "paragraphs": [],
            "list_items": [],
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
        output_file = "scraper/nestle_full_data.json"
        data = scrape_nestle_website()
        save_to_json(data, output_file)
        logger.info("Scraping process completed")
    except Exception as e:
        logger.error(f"An error occurred in the main process: {e}")

if __name__ == "__main__":
    main() 