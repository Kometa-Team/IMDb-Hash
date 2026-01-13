import os, re, sys, time
from datetime import datetime, UTC
from urllib.parse import unquote
from urllib3.exceptions import ReadTimeoutError

if sys.version_info[0] != 3 or sys.version_info[1] < 11:
    print("Version Error: Version: %s.%s.%s incompatible please use Python 3.11+" % (sys.version_info[0], sys.version_info[1], sys.version_info[2]))
    sys.exit(0)

try:
    from git import Repo
    from selenium import webdriver
    from selenium.common import ElementClickInterceptedException
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
chrome_driver_path = os.path.join(folder, next((f for f in os.listdir(folder) if not f.endswith(".chromedriver"))))
logger.info(f"Keyword: {keyword}")
logger.info(f"Chrome Driver Path: {chrome_driver_path}")
os.chmod(chrome_driver_path, 0o755)
service = Service(chrome_driver_path)

options = Options()
options.add_argument("--headless")
options.add_argument("--window-size=1920,1600")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36")

failed = []

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
                    logger.info(f"Encoded SHA-256 Hash URL: {request}")
                    decoded_url = unquote(request)
                    logger.info(f"Decoded SHA-256 Hash URL: {decoded_url}")
                    sha256hash = re.search(r'sha256Hash":"([^"]+)', decoded_url).group(1)
                    break
                elif "graphql" in request and args["trace"]:
                    logger.info(f"GraphQL Request: {request}")

        if sha256hash:
            with open(filename, "w") as fa:
                fa.write(sha256hash)
            logger.info(f"Extracted SHA-256 {hash_type} Hash: {sha256hash}")
        else:
            logger.info(f"Failed to retrieve SHA-256 {hash_type} Hash.")
            failed.append(hash_type)

    screenshot_count = 0

    def screenshot_and_wait(screen, sleep=20):
        if sleep:
            time.sleep(sleep)
        global screenshot_count
        screenshot_count += 1
        if args["trace"]:
            driver.save_screenshot(f"./logs/{screenshot_count:02}_{screen}.png")

    def page_get(title, url, screen, count=0):
        try:
            logger.separator(title)
            logger.info(f"Get URL: {url}")
            driver.get(url)
            screenshot_and_wait(screen)
        except ReadTimeoutError:
            screenshot_and_wait(f"{screen}.{count}")
            if count < 20:
                page_get(title, url, screen, count=count + 1)

    def click(title, xpath, screen, count=0):
        try:
            logger.info(f"{title}{f' attempt {count + 1}' if count else ''}")
            _button = WebDriverWait(driver, 10).until(expected_conditions.element_to_be_clickable((By.XPATH, xpath)))
            _button.click()
            screenshot_and_wait(screen)
        except ElementClickInterceptedException:
            screenshot_and_wait(f"{screen}.{count}")
            if count < 20:
                click(title, xpath, screen, count=count + 1)

    def textbox(title, xpath, screen):
        logger.info(title)
        _box = WebDriverWait(driver, 10).until(expected_conditions.presence_of_element_located((By.XPATH, xpath)))
        _box.send_keys(keyword)
        screenshot_and_wait(screen)
        return _box

    def enter(_box, title, screen):
        logger.info(title)
        _box.send_keys(Keys.ENTER)
        screenshot_and_wait(screen)

    def page_end(screen, title="Page End"):
        logger.info(title)
        html = driver.find_element(By.TAG_NAME, "html")
        html.send_keys(Keys.END)
        screenshot_and_wait(screen)

    page_get("IMDb Search Hash", "https://www.imdb.com/search/title/", "search_url")
    click("Get Expand All Button", '//span[@class="ipc-btn__text" and text()="Expand all"]', "after_expand_all_click")
    search = textbox(f"Send Keyword: {keyword}", '//input[@aria-label="Title name"]', "after_sending_keyword")
    click("Click Movie Button", "//button[@data-testid='test-chip-id-movie']", "after_movie_button_click")
    enter(search, "Get Search Results", "after_search_results_found")
    scan_for_hash("Search", keyword, "HASH")

    page_get("IMDb List Hash", "https://www.imdb.com/list/ls005526372/", "list_url")
    page_end("after_list_page_end")
    click("Page 2", '//button[@data-testid="index-pagination-nxt"]', "after_list_page_2")
    scan_for_hash("List", "operationName=TitleListMainPage", "LIST_HASH")

    page_get("IMDb Watchlist Hash", "https://www.imdb.com/user/ur51920649/watchlist/", "watchlist_url")
    page_end("after_watchlist_page_end")
    click("Page 2", '//button[@data-testid="index-pagination-nxt"]', "after_watchlist_page_2")
    scan_for_hash("Watchlist", "operationName=WatchListPageRefiner", "WATCHLIST_HASH")

if [item.a_path for item in Repo(path=".").index.diff(None) if item.a_path.endswith("HASH")]:

    with open("README.md", "r", encoding="utf-8") as f:
        readme_data = f.readlines()

    readme_data[2] = f"Last generated at: {datetime.now(UTC).strftime('%B %d, %Y %H:%M')} UTC\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.writelines(readme_data)

logger.separator(f"{script_name} Finished\nTotal Runtime: {logger.runtime()}")

if failed:
    hashes = f"{' and '.join(failed if len(failed) < 3 else [f"{', '.join(failed[:-1])},", failed[-1]])}"
    sys.exit(f"Failed to Find {hashes} Hash{'s' if failed > 1 else ''}")
