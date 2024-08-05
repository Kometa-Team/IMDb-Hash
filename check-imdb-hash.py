import os, re, sys, time
from datetime import datetime, UTC
from urllib.parse import unquote

if sys.version_info[0] != 3 or sys.version_info[1] < 11:
    print("Version Error: Version: %s.%s.%s incompatible please use Python 3.11+" % (sys.version_info[0], sys.version_info[1], sys.version_info[2]))
    sys.exit(0)

try:
    from git import Repo
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
    from kometautils import KometaLogger, KometaArgs, YAML
except (ModuleNotFoundError, ImportError):
    print("Requirements Error: Requirements are not installed")
    sys.exit(0)

options = [
    {"arg": "k",  "key": "keyword",      "env": "KEYWORD",      "type": "str",  "default": None,  "help": "Use this Keyword for the run. (Default: Shrek)"},
    {"arg": "tr", "key": "trace",        "env": "TRACE",        "type": "bool", "default": False, "help": "Run with extra trace logs and screenshots."},
    {"arg": "lr", "key": "log-requests", "env": "LOG_REQUESTS", "type": "bool", "default": False, "help": "Run with every request logged."}
]
script_name = "IMDb Hash"
base_dir = os.path.dirname(os.path.abspath(__file__))
args = KometaArgs("Kometa-Team/IMDb-Hash", base_dir, options, use_nightly=False)
logger = KometaLogger(script_name, "imdb_hash", os.path.join(base_dir, "logs"), is_trace=args["trace"], log_requests=args["log-requests"])
logger.screen_width = 160
logger.header(args, sub=True)
logger.separator()
logger.start()
keyword = args["keyword"] if args["keyword"] else "Shrek"

folder = os.path.dirname(ChromeDriverManager().install())
logger.info(f"Files in {folder}")
for f in os.listdir(folder):
    logger.info(f"File: {f}")
logger.info("")
chrome_driver_path = os.path.join(folder, "chromedriver.exe")
logger.info(f"Keyword: {keyword}")
logger.info(f"Chrome Driver Path: {chrome_driver_path}")

service = Service(chrome_driver_path)

options = Options()
options.add_argument("--headless")
options.add_argument("--window-size=1920,1600")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36")

with webdriver.Chrome(service=service, options=options) as driver:
    logger.info(f"Chrome Browser Version: {driver.capabilities['browserVersion']}")
    logger.info(f"Chrome Driver Version: {driver.capabilities['chrome']['chromedriverVersion']}")

    def scan_for_hash(hash_type, special_text, filename):
        logger.info(f"Get Network Requests for {hash_type}")
        sha256hash = None
        network_requests = driver.execute_script("""
                var performanceEntries = [];
                var entries = window.performance.getEntries();
                if (entries && entries.length > 0) {
                    for (var i = 0; i < entries.length; i++) {
                        var entry = entries[i];
                        var url = entry.name || entry.initiatorType;
                        if (url) {
                            performanceEntries.push(url);
                        }
                    }
                }
                return performanceEntries;
            """)
        if network_requests:
            target_strings = ["persistedQuery", "sha256Hash", "caching.graphql.imdb.com", special_text]

            logger.info(f"Number of network requests: {len(network_requests)}")  # Print the number of network requests
            for i, request in enumerate(network_requests, start=1):
                if all(target_string in request for target_string in target_strings):
                    logger.info(f"Encoded SHA-256 {hash_type} Hash URL: {request}")
                    decoded_url = unquote(request)
                    logger.info(f"Decoded SHA-256 {hash_type} Hash URL: {decoded_url}")
                    sha256hash = re.search(r'sha256Hash":"([^"]+)', decoded_url).group(1)
                    break

        if sha256hash:
            with open(filename, "w") as fa:
                fa.write(sha256hash)
            logger.info(f"Extracted SHA-256 {hash_type} Hash: {sha256hash}")
        else:
            logger.info(f"Failed to retrieve SHA-256 {hash_type} Hash.")

    logger.info("Get URL: https://www.imdb.com/search/title/")
    driver.get("https://www.imdb.com/search/title/")
    time.sleep(5)
    if args["trace"]:
        driver.save_screenshot('./logs/01_current_url.png')

    logger.info("Get Expand All Button")
    expand_all_button = WebDriverWait(driver, 10).until(expected_conditions.element_to_be_clickable((By.XPATH, '//span[@class="ipc-btn__text" and text()="Expand all"]')))
    expand_all_button.click()
    if args["trace"]:
        driver.save_screenshot('./logs/02_after_expand_all_click.png')

    logger.info(f"Send Keyword: {keyword}")
    search_box = WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, '//input[@aria-label="Title name"]')))
    search_box.send_keys(keyword)
    if args["trace"]:
        driver.save_screenshot('./logs/03_after_sending_keyword.png')

    logger.info("Click Movie Button")
    movie_button = WebDriverWait(driver, 10).until(expected_conditions.element_to_be_clickable((By.XPATH, '//button[@data-testid="test-chip-id-movie"]')))
    movie_button.click()
    if args["trace"]:
        driver.save_screenshot('./logs/04_after_movie_button_click.png')

    search_box.send_keys(Keys.ENTER)
    time.sleep(5)

    logger.info("Get Search Results")
    WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.CSS_SELECTOR, 'h3.ipc-title__text')))
    if args["trace"]:
        driver.save_screenshot('./logs/05_after_search_results_found.png')

    scan_for_hash("Search", keyword, "HASH")

    logger.info("Get URL: https://www.imdb.com/list/ls005526372/")
    driver.get("https://www.imdb.com/list/ls005526372/")
    time.sleep(5)
    if args["trace"]:
        driver.save_screenshot('./logs/06_list_url.png')

    html = driver.find_element(By.TAG_NAME, 'html')
    for _ in range(30):
        html.send_keys(Keys.PAGE_DOWN)
    if args["trace"]:
        driver.save_screenshot('./logs/07_list_page_down_placement.png')

    scan_for_hash("List", "operationName=TitleListMainPage", "LIST_HASH")

    logger.info("Get URL: https://www.imdb.com/user/ur51920649/watchlist/")
    driver.get("https://www.imdb.com/user/ur51920649/watchlist/")
    time.sleep(5)
    if args["trace"]:
        driver.save_screenshot('./logs/08_watchlist_url.png')

    html = driver.find_element(By.TAG_NAME, 'html')
    for _ in range(30):
        html.send_keys(Keys.PAGE_DOWN)
    if args["trace"]:
        driver.save_screenshot('./logs/09_watchlist_page_down_placement.png')

    scan_for_hash("Watchlist", "operationName=WatchListPageRefiner", "WATCHLIST_HASH")

if [item.a_path for item in Repo(path=".").index.diff(None) if item.a_path.endswith("HASH")]:

    with open("README.md", "r", encoding="utf-8") as f:
        readme_data = f.readlines()

    readme_data[2] = f"Last generated at: {datetime.now(UTC).strftime('%B %d, %Y %H:%M')} UTC\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.writelines(readme_data)

logger.separator(f"{script_name} Finished\nTotal Runtime: {logger.runtime()}")