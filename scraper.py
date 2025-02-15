# scraper.py

import time
import logging
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    StaleElementReferenceException,
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ensure_logged_in(driver, auth0_email, auth0_password, max_retries=2):
    """
    Attempt to log into the Tuuthfairy dashboard via Auth0.
    We do step-by-step waits for intermediate redirects and
    retry the entire login flow if we encounter timeouts.

    NOTE FOR CRON/CI USAGE:
    - Make sure PATH includes /usr/bin, /bin, etc. so that Google Chrome
      can locate system utilities it needs. If missing, login may fail.
    - If you see 'Chrome failed to start: exited abnormally', you may need
      --no-sandbox, --disable-dev-shm-usage, or an updated PATH in the crontab.
    """
    login_url = "https://dashboard.tuuthfairy.com/auth/login"

    for attempt in range(max_retries):
        logger.info("ensure_logged_in: Attempt %d of %d", attempt + 1, max_retries)

        # Start fresh each time we retry:
        driver.get(login_url)
        time.sleep(2)  # small pause for the initial page load

        found_login_form = False

        try:
            # A) DETECT THE LOGIN FORM
            try:
                # Try main page first
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input#username"))
                )
                logger.info("Found input#username on main page (no iframe).")
                found_login_form = True
            except TimeoutException:
                logger.info("No direct #username found on main page; checking for iframe...")
                try:
                    WebDriverWait(driver, 5).until(
                        EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe"))
                    )
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input#username"))
                    )
                    logger.info("Found #username in iframe.")
                    found_login_form = True
                except TimeoutException:
                    logger.info("No #username found at all—could be already logged in or slow load.")

            if found_login_form:
                email_input = driver.find_element(By.CSS_SELECTOR, "input#username")
                email_input.clear()
                email_input.send_keys(auth0_email)

                password_input = driver.find_element(By.CSS_SELECTOR, "input#password")
                password_input.clear()
                password_input.send_keys(auth0_password)

                login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_btn.click()

                # If we switched to an iframe, revert to main content
                try:
                    driver.switch_to.default_content()
                except:
                    pass

            # B) WAIT FOR AUTH0 REDIRECT
            def on_auth0_domain(d):
                return "auth0" in d.current_url.lower()

            try:
                WebDriverWait(driver, 30).until(on_auth0_domain)
                logger.info("Detected Auth0 domain in URL: %s", driver.current_url)
            except TimeoutException:
                logger.info("Never saw an auth0.com domain—maybe the redirect was very quick or not needed.")

            # C) WAIT FOR FINAL REDIRECT BACK TO TUUTHFAIRY
            def on_tuuthfairy_domain(d):
                return "dashboard.tuuthfairy.com" in d.current_url.lower()

            WebDriverWait(driver, 60).until(on_tuuthfairy_domain)
            logger.info("Back on Tuuthfairy domain. Current URL: %s", driver.current_url)

            # Wait for the "Connections" link or a nav bar element to confirm login
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "nav a[href*='connection']"))
            )
            logger.info("Found 'Connections' link. Login flow appears complete.")
            return  # success
        except TimeoutException:
            # If we hit a TimeoutException, let's log it, possibly do a screenshot, then retry
            logger.warning("Timeout while logging in (attempt %d/%d). Retrying...", attempt + 1, max_retries)

            screenshot_path = os.path.join(BASE_DIR, f"login_error_attempt_{attempt+1}.png")
            driver.save_screenshot(screenshot_path)
            logger.info("Saved screenshot to %s", screenshot_path)

            html_path = os.path.join(BASE_DIR, f"login_error_attempt_{attempt+1}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info("Saved HTML page source to %s", html_path)

    # If we exhaust retries and still haven't returned, raise an exception
    raise TimeoutException("Failed to log in after multiple attempts.")

def go_directly_to_connections(driver):
    driver.get("https://dashboard.tuuthfairy.com/connection")
    logger.info("Navigating directly to /connection...")

    # Debug snippet 1 (BEFORE waiting for the table) - take only if logger is set to Debug 
    if logger.isEnabledFor(logging.DEBUG):
        driver.save_screenshot("connection_before_wait.png")
        logger.debug("Saved screenshot to connection_before_wait.png")

    logger.debug("Page source BEFORE waiting:\n%s", driver.page_source)

    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
    )

    # Debug snippet 2 (AFTER the table is found):
    if logger.isEnabledFor(logging.DEBUG):
        driver.save_screenshot("connection_after_wait.png")
        logger.debug("Saved screenshot to connection_after_wait.png")

    logger.debug("Page source AFTER waiting:\n%s", driver.page_source)

    logger.info("Connections table loaded after direct navigation.")

