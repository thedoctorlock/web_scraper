# scraper.py

import time
import logging
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

# If you do want to store screenshots from here, do:
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ensure_logged_in(driver, auth0_email, auth0_password):
    """
    Load /auth/login (redirects to Auth0).
    Fill credentials if the login form is found, then wait for body to confirm we're in.
    """
    driver.get("https://dashboard.tuuthfairy.com/auth/login")
    time.sleep(5)
    logger.debug("After hitting /auth/login, current URL = %s", driver.current_url)

    found_login_form = False

    try:
        # Try to find fields directly in main page
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#username"))
        )
        logger.info("Found input#username on main page (no iframe).")
        found_login_form = True
    except:
        logger.info("No direct #username found; maybe there's an iframe... ")
        try:
            WebDriverWait(driver, 5).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe"))
            )
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#username"))
            )
            logger.info("Found #username in iframe.")
            found_login_form = True
        except:
            logger.info("No #username found at all, possibly already logged in.")
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

        # If we switched to an iframe, switch back
        try:
            driver.switch_to.default_content()
        except:
            pass

    # Wait for the body to appear, giving up to 120s for Auth0 flow
    WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
    )
    logger.info("Login flow done (body present).")


def go_directly_to_connections(driver):
    """
    Navigate straight to /connection, wait for the table to appear.
    """
    driver.get("https://dashboard.tuuthfairy.com/connection")
    logger.info("Navigating directly to /connection...")

    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
    )
    logger.info("Connections table loaded after direct navigation.")


def scrape_connections_table(driver):
    """
    Scrape the entire Connections table across all pages, returning list of dicts.
    """
    all_records = []

    while True:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

        # The site might be using 5 rows per page, or 100, etc.
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 6:
                record = {
                    "ID": cells[0].text.strip(),
                    "WebsiteId": cells[1].text.strip(),
                    "Username": cells[2].text.strip(),
                    "Status": cells[3].text.strip(),
                    "Locations": cells[4].text.strip(),  # We'll parse these later
                    "LastUpdated": cells[5].text.strip(),
                }
                all_records.append(record)

        # If there's a "Next" pagination button, click it; otherwise break
        next_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]")
        if not next_buttons:
            break
        next_buttons[0].click()
        time.sleep(2)

    logger.info("Scraped %d records from connections table.", len(all_records))
    return all_records

def save_debug_screenshot_and_html(driver):
    """
    Example helper if you want a function to save debug info from scraper.py
    """
    screenshot_path = os.path.join(BASE_DIR, "scraper_error.png")
    driver.save_screenshot(screenshot_path)
    logger.info("Saved screenshot to %s", screenshot_path)

    html_path = os.path.join(BASE_DIR, "scraper_error.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    logger.info("Saved page source to %s", html_path)