# redash_data.py

import requests
import csv
import io
import logging

logger = logging.getLogger(__name__)

def fetch_redash_csv(redash_url, api_key=None):
    """
    Retrieve CSV data from Redash and return as a list of dict rows.
    """
    logger.info("Fetching Redash CSV from %s", redash_url)

    headers = {}
    if api_key:
        logger.debug("Using API key for authorization.")
        headers["Authorization"] = f"Key {api_key}"

    response = requests.get(redash_url, headers=headers)
    response.raise_for_status()  # raise an exception if the request fails

    logger.debug("Redash response received. Status code: %s", response.status_code)

    f = io.StringIO(response.text)
    reader = csv.DictReader(f)
    rows = list(reader)

    logger.info("Successfully parsed %d rows from Redash CSV.", len(rows))
    return rows

def build_location_map(redash_rows):
    """
    Convert the list of Redash CSV rows into a dictionary keyed by locationId.
    We only keep practiceGroupId and practiceGroupName.

    If multiple rows share the same locationId, store the first match found.
    Adjust logic if you want to handle duplicates differently.
    """
    logger.info("Building location map from Redash rows. Total rows: %d", len(redash_rows))
    location_map = {}

    for row in redash_rows:
        loc_id = row["locationId"]  # CSV column name
        if loc_id not in location_map:
            location_map[loc_id] = {
                "practiceGroupId": row["practiceGroupId"],
                "practiceGroupName": row["practiceGroupName"]
            }

    logger.info("Built location map with %d unique locationIds.", len(location_map))
    return location_map