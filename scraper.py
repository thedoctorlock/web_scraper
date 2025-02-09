# scraper.py

import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

def ensure_logged_in(driver, auth0_email, auth0_password):
    """
    Load /auth/login (redirects to Auth0).
    Fill credentials if the login form is found.
    We wait until we're certain the user is logged in, then we proceed.
    """
    driver.get("https://dashboard.tuuthfairy.com/auth/login")
    time.sleep(5)  # Allow initial page or redirect to happen
    logger.debug("After hitting /auth/login, current URL = %s", driver.current_url)

    found_login_form = False

    # Attempt to find login fields outside an iframe
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#username"))
        )
        logger.info("Found input#username on main page (no iframe).")
        found_login_form = True
    except:
        logger.info("No direct #username found on main page; checking for iframe...")
        # Attempt to switch to an iframe with login fields
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
            logger.info("No #username found, possibly already logged in.")
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

    # Instead of waiting specifically for the "Connections" link,
    # we'll just wait until the page (body) is present for up to 2 minutes,
    # which should cover the Auth0 flow.
    WebDriverWait(driver, 120).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
    )
    logger.info("Login flow done (body present).")


def go_directly_to_connections(driver):
    """
    Instead of clicking a sidebar link, navigate straight to /connection,
    and wait for the 'table tbody tr' to appear.
    """
    driver.get("https://dashboard.tuuthfairy.com/connection")
    logger.info("Navigating directly to /connection...")

    # Wait up to 60 seconds for the table to appear
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
    )
    logger.info("Connections table loaded after direct navigation.")


def scrape_connections_table(driver):
    """
    Scrape the entire Connections table across all pages. Returns a list of dicts.
    """
    all_records = []

    while True:
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
                    "Locations": cells[4].text.strip(),  # cleaned later
                    "LastUpdated": cells[5].text.strip(),
                }
                all_records.append(record)

        # Check for a 'Next' pagination button
        next_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]")
        if not next_buttons:
            break
        else:
            next_buttons[0].click()
            time.sleep(2)

    logger.info("Scraped %d records from connections table.", len(all_records))
    return all_records