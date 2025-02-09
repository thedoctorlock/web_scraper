# location_helpers.py

import logging

logger = logging.getLogger(__name__)

def process_location_field(location_field):
    """
    Process a comma-separated location field.

    - If the field is exactly "default", return ["default"].
    - Otherwise, remove "airpay_" prefix from entries.
    - If 'default' is present among multiple entries, ignore it.

    e.g.:
      "airpay_23864, airpay_23352, default" -> ["23864", "23352"]
    """
    logger.debug("Processing location field: %s", location_field)
    entries = [entry.strip() for entry in location_field.split(",")]

    # If there's only one entry and it's "default"
    if len(entries) == 1 and entries[0].lower() == "default":
        logger.debug("Only 'default' found; returning ['default']")
        return ["default"]

    processed_entries = []
    for entry in entries:
        entry_lower = entry.lower()
        if entry_lower == "default":
            # Skip if there are multiple entries
            logger.debug("Skipping 'default' among multiple entries.")
            continue
        elif entry.startswith("airpay_"):
            processed_value = entry[7:]
            logger.debug("Removing 'airpay_' prefix: %s -> %s", entry, processed_value)
            processed_entries.append(processed_value)
        else:
            processed_entries.append(entry)
    
    logger.debug("Processed entries: %s", processed_entries)
    return processed_entries