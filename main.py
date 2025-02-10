#!/usr/bin/env python3
import json
import logging
import os
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

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
    # skip header row 0
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

def main():
    logger.info("Launching script...")

    # Load config from absolute path
    config = load_config(CONFIG_PATH)
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

    # Configure headless Chrome
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Optional user-agent + hide automation banners
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.77 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)

    try:
        # 1) Login via Auth0
        ensure_logged_in(driver, AUTH0_EMAIL, AUTH0_PASSWORD)

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

        logger.info("Done!")
    except Exception:
        import traceback
        # If something breaks, store screenshot & HTML in the same folder as main.py
        screenshot_path = os.path.join(BASE_DIR, "headless_timeout.png")
        driver.save_screenshot(screenshot_path)
        logger.info("Saved screenshot to %s", screenshot_path)

        html_path = os.path.join(BASE_DIR, "headless_timeout.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("Saved page source to %s", html_path)

        logger.exception("An error occurred during main execution.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()