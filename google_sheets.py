# google_sheets.py

import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_google_sheets_client(service_account_file, sheet_name, worksheet_name="auth_failed"):
    """
    Opens the specified Google Spreadsheet and returns the given worksheet (default: 'auth_failed').
    """
    creds = Credentials.from_service_account_file(service_account_file)
    scoped = creds.with_scopes([
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ])
    client = gspread.authorize(scoped)
    spreadsheet = client.open(sheet_name)
    worksheet = spreadsheet.worksheet(worksheet_name)
    return worksheet

def upload_data_to_google_sheets(worksheet, data):
    """
    Overwrites the entire worksheet with the new data.
    1) Clear the sheet.
    2) Re-insert the header in row 1.
    3) Insert all rows starting at row 2.
    """

    if not data:
        logger.info("No data to upload. Clearing the sheet just in case.")
        worksheet.clear()
        return

    # Define the header (including 'FetchedAt')
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

    # Clear the entire worksheet
    worksheet.clear()

    # Insert header at row 1
    worksheet.insert_row(header, 1)

    # We'll use one timestamp for this upload run
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build rows to insert
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

    # Insert all new rows below the header
    worksheet.insert_rows(new_rows, 2)

    logger.info("Data successfully overwritten in Google Sheets (auth_failed tab).")