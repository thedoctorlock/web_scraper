#!/usr/bin/env python3

import time
import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import gspread
from google.oauth2.service_account import Credentials


def load_config(path="config.json"):
    """Load configuration (Auth0 creds, Google Sheets info) from a JSON file."""
    with open(path, "r") as f:
        return json.load(f)

def setup_google_sheets_client(service_account_file, sheet_name):
    creds = Credentials.from_service_account_file(service_account_file)
    scoped = creds.with_scopes([
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ])
    client = gspread.authorize(scoped)

    spreadsheet = client.open(sheet_name)
    worksheet = spreadsheet.sheet1
    return worksheet

def ensure_logged_in(driver, auth0_email, auth0_password):
    """
    1) Load /auth/login, which redirects to Auth0.
    2) If we see #username, fill credentials and submit.
       (Either on the main page or inside an iframe.)
    3) Wait until we're back to 'dashboard.tuuthfairy.com' (meaning login succeeded).
    """
    driver.get("https://dashboard.tuuthfairy.com/auth/login")
    time.sleep(5)  # let it redirect or load

    print("DEBUG: after hitting /auth/login, current URL =", driver.current_url)

    found_login_form = False

    # Check for #username on the main page
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#username"))
        )
        print("Found input#username on main page (no iframe).")
        found_login_form = True
    except:
        print("No direct #username found on main page; checking for iframe...")

        # Maybe it's in an iframe
        try:
            WebDriverWait(driver, 5).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe"))
            )
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#username"))
            )
            print("Found #username in iframe.")
            found_login_form = True
        except:
            print("No #username found, possibly already logged in.")
            pass

    if found_login_form:
        email_input = driver.find_element(By.CSS_SELECTOR, "input#username")
        email_input.clear()
        email_input.send_keys(auth0_email)

        password_input = driver.find_element(By.CSS_SELECTOR, "input#password")
        password_input.clear()
        password_input.send_keys(auth0_password)

        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_btn.click()

        # If we switched into an iframe, switch out
        try:
            driver.switch_to.default_content()
        except:
            pass

        # Wait until the URL indicates we're back on dashboard.tuuthfairy.com
        WebDriverWait(driver, 60).until(
            lambda d: "dashboard.tuuthfairy.com" in d.current_url
        )
        print("Redirected back to dashboard.tuuthfairy.com after login.")

    else:
        # If we didn't find a login form, we assume we're already logged in
        pass


def click_connections_link(driver):
    """
    In the left sidebar, there's presumably a link or anchor for 'Connections'.
    Let's click it, just like you'd do manually.
    """
    # 1) Wait until the link is clickable
    #    For instance, <a href="/connection"> or something similar
    WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="/connection"]'))
    )

    # 2) Click it
    link = driver.find_element(By.CSS_SELECTOR, 'a[href="/connection"]')
    link.click()
    print("Clicked 'Connections' link in sidebar.")

    # 3) Wait for the table rows to appear on the /connection page
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
    )
    print("Connections table loaded.")


def scrape_connections_table(driver):
    """
    Scrape the entire Connections table from all pages (if paginated).
    """
    all_records = []

    while True:
        # Wait for table rows on the current page
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 6:
                record = {
                    "ID": cells[0].text.strip(),
                    "WebsiteId": cells[1].text.strip(),
                    "Username": cells[2].text.strip(),
                    "Status": cells[3].text.strip(),
                    "Locations": cells[4].text.strip(),
                    "LastUpdated": cells[5].text.strip(),
                }
                all_records.append(record)

        # Check for a "Next" button
        next_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]")
        if not next_buttons:
            break
        else:
            next_buttons[0].click()
            time.sleep(2)

    return all_records

def upload_data_to_google_sheets(worksheet, data):
    rows = [["ID", "WebsiteId", "Username", "Status", "Locations", "LastUpdated"]]
    for record in data:
        rows.append([
            record["ID"],
            record["WebsiteId"],
            record["Username"],
            record["Status"],
            record["Locations"],
            record["LastUpdated"]
        ])
    worksheet.clear()
    worksheet.update(values=rows, range_name="A1")
    print("Data successfully uploaded to Google Sheets!")

def main():
    print("Launching script...")  # <-- Debug print to test if main() runs
    
    # 1) Load config, set up Sheets, etc.
    config = load_config("config.json")
    SERVICE_ACCOUNT_FILE = config["service_account_file"]
    SHEET_NAME = config["sheet_name"]
    AUTH0_EMAIL = config["auth0_email"]
    AUTH0_PASSWORD = config["auth0_password"]

    worksheet = setup_google_sheets_client(SERVICE_ACCOUNT_FILE, SHEET_NAME)

    driver = webdriver.Chrome()
    try:
        # 2) Log in & navigate
        ensure_logged_in(driver, AUTH0_EMAIL, AUTH0_PASSWORD)
        click_connections_link(driver)

        # 3) Scrape the table (scrapes everything)
        all_data = scrape_connections_table(driver)

        # 4) Filter to just rows where Status == 'auth_failed'
        auth_failed_rows = [row for row in all_data if row["Status"] == "auth_failed"]

        # 5) Upload only the filtered rows
        upload_data_to_google_sheets(worksheet, auth_failed_rows)
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()