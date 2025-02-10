# local_history.py

import csv
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Define a base directory for local_history.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Construct an absolute path for the CSV
HISTORY_FILE = os.path.join(BASE_DIR, "auth_failed_history.csv")

def append_run_data(data, filepath=HISTORY_FILE):
    """
    Appends the 'data' rows to a local CSV file for historical record.

    If the file doesn't exist yet, we create it and write a header first.
    Otherwise, we simply append new rows at the end.

    We also set or update the 'FetchedAt' timestamp for consistency.
    """

    if not data:
        logger.info("No data to record locally.")
        return

    file_exists = os.path.isfile(filepath)
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

    # One timestamp for all rows in this run
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(filepath, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # If the file is brand new, add the header first
        if not file_exists:
            writer.writerow(header)

        # Write each row
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
            writer.writerow(row)

    logger.info("Appended %d rows to the local history file: %s", len(data), filepath)