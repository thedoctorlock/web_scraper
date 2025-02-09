# google_sheets.py

import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_google_sheets_client(service_account_file, sheet_name, worksheet_name="auth_failed"):
    """
    Opens the specified Google Spreadsheet and returns the 'auth_failed' worksheet (by default).
    """
    creds = Credentials.from_service_account_file(service_account_file)
    scoped = creds.with_scopes([
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ])
    client = gspread.authorize(scoped)
    spreadsheet = client.open(sheet_name)

    # Instead of using spreadsheet.sheet1, explicitly open the 'auth_failed' tab
    worksheet = spreadsheet.worksheet(worksheet_name)
    return worksheet

def upload_data_to_google_sheets(worksheet, data):
    """
    Instead of clearing the sheet and overwriting everything, we:
      1) Ensure row 1 has our header.
      2) Insert the new rows at row 2, so the newest is always on top.
      3) Include a new column called 'FetchedAt' for a timestamp of when the data was pulled.
    """
    if not data:
        logger.info("No data to upload.")
        return

    # Define the updated header, including the new timestamp column
    header = [
        "ID",
        "WebsiteId",
        "Username",
        "Status",
        "locationId",
        "LastUpdated",
        "practiceGroupId",
        "practiceGroupName",
        "FetchedAt"
    ]

    # Check existing sheet content
    existing_values = worksheet.get_all_values()

    # If empty or missing columns, insert/update the header
    if not existing_values:
        logger.info("Sheet is empty, inserting header row.")
        worksheet.insert_row(header, 1)
    else:
        # Optionally, you could check if existing_values[0] == header.
        # But typically, if your columns match, this is enough.
        pass

    # Append new rows at the top (below the header)
    # We'll use one timestamp for this entire run, or you could do per-row if you like
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_rows = []
    for record in data:
        row = [
            record.get("ID", ""),
            record.get("WebsiteId", ""),
            record.get("Username", ""),
            record.get("Status", ""),
            record.get("locationId", ""),
            record.get("LastUpdated", ""),
            record.get("practiceGroupId", ""),
            record.get("practiceGroupName", ""),
            fetch_time
        ]
        new_rows.append(row)

    # Insert these rows at row 2, pushing older data downward
    worksheet.insert_rows(new_rows, 2)

    logger.info("Data successfully uploaded to Google Sheets (auth_failed tab)!")