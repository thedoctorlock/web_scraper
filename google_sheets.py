# google_sheets.py

import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_google_sheets_client(service_account_file, sheet_name, worksheet_name="auth_failed"):
    """
    Sets up the Google Sheets client and returns the specified worksheet.
    """
    client = gspread.service_account(filename=service_account_file)
    spreadsheet = client.open(sheet_name)
    worksheet = spreadsheet.worksheet(worksheet_name)
    return worksheet

def upload_data_to_google_sheets(worksheet, data, practice_group_count=None):
    """
    Overwrites the entire worksheet with the new data.
    If there's no data, writes a message indicating that no auth_failed connections were found,
    including the number of practice groups pulled and a timestamp.

    Otherwise:
      1) Clears the sheet.
      2) Inserts a header row (including a 'Connection Link' column).
      3) Builds each row with a clickable link in the 'Connection Link' column that points to
         https://dashboard.tuuthfairy.com/connection/<ID>.
      4) Inserts all rows below the header, interpreting formulas with `value_input_option='USER_ENTERED'`.
    """
    # CASE 1: No data
    if not data:
        logger.info("No auth_failed connections found. Writing a message to the sheet instead.")
        worksheet.clear()

        # Format the message with the practice group count and time
        fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"No auth_failed connections found. {practice_group_count} practice groups pulled "
            f"from Tuuthfairy Groups. {fetch_time}"
        )

        # Insert a header row for clarity
        worksheet.insert_row(["Message"], 1)
        # Insert the message as the second row
        worksheet.insert_row([message], 2)
        return

    # CASE 2: We have data
    # Define the header row
    header = [
        "Connection Link",
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

    # Insert the header at row 1
    worksheet.insert_row(header, 1)

    # We'll use one timestamp for the entire upload run
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build rows to insert, with the first column as a clickable link
    new_rows = []
    base_url = "https://dashboard.tuuthfairy.com/connection/"

    for record in data:
        connection_id = record.get("ID", "")
        # Build a formula that creates a clickable hyperlink: =HYPERLINK("url", "link text")
        link_formula = f'=HYPERLINK("{base_url}{connection_id}", "{connection_id}")'

        row = [
            link_formula,
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
    # Use 'USER_ENTERED' so Google Sheets interprets our =HYPERLINK formula
    worksheet.insert_rows(new_rows, 2, value_input_option='USER_ENTERED')

    logger.info("Data successfully overwritten in Google Sheets (auth_failed tab).")