# redash_data.py

import requests
import csv
import io

def fetch_redash_csv(redash_url, api_key=None):
    """
    Retrieve CSV data from Redash and return as a list of dict rows.
    """
    headers = {}
    if api_key:
        headers["Authorization"] = f"Key {api_key}"

    response = requests.get(redash_url, headers=headers)
    response.raise_for_status()  # raise an exception if the request fails

    f = io.StringIO(response.text)
    reader = csv.DictReader(f)
    rows = list(reader)
    return rows

def build_location_map(redash_rows):
    """
    Convert the list of Redash CSV rows into a dictionary keyed by locationId.
    We only keep practiceGroupId and practiceGroupName.

    If multiple rows share the same locationId, store the first match found.
    Adjust logic if you want to handle duplicates differently.
    """
    location_map = {}

    for row in redash_rows:
        loc_id = row["locationId"]  # CSV column name
        if loc_id not in location_map:
            location_map[loc_id] = {
                "practiceGroupId": row["practiceGroupId"],
                "practiceGroupName": row["practiceGroupName"]
            }

    return location_map