def scrape_connections_table(driver):
    """
    Scrape the entire Connections table across all pages, returning a list of dicts.

    We use a robust row-by-row approach to re-locate elements if they go stale.
    """
    all_records = []
    page_count = 1  # Initialize the page count
    
    while True:
        # Before waiting
        if logger.isEnabledFor(logging.DEBUG):
            driver.save_screenshot(f"scrape_before_wait_page{page_count}.png")
            logger.debug("Saved screenshot to scrape_before_wait_page#.png")

        logger.debug("Page source BEFORE wait on page %d:\n%s", page_count, driver.page_source)

        # Wait for the table (empty or not)
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.w-full.caption-bottom.text-sm"))
        )

        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        if not rows:
            logger.info("Page %d is empty. Stopping scraper.", page_count)
            break

        # After waiting
        if logger.isEnabledFor(logging.DEBUG):
            driver.save_screenshot(f"scrape_after_wait_page{page_count}.png")
            logger.debug("Saved screenshot to scrape_after_wait_page#.png")
        
        logger.debug("Page source AFTER wait on page %d:\n%s", page_count, driver.page_source)

        # 1) Get the total number of rows in the table
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        # If rows exist but they contain no <td> cells (or only header cells), consider it blank.
        data_found = False
        for row in rows:
            # Look for <td> cells
            cells = row.find_elements(By.TAG_NAME, "td")
            if cells and any(cell.text.strip() for cell in cells):
                data_found = True
                break

        if not data_found:
            logger.info("No data rows found on page %d, ending pagination.", page_count)
            break

        num_rows = len(rows)
        logger.debug("Found %d rows on this page", num_rows)

        # 2) Iterate by index so we can re-locate each row as needed
        for row_index in range(num_rows):
            record = _scrape_row_with_retry(driver, row_index)
            if record is not None:
                all_records.append(record)

        # 3) Check for "Next" pagination button and click if present
        next_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]")
        if not next_buttons:
            break
        next_buttons[0].click()

        # small buffer after pagination click so page can re-render
        time.sleep(2)
        page_count += 1

    logger.info("Scraped %d records from connections table.", len(all_records))
    return all_records

def _scrape_row_with_retry(driver, row_index, max_retries=3):
    """
    Locate the row at row_index, find its <td> cells, and extract text.
    If we hit a StaleElementReferenceException, we re-locate the row and try again.

    Returns a dict or None if we fail.
    """
    attempts = 0
    while attempts < max_retries:
        try:
            # Re-locate the row at this index
            rows_current = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            # Debug snippet
            if logger.isEnabledFor(logging.DEBUG):
                driver.save_screenshot(f"row_retry_{row_index}_attempt_{attempts}.png")
                logger.debug("Saved screenshot to row_retry_#_attempt_#.png")
            
            logger.debug("Found %d rows. Attempt %d for row %d. Page source:\n%s",
                        len(rows_current), attempts, row_index, driver.page_source)
            
            if row_index >= len(rows_current):
                logger.warning(
                    "Row index %d is out of range after re-locating rows. Skipping row.",
                    row_index
                )
                return None

            row = rows_current[row_index]
            cells = row.find_elements(By.TAG_NAME, "td")

            # We expect at least 6 cells: ID, WebsiteId, Username, Status, Locations, LastUpdated
            if len(cells) < 6:
                logger.warning(
                    "Row %d has only %d cells, expected >= 6. Skipping this row.",
                    row_index, len(cells)
                )
                return None

            # Extract text immediately
            id_text = cells[0].text.strip()
            website_text = cells[1].text.strip()
            username_text = cells[2].text.strip()
            status_text = cells[3].text.strip()
            locations_text = cells[4].text.strip()
            last_updated_text = cells[5].text.strip()

            record = {
                "ID": id_text,
                "WebsiteId": website_text,
                "Username": username_text,
                "Status": status_text,
                "Locations": locations_text,
                "LastUpdated": last_updated_text,
            }
            return record

        except StaleElementReferenceException:
            logger.warning(
                "Stale element on row %d attempt %d/%d. Re-locating row and retrying.",
                row_index, attempts + 1, max_retries
            )
            time.sleep(1)
            attempts += 1
        except WebDriverException as e:
            logger.warning("WebDriverException on row %d: %s", row_index, e)
            return None

    logger.warning(
        "Row %d: max retries (%d) hit for stale elements. Skipping this row.",
        row_index, max_retries
    )
    return None

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