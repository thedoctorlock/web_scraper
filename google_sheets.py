# google_sheets.py

import gspread
from google.oauth2.service_account import Credentials

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

def upload_data_to_google_sheets(worksheet, data):
    """
    data is a list of dictionaries. We create a header row with the columns we expect,
    then build rows accordingly.

    We'll include:
      - ID, WebsiteId, Username, Status, locationId, LastUpdated
      - practiceGroupId, practiceGroupName
    """
    if not data:
        print("No data to upload.")
        return

    header = [
        "ID",
        "WebsiteId",
        "Username",
        "Status",
        "locationId",
        "LastUpdated",
        "practiceGroupId",
        "practiceGroupName"
    ]
    rows = [header]

    for record in data:
        row = [
            record.get("ID", ""),
            record.get("WebsiteId", ""),
            record.get("Username", ""),
            record.get("Status", ""),
            record.get("locationId", ""),
            record.get("LastUpdated", ""),
            record.get("practiceGroupId", ""),
            record.get("practiceGroupName", "")
        ]
        rows.append(row)

    worksheet.clear()
    worksheet.update(values=rows, range_name="A1")
    print("Data successfully uploaded to Google Sheets!")