import json, os, re, sys, time
from datetime import datetime, UTC
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
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
    {"arg": "k",  "key": "keyword",      "env": "KEYWORD",      "type": "str",  "default": None,  "help": "Use this Keyword for the run. (Default: Pandora and the Flying Dutchman)"},
    {"arg": "tr", "key": "trace",        "env": "TRACE",        "type": "bool", "default": False, "help": "Run with extra trace logs and screenshots."},
    {"arg": "lr", "key": "log-requests", "env": "LOG_REQUESTS", "type": "bool", "default": False, "help": "Run with every request logged."},
    {"arg": "r",  "key": "refresh",      "env": "REFRESH",      "type": "bool", "default": False, "help": "Refresh hashes in an interactive browser instead of only validating them."}
]
script_name = "IMDb Hash"
base_dir = os.path.dirname(os.path.abspath(__file__))
args = KometaArgs("Kometa-Team/IMDb-Hash", base_dir, options, use_nightly=False)
logger = KometaLogger(script_name, "imdb_hash", os.path.join(base_dir, "logs"), is_trace=args["trace"], log_requests=args["log-requests"])
logger.screen_width = 160
logger.header(args, sub=True)
logger.separator()
logger.start()
keyword = args["keyword"] if args["keyword"] else "Pandora and the Flying Dutchman"

hash_checks = [
    ("Search", "AdvancedTitleSearch", "HASH", {
        "first": 50, "locale": "en-US", "sortBy": "POPULARITY", "sortOrder": "ASC",
        "titleTextConstraint": {"searchTerm": keyword}
    }),
    ("List", "TitleListMainPage", "LIST_HASH", {
        "first": 250, "jumpToPosition": 251, "locale": "en-US", "lsConst": "ls005526372",
        "sort": {"by": "LIST_ORDER", "order": "ASC"}
    }),
    ("Watchlist", "WatchListPageRefiner", "WATCHLIST_HASH", {
        "first": 250, "jumpToPosition": 251, "locale": "en-US",
        "sort": {"by": "LIST_ORDER", "order": "ASC"}, "urConst": "ur51920649"
    })
]


class IMDbError(Exception):
    pass


def decode_imdb_response(response, status=None):
    response_body = response.read()
    response_status = status if status is not None else response.status
    content_type = response.headers.get_content_type()

    if response_status >= 400:
        detail = response.reason
        if content_type == "application/json":
            try:
                error_data = json.loads(response_body)
                detail = error_data.get("message") or error_data.get("errors") or detail
            except json.JSONDecodeError:
                pass
        raise IMDbError(f"HTTP {response_status} {detail} ({content_type})")

    try:
        return json.loads(response_body)
    except json.JSONDecodeError as error:
        raise IMDbError(
            f"Expected a JSON response but received {content_type} "
            f"(HTTP {response_status}): {error}"
        ) from error


def validate_hash(hash_type, operation_name, filename, variables):
    logger.info(f"Validate {hash_type} Hash")
    try:
        with open(os.path.join(base_dir, filename), encoding="utf-8") as hash_file:
            sha256_hash = hash_file.read().strip()
        query = urlencode({
            "operationName": operation_name,
            "variables": json.dumps(variables, separators=(",", ":")),
            "extensions": json.dumps(
                {"persistedQuery": {"sha256Hash": sha256_hash, "version": 1}},
                separators=(",", ":")
            )
        })
        request = Request(
            f"https://caching.graphql.imdb.com/?{query}",
            headers={
                "Content-Type": "application/json",
                "Origin": "https://www.imdb.com",
                "User-Agent": "IMDb-Hash/1.0",
                "X-Imdb-Client-Name": "imdb-web-next"
            }
        )
        try:
            with urlopen(request, timeout=30) as response:
                response_data = decode_imdb_response(response)
        except HTTPError as error:
            response_data = decode_imdb_response(error, status=error.code)
        errors = response_data.get("errors", [])
        invalid = any(
            error.get("extensions", {}).get("code") == "PERSISTED_QUERY_NOT_FOUND"
            or "PersistedQueryNotFound" in error.get("message", "")
            for error in errors
        )
        if invalid:
            logger.error(f"{hash_type} Hash is no longer registered by IMDb.")
            return False
        logger.info(f"{hash_type} Hash is valid: {sha256_hash}")
        return True
    except IMDbError as error:
        logger.error(f"IMDb Error: Unable to validate {hash_type} Hash: {error}")
        return False
    except (FileNotFoundError, TimeoutError, URLError) as error:
        logger.error(f"Unable to validate {hash_type} Hash: {error}")
        return False


logger.separator("IMDb Persisted Query Validation")
invalid_hashes = [
    hash_type for hash_type, operation_name, filename, variables in hash_checks
    if not validate_hash(hash_type, operation_name, filename, variables)
]

if not args["refresh"]:
    logger.separator(f"{script_name} Finished\nTotal Runtime: {logger.runtime()}")
    if invalid_hashes:
        plural = "es" if len(invalid_hashes) > 1 else ""
        sys.exit(
            f"Invalid or unverifiable {' and '.join(invalid_hashes)} Hash{plural}. "
            "Run check-imdb-hash.py --refresh locally to regenerate."
        )
    sys.exit(0)

folder = os.path.dirname(ChromeDriverManager().install())
chrome_driver_path = os.path.join(folder, next((f for f in os.listdir(folder) if not f.endswith(".chromedriver"))))
logger.info(f"Keyword: {keyword}")
logger.info(f"Chrome Driver Path: {chrome_driver_path}")
os.chmod(chrome_driver_path, 0o755)
service = Service(chrome_driver_path)

options = Options()
if os.environ.get("CI"):
    options.add_argument("--headless")
options.add_argument("--window-size=1920,1600")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

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
    enter(search, "Get Search Results", "after_search_results_found")
    scan_for_hash("Search", "operationName=AdvancedTitleSearch", "HASH")

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
