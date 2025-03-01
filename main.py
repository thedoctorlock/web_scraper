#!/usr/bin/env python3
import json
import logging
import os
import sys
import time
from datetime import datetime
import shutil  # ADDED for environment checks

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Scraper pieces
from scraper import (
    ensure_logged_in,
    go_directly_to_connections,
    scrape_connections_table,
)
from redash_data import fetch_redash_csv, build_location_map
from data_filter import (
    filter_by_practice_groups,
    filter_auth_failed,
    exclude_websites,
    regroup_and_merge_locations,
)
from google_sheets import setup_google_sheets_client, upload_data_to_google_sheets
from location_helpers import process_location_field
from local_history import append_run_data

###################################################
# Use absolute paths for files/logs
###################################################
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "tuuthfairy_scraper.log")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

def load_config(path=CONFIG_PATH):
    with open(path, "r") as f:
        return json.load(f)

def check_cron_environment():
    """
    Warn if essential binaries are missing from PATH, which can happen in a minimal
    cron environment. Also log the current PATH so you can confirm it includes
    /usr/bin, /bin, or other directories needed by Chrome/ChromeDriver.
    """
    logger.info("Checking environment variables for cron usage...")
    # These utilities are typically used by Chrome startup scripts
    # If they're missing, Chrome might fail in a cron environment.
    essential_cmds = ["readlink", "dirname"]
    for cmd in essential_cmds:
        if shutil.which(cmd) is None:
            logger.warning(
                "Command '%s' not found in PATH. If running from cron, "
                "ensure /usr/bin (etc.) is in PATH to prevent Chrome startup issues.",
                cmd
            )

    path_env = os.getenv("PATH", "")
    logger.info("Current PATH environment variable: %s", path_env)

def load_practice_groups_from_sheet(
    service_account_file,
    spreadsheet_name,
    practice_list_tab="Tuuthfairy Groups"
):
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(service_account_file)
    scoped = creds.with_scopes([
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ])
    client = gspread.authorize(scoped)

    spreadsheet = client.open(spreadsheet_name)
    worksheet = spreadsheet.worksheet(practice_list_tab)

    # Grab column A (Status) and column B (Practice Group)
    status_col = worksheet.col_values(1)
    groups_col = worksheet.col_values(2)

    valid_practice_groups = []
    min_len = min(len(status_col), len(groups_col))
    # skip the header row (index 0)
    for i in range(1, min_len):
        status_value = status_col[i].strip()
        group_name = groups_col[i].strip()
        if status_value.lower() == "run":
            valid_practice_groups.append(group_name)

    return set(valid_practice_groups)

def _combine(scraped_record, loc_id, redash_info):
    """
    Combine a single scraped record with Redash practice group info for that location.
    """
    new_entry = {
        "ID": scraped_record["ID"],
        "WebsiteId": scraped_record["WebsiteId"],
        "Username": scraped_record["Username"],
        "Status": scraped_record["Status"],
        "locationId": loc_id or "",
        "LastUpdated": scraped_record["LastUpdated"],
    }
    if redash_info:
        new_entry["practiceGroupId"] = redash_info["practiceGroupId"]
        new_entry["practiceGroupName"] = redash_info["practiceGroupName"]
    else:
        new_entry["practiceGroupId"] = ""
        new_entry["practiceGroupName"] = ""
    return new_entry

