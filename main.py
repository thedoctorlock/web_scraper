# main.py

import json
import logging
from datetime import datetime
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from scraper import ensure_logged_in, click_connections_link, scrape_connections_table
from redash_data import fetch_redash_csv, build_location_map
from data_filter import (
    filter_by_practice_groups,
    filter_auth_failed,
    exclude_websites,
    regroup_and_merge_locations
)
from google_sheets import setup_google_sheets_client, upload_data_to_google_sheets
from location_helpers import process_location_field

# Configure logging
logging.basicConfig(
    filename="tuuthfairy_scraper.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

def load_practice_groups_from_sheet(
    service_account_file, 
    spreadsheet_name, 
    practice_list_tab="Tuuthfairy Groups"
):
    """
    Reads Column A ("Status") and Column B ("Practice Group") from 'Tuuthfairy Groups'.
    Skips the header row (row 1).
    Returns a set of group names from rows where Status == "Run".
    """
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
    status_col = worksheet.col_values(1)  # A
    groups_col = worksheet.col_values(2)  # B

    valid_practice_groups = []
    min_len = min(len(status_col), len(groups_col))

    # Skip header row (index 0)
    for i in range(1, min_len):
        status_value = status_col[i].strip()
        group_name = groups_col[i].strip()
        if status_value.lower() == "run":
            valid_practice_groups.append(group_name)

    return set(valid_practice_groups)

def load_config(config_path="config.json"):
    with open(config_path, "r") as f:
        return json.load(f)

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
    config = load_config("config.json")

    SERVICE_ACCOUNT_FILE = config["service_account_file"]
    SHEET_NAME = config["sheet_name"]          # The name of the Google Spreadsheet
    AUTH0_EMAIL = config["auth0_email"]
    AUTH0_PASSWORD = config["auth0_password"]
    
    redash_url = config["redash_url"]
    api_key = config["redash_api_key"]

    # Websites we want to exclude, if any
    excluded_domains = {"unumdentalpwp.skygenusasystems.com"}

    # Load practice groups from 'Tuuthfairy Groups' sheet, but only for rows marked "Run"
    valid_practice_groups = load_practice_groups_from_sheet(
        SERVICE_ACCOUNT_FILE, 
        SHEET_NAME, 
        practice_list_tab="Tuuthfairy Groups"
    )
    logger.info("Fetched practice groups from 'Tuuthfairy Groups' where Status=Run: %s", valid_practice_groups)

    # Fetch Redash CSV, build location -> practice group map
    redash_rows = fetch_redash_csv(redash_url, api_key=api_key)
    location_map = build_location_map(redash_rows)

    # Configure Chrome in 'stealth' headless mode
    options = Options()
    options.add_argument("--headless=new")  # For Chrome 109+ 
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.77 Safari/537.36"
    )
    # Hide the "Chrome is being controlled by automated test software" banner 
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)

    try:
        # Login and navigate
        ensure_logged_in(driver, AUTH0_EMAIL, AUTH0_PASSWORD)
        click_connections_link(driver)

        # Scrape data
        all_data = scrape_connections_table(driver)

        # Clean location fields
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

        # 1) Filter by practice group
        filtered_data = filter_by_practice_groups(expanded_data, valid_practice_groups)

        # 2) Filter by Status == 'auth_failed'
        auth_failed_data = filter_auth_failed(filtered_data)

        # 3) Exclude any unwanted websites
        final_filtered_data = exclude_websites(auth_failed_data, excluded_domains)

        # 4) Group multiple locationIds into a single row for each ID
        regrouped_data = regroup_and_merge_locations(final_filtered_data)

        # Upload to Google Sheets (auth_failed tab)
        worksheet = setup_google_sheets_client(SERVICE_ACCOUNT_FILE, SHEET_NAME, worksheet_name="auth_failed")
        upload_data_to_google_sheets(worksheet, regrouped_data)

        logger.info("Done!")
    except Exception:
        # Save screenshot & page source for debugging
        screenshot_path = os.path.join(os.getcwd(), "headless_timeout.png")
        driver.save_screenshot(screenshot_path)
        logger.info("Saved screenshot to %s", screenshot_path)

        html_path = os.path.join(os.getcwd(), "headless_timeout.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("Saved page source to %s", html_path)

        logger.exception("An error occurred during main execution.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()