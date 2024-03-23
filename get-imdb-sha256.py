import re
import time
from urllib.parse import unquote
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def get_sha256_from_network_tab(url, keyword):
    options = Options()
    # options.add_argument("--ignore-certificate-errors")  # Example of adding a header
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1600")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36")
    # options.add_argument("--user-agent=Your_Custom_User_Agent_String")
    # options.add_argument("--proxy-server=http://your-proxy-server:port")
    # options.add_argument("--disable-extensions")
    # options.add_argument("--disable-gpu")
    # options.add_argument("--incognito")
    # options.add_argument("--enable-logging")
    # options.add_argument("--v=0")
    # options.add_argument("--log-path=./chromedriver.log")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get(url)
        # print("Current URL:", driver.current_url)
        # Perform any necessary scrolling actions
        # driver.save_screenshot('./current_url.png')

        # Click on "Expand all" to reveal all advanced filter boxes
        expand_all_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//span[@class="ipc-btn__text" and text()="Expand all"]'))
        )
        # driver.save_screenshot('./before_click.png')
        expand_all_button.click()
        # driver.save_screenshot('./after_click.png')

        # Now, all advanced filter boxes should be visible, locate and interact with the search box
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//input[@aria-label="Title name"]'))
        )
        # Send the keyword to the search box
        search_box.send_keys(keyword)

        # Simulate pressing the Enter key
        # driver.save_screenshot('./before_click_shrek.png')
        search_box.send_keys(Keys.ENTER)
        # driver.save_screenshot('./after_click_shrek.png')

        # Click on the specified button
        movie_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//button[@data-testid="test-chip-id-movie"]'))
        )
        # driver.save_screenshot('./before_click_movie_button.png')
        movie_button.click()
        # driver.save_screenshot('./after_click_movie_button.png')

        # Wait for the search results to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h3.ipc-title__text'))
        )
        # print("Current URL after first search results found:", driver.current_url)

        # Get the network requests
        network_requests = driver.execute_script("return window.performance.getEntries();")
        # print("Number of network requests:", len(network_requests))  # Print the number of network requests
        for i, request in enumerate(network_requests, start=1):
            url = request.get("name")
            # print(f"Network request {i} URL:", url)  # Print the URL of each network request
            if "persistedQuery" in url and "sha256Hash" in url and "caching.graphql.imdb.com" in url and "Shrek" in url:
                # print(f"Network request {i} URL containing SHA-256 hash:", url)  # Print the URL before extraction
                # Decode the URL-encoded string before applying regex
                decoded_url = unquote(url)
                # print(f"Network request {i} URL containing SHA-256 hash (DECODED):", decoded_url)
                sha256_hash = re.search(r'sha256Hash":"([^"]+)', decoded_url).group(1)
                # print(f"Extracted SHA-256 hash:", sha256_hash)  # Print the extracted SHA-256 hash
                return sha256_hash

    finally:
        # Wait for a while before quitting to ensure all network requests are captured
        driver.quit()


if __name__ == "__main__":
    url = "https://www.imdb.com/search/title/"
    keyword = "Shrek"
    sha256_hash = get_sha256_from_network_tab(url, keyword)
    if sha256_hash:
        with open("HASHtest", "w") as f:
            f.write(sha256_hash)
        print("SHA-256 hash from network tab:", sha256_hash)
    else:
        print("Failed to retrieve SHA-256 hash.")
