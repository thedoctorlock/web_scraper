Tuuthfairy Web Scraper

This project automates data collection from the Tuuthfairy dashboard, merges the scraped data with external info from Redash, filters out irrelevant or duplicated entries, then updates Google Sheets with all rows marked as auth_failed. It also logs a local historical record of each run.

Table of Contents
	•	Overview
	•	Project Structure
	•	Features
	•	Setup & Installation
	•	1. Clone the Repository
	•	2. Create/Activate a Virtual Environment
	•	3. Install Dependencies
	•	4. Set Up config.json
	•	5. Configure Credentials
	•	Usage
	•	Run the Scraper Directly
	•	Using run_scraper.sh
	•	How It Works
	•	Scheduling With Cron
	•	Logs & History
	•	Troubleshooting
	•	License

Overview

The Tuuthfairy Web Scraper logs into the Tuuthfairy dashboard via Auth0, navigates to the Connections table, scrapes connection details, enriches them with practice group information from Redash, and filters for any rows labeled auth_failed. Finally, it uploads the filtered results to a specific Google Sheets tab and appends a record to local history for auditing and tracking.

Key Technologies:
	•	Python 3
	•	Selenium for headless browser automation
	•	Google Sheets API via gspread for data upload
	•	Redash for pulling CSV data
	•	cron (on macOS) or a similar scheduler for automation

Project Structure

web_scraper/
├── config.json (not in repo, user-provided)
├── data_filter.py        # Filters the scraped data by practice group, status, etc.
├── google_sheets.py      # Handles all interactions with the Google Sheets API
├── local_history.py       # Appends data to a local CSV historical record
├── location_helpers.py   # Utility functions for parsing location fields
├── main.py               # Main entry point for the scraper
├── redash_data.py        # Fetches and processes data from Redash
├── requirements          # List of Python dependencies
├── run_scraper.sh        # Shell script to activate environment & run main.py
├── scraper.py            # Contains Selenium-based scraping logic
├── tuuthfairy_scraper.log (runtime log - created automatically)
└── auth_failed_history.csv (local history file - created automatically)

Features
	1.	Headless Scraping
Uses Selenium’s headless mode to log in via Auth0 and scrape the Connections table on the Tuuthfairy dashboard.
	2.	Redash Integration
Pulls data from a Redash CSV to map each locationId to a practiceGroupName and practiceGroupId.
	3.	Filtering & Merging
	•	Filters rows to specific practice groups designated as “Run” in a separate Google Sheet tab.
	•	Further narrows results to rows where Status == "auth_failed".
	•	Excludes domains you specify (like unumdentalpwp.skygenusasystems.com).
	•	Aggregates multiple locationId values per connection into a single row.
	4.	Data Upload to Google Sheets
Overwrites a chosen worksheet (default: “auth_failed”) with fresh data each run.
	5.	Local Historical Log
Appends every run’s data to a local CSV file (auth_failed_history.csv) for historical reference.

Setup & Installation

1. Clone the Repository

git clone <YOUR_REPO_URL> web_scraper
cd web_scraper

2. Create/Activate a Virtual Environment

Create a virtual environment (e.g., using venv) and activate it:

python3 -m venv env
source env/bin/activate

(Windows users would run env\Scripts\activate.)

3. Install Dependencies

pip install -r requirements

Ensure you have Google Chrome and ChromeDriver installed on your system, as Selenium will need them.

4. Set Up config.json

Create a config.json in the root project folder. Example structure:

{
  "service_account_file": "/path/to/google_service_account.json",
  "sheet_name": "Tuuthfairy Dashboard",
  "auth0_email": "myemail@example.com",
  "auth0_password": "myS3cretP4ssword",
  "redash_url": "https://redash.example.com/api/queries/123/results.csv",
  "redash_api_key": "REDASH_API_KEY"
}

	•	service_account_file: Path to your Google Service Account JSON file.
	•	sheet_name: Name of the Google Spreadsheet where data will be uploaded.
	•	auth0_email, auth0_password: Credentials for the Tuuthfairy dashboard.
	•	redash_url, redash_api_key: The CSV endpoint and API key for your Redash query.

5. Configure Credentials
	•	Google Service Account: In the Google Cloud Console, create or retrieve your service account JSON file and place it in a secure location.
	•	Auth0: Your email/password for logging into Tuuthfairy.
	•	Redash: The CSV URL (with query ID) and your API key.

Usage

Run the Scraper Directly

To run once from your terminal (assuming your virtual environment is active):

python main.py

Using run_scraper.sh

The included shell script can be used to activate the venv and run main.py in one go. Make sure it’s executable:

chmod +x run_scraper.sh

Then execute:

./run_scraper.sh

(By default, it logs output to cron.log in the same directory.)

How It Works
	1.	Initialization: main.py loads config, sets up logging, and configures Selenium in headless mode.
	2.	Auth0 Login: scraper.py automates the login process, waiting for the “Connections” link to confirm success.
	3.	Data Scraping: Selenium retrieves each page of the Connections table, building a list of rows.
	4.	Data Enrichment: redash_data.py pulls CSV from Redash and maps locationId to practice group metadata.
	5.	Filtering: data_filter.py narrows the results to practice groups that should “Run”, filters auth_failed, excludes certain websites, and merges multiple locations.
	6.	Local History: local_history.py appends the final dataset to auth_failed_history.csv.
	7.	Google Sheets Upload: google_sheets.py overwrites the “auth_failed” worksheet with fresh rows.

Scheduling With Cron

To run this automatically at a set time each day, add a crontab entry. For example, to run at 4:40 AM every day:

40 4 * * * /Users/YourUser/scripts/web_scraper/run_scraper.sh

	•	Make sure /Users/YourUser/scripts/web_scraper is a location macOS allows cron to access (e.g., outside Documents).
	•	Check cron.log or tuuthfairy_scraper.log for success/failure info.

Logs & History
	•	Log File: tuuthfairy_scraper.log captures execution details, including Selenium messages and error traces.
	•	Local CSV History: auth_failed_history.csv appends a copy of each run’s final data for a time-stamped record.
	•	cron.log: If you run run_scraper.sh with >> cron.log 2>&1, it captures stdout and stderr from the shell script.

Troubleshooting
	1.	Operation not permitted / Cron fails to run
	•	On macOS, check for extra security restrictions (e.g., Full Disk Access for cron).
	•	Move your script outside of Documents/ or Desktop/ to avoid TCC protection.
	•	Remove quarantine flags with xattr -d com.apple.quarantine run_scraper.sh.
	2.	Selenium / ChromeDriver Version Mismatch
	•	Update ChromeDriver to match your installed Chrome version.
	•	Confirm chromedriver --version aligns with chrome://version.
	3.	Network / Auth
	•	Ensure your Auth0 credentials are correct.
	•	Verify Redash URL & API key are accurate and that the endpoint is reachable.
	4.	Google API Errors
	•	Make sure your Google Service Account JSON is valid and has the correct scopes (Drive & Spreadsheets).
	•	Share your target Google Sheet with the service account email.

License

(Specify your license here, for example:)

This project is licensed under the MIT License. Feel free to modify and distribute according to the terms of the license.

Enjoy automating your Tuuthfairy scraping! If you have any issues or suggestions, feel free to open a pull request or file an issue.