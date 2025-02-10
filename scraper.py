# scraper.py

import time
import logging
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ensure_logged_in(driver, auth0_email, auth0_password, max_retries=2):
    """
    Attempt to log into the Tuuthfairy dashboard via Auth0.
    We do step-by-step waits for intermediate redirects and
    retry the entire login flow if we encounter timeouts.

    :param driver: The Selenium WebDriver instance.
    :param auth0_email: Auth0 login email.
    :param auth0_password: Auth0 login password.
    :param max_retries: How many times to retry if timeouts occur.
    """
    login_url = "https://dashboard.tuuthfairy.com/auth/login"

    for attempt in range(max_retries):
        logger.info("ensure_logged_in: Attempt %d of %d", attempt+1, max_retries)

        # Start fresh each time we retry:
        driver.get(login_url)
        time.sleep(2)  # small pause for the initial page load

        found_login_form = False

        try:
            ###############################
            # A) DETECT THE LOGIN FORM
            ###############################
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
                    # If we never found the form, let's move on; possibly we’re already logged in.

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

            ###############################
            # B) WAIT FOR AUTH0 REDIRECT
            ###############################
            # If your Auth0 flow actually redirects to "something.auth0.com",
            # we can explicitly wait to see that domain. This step is optional
            # and depends on your exact Auth0 tenant domain.

            def on_auth0_domain(d):
                return "auth0" in d.current_url.lower()

            try:
                WebDriverWait(driver, 30).until(on_auth0_domain)
                logger.info("Detected Auth0 domain in URL: %s", driver.current_url)
            except TimeoutException:
                logger.info("Never saw an auth0.com domain—maybe the redirect was fast or not needed.")

            ###############################
            # C) WAIT FOR FINAL REDIRECT BACK TO TUUTHFAIRY
            ###############################
            def on_tuuthfairy_domain(d):
                return "dashboard.tuuthfairy.com" in d.current_url.lower()

            WebDriverWait(driver, 60).until(on_tuuthfairy_domain)
            logger.info("Back on Tuuthfairy domain. Current URL: %s", driver.current_url)

            # Optionally wait for a post-login element: e.g., "Connections" link or a nav bar
            # that indicates the user is truly logged in:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "nav a[href*='connection']"))
            )
            logger.info("Found 'Connections' link. Login flow appears complete.")
            return  # success, so exit the function

        except TimeoutException:
            # If we hit any TimeoutException, let's log it, possibly do a screenshot, then retry
            logger.warning("Timeout while logging in (attempt %d/%d). Retrying...", attempt+1, max_retries)

            # Optionally save a screenshot for debug
            screenshot_path = os.path.join(BASE_DIR, f"login_error_attempt_{attempt+1}.png")
            driver.save_screenshot(screenshot_path)
            logger.info("Saved screenshot to %s", screenshot_path)

            # Optionally we can do a quick page_source dump:
            html_path = os.path.join(BASE_DIR, f"login_error_attempt_{attempt+1}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info("Saved HTML page source to %s", html_path)

    # If we exhaust retries and still haven't returned, raise an exception
    raise TimeoutException("Failed to log in after multiple attempts.")

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