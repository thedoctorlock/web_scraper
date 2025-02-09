# scraper.py
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def ensure_logged_in(driver, auth0_email, auth0_password):
    """
    Load /auth/login (redirects to Auth0).
    Fill credentials if the login form is found.
    Wait until the URL indicates we're back on dashboard.tuuthfairy.com.
    """
    driver.get("https://dashboard.tuuthfairy.com/auth/login")
    time.sleep(5)  # Let it redirect or load

    print("DEBUG: after hitting /auth/login, current URL =", driver.current_url)

    found_login_form = False

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#username"))
        )
        print("Found input#username on main page (no iframe).")
        found_login_form = True
    except:
        print("No direct #username found on main page; checking for iframe...")
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


def click_connections_link(driver):
    """
    Click the 'Connections' link in the sidebar, then wait for the table.
    """
    WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href="/connection"]'))
    )
    link = driver.find_element(By.CSS_SELECTOR, 'a[href="/connection"]')
    link.click()
    print("Clicked 'Connections' link in sidebar.")

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
    )
    print("Connections table loaded.")


def scrape_connections_table(driver):
    """
    Scrape the entire Connections table across all paginated pages.
    Returns a list of dict records.
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
                    "Locations": cells[4].text.strip(),  # Will process this later
                    "LastUpdated": cells[5].text.strip(),
                }
                all_records.append(record)

        next_buttons = driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]")
        if not next_buttons:
            break
        else:
            next_buttons[0].click()
            time.sleep(2)

    return all_records