def run_scraper_once(config):
    """
    Run the scraper steps exactly once.
    Raises exceptions on any failure so that main() can catch them.
    """
    logger.info("Starting single scraper run...")

    SERVICE_ACCOUNT_FILE = config["service_account_file"]
    SHEET_NAME = config["sheet_name"]
    AUTH0_EMAIL = config["auth0_email"]
    AUTH0_PASSWORD = config["auth0_password"]
    redash_url = config["redash_url"]
    api_key = config["redash_api_key"]

    # Example: exclude certain domains
    excluded_domains = {"unumdentalpwp.skygenusasystems.com"}

    # Load practice groups from Google Sheet
    valid_practice_groups = load_practice_groups_from_sheet(
        SERVICE_ACCOUNT_FILE,
        SHEET_NAME,
        practice_list_tab="Tuuthfairy Groups",
    )
    logger.info("Fetched practice groups: %s", valid_practice_groups)

    # Fetch & build location map from Redash
    redash_rows = fetch_redash_csv(redash_url, api_key=api_key)
    location_map = build_location_map(redash_rows)

    # Configure headless Chrome with recommended flags for cron
    options = Options()
    # Headless + no sandbox + disable dev shm usage for memory-limited or minimal env
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1280,720")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1280,720")
    options.binary_location = '/snap/bin/chromium'

    # Unique profile folder for each run (solves profile conflicts)
    unique_profile = f"/tmp/chrome-profile-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    options.add_argument(f"--user-data-dir={unique_profile}")

    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.77 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if sys.platform.startswith("darwin"):
        # === macOS ===
        # 1) ChromeDriver location (likely installed via Homebrew)
        chromedriver_path = "/usr/local/bin/chromedriver"

        # 2) Google Chrome binary location
        # If you definitely have Chrome installed here:
        options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

    elif sys.platform.startswith("linux"):
        # === Linux droplet ===
        # 1) ChromeDriver location
        chromedriver_path = "/usr/bin/chromedriver"

        # 2) Chromium browser binary installed from snap
        options.binary_location = "/snap/bin/chromium"

    else:
        # Windows or something else...
        # fill in as appropriate, or just raise an error
        raise RuntimeError("Unsupported platform for this script.")

    # Set up the ChromeDriver service
    service = Service(
        executable_path=chromedriver_path,
        service_args=["--verbose"],  # produce verbose chromedriver.log
        log_path="/tmp/chromedriver.log"
    )

    driver = webdriver.Chrome(service=service, options=options)
    try:
        # 1) Login via Auth0 with step-by-step waits and 2 retries if needed
        ensure_logged_in(driver, AUTH0_EMAIL, AUTH0_PASSWORD, max_retries=2)

        # 2) Go directly to /connection
        go_directly_to_connections(driver)

        # 3) Scrape all rows
        all_data = scrape_connections_table(driver)

        # 4) Process location fields
        for record in all_data:
            cleaned_locations = process_location_field(record["Locations"])
            record["Locations"] = cleaned_locations

        # Expand data: one row per location
        expanded_data = []
        for record in all_data:
            if not record["Locations"]:
                expanded_data.append(_combine(record, None, None))
                continue
            for loc_id in record["Locations"]:
                redash_info = location_map.get(loc_id, None)
                expanded_data.append(_combine(record, loc_id, redash_info))

        # 5) Filter and regroup
        filtered_data = filter_by_practice_groups(expanded_data, valid_practice_groups)
        auth_failed_data = filter_auth_failed(filtered_data)
        final_filtered_data = exclude_websites(auth_failed_data, excluded_domains)
        regrouped_data = regroup_and_merge_locations(final_filtered_data)

        # 6) Save a local CSV
        append_run_data(regrouped_data)

        # 7) Overwrite Google Sheets
        worksheet = setup_google_sheets_client(SERVICE_ACCOUNT_FILE, SHEET_NAME, "auth_failed")
        upload_data_to_google_sheets(worksheet, regrouped_data)

        logger.info("Single scraper run completed successfully!")
    finally:
        # Always quit the driver to free resources, preventing zombies
        driver.quit()

def main():
    logger.info("Launching script with retry mechanism...")

    # Check environment up front (especially helpful under cron)
    check_cron_environment()

    # Load config from absolute path
    config = load_config(CONFIG_PATH)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        logger.info("=== Scraper Attempt %d of %d ===", attempt, max_attempts)
        try:
            run_scraper_once(config)
            logger.info("Scraper attempt %d succeeded. Exiting retry loop.", attempt)
            break  # success, so stop trying
        except Exception as exc:
            logger.exception("Scraper attempt %d failed with error: %s", attempt, exc)
            if attempt < max_attempts:
                logger.info("Will retry in 60 seconds...")
                time.sleep(60)
            else:
                logger.error("Max retries reached. Aborting.")

if __name__ == "__main__":
    main()