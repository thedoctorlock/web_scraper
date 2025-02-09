# location_helpers.py

def process_location_field(location_field):
    """
    Process a comma-separated location field.

    - If the field is exactly "default", return ["default"].
    - Otherwise, remove "airpay_" prefix from entries.
    - If 'default' is present among multiple entries, ignore it.

    e.g.:
      "airpay_23864, airpay_23352, default" -> ["23864", "23352"]
    """
    entries = [entry.strip() for entry in location_field.split(",")]

    # If there's only one entry and it's "default"
    if len(entries) == 1 and entries[0].lower() == "default":
        return ["default"]

    processed_entries = []
    for entry in entries:
        entry_lower = entry.lower()
        if entry_lower == "default":
            # Skip if there are multiple entries
            continue
        elif entry.startswith("airpay_"):
            processed_entries.append(entry[7:])  # remove 'airpay_'
        else:
            processed_entries.append(entry)
    
    return processed_entries