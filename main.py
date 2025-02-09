# main.py

import json
from selenium import webdriver

# (1) Import your existing helpers
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
    print("Launching script...")
    config = load_config("config.json")

    # Make sure these keys match your config.json
    SERVICE_ACCOUNT_FILE = config["service_account_file"]
    SHEET_NAME = config["sheet_name"]
    AUTH0_EMAIL = config["auth0_email"]
    AUTH0_PASSWORD = config["auth0_password"]
    
    # Ensure you have "redash_url" and "redash_api_key" in your config
    redash_url = config["redash_url"]
    api_key = config["redash_api_key"]

    # Load valid practice groups from config
    valid_practice_groups = set(config.get("valid_practice_groups", []))

    # If you have a list of websites to exclude, you can keep it in config.json, e.g.:
    # { "excluded_websites": ["unumdentalpwp.skygenusasystems.com"] }
    # or just define inline:
    excluded_domains = {"unumdentalpwp.skygenusasystems.com"}

    # Fetch Redash CSV and build location -> practice group map
    redash_rows = fetch_redash_csv(redash_url, api_key=api_key)
    location_map = build_location_map(redash_rows)

    driver = webdriver.Chrome()
    try:
        # Login to the dashboard
        ensure_logged_in(driver, AUTH0_EMAIL, AUTH0_PASSWORD)

        # Navigate to connections
        click_connections_link(driver)

        # Scrape data
        all_data = scrape_connections_table(driver)

        # Clean the location fields (split, remove 'airpay_', etc.)
        for record in all_data:
            cleaned_locations = process_location_field(record["Locations"])
            record["Locations"] = cleaned_locations

        # Expand data: one row per location
        expanded_data = []
        for record in all_data:
            if not record["Locations"]:
                # If no locations, still create a row with empty location & practice group
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
        #    e.g. 'unumdentalpwp.skygenusasystems.com'
        final_filtered_data = exclude_websites(auth_failed_data, excluded_domains)

        # 4) Group multiple locationIds into a single row for each ID
        regrouped_data = regroup_and_merge_locations(final_filtered_data)

        # Upload to Google Sheets
        worksheet = setup_google_sheets_client(SERVICE_ACCOUNT_FILE, SHEET_NAME)
        upload_data_to_google_sheets(worksheet, regrouped_data)
        print("Done!")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()