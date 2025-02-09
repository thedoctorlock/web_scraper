# data_filter.py

import logging

logger = logging.getLogger(__name__)

def filter_by_practice_groups(expanded_data, valid_practice_groups):
    """
    Filter the list of expanded data rows to only include rows whose
    practiceGroupName is in valid_practice_groups. We normalize by stripping
    and lowercasing both sides to avoid subtle mismatches.
    """
    logger.info("Filtering by valid practice groups: %s", valid_practice_groups)
    normalized_set = {pg.strip().lower() for pg in valid_practice_groups}

    filtered = []
    for row in expanded_data:
        pg_name = row.get("practiceGroupName", "").strip().lower()
        if pg_name in normalized_set:
            filtered.append(row)

    logger.info(
        "filter_by_practice_groups: %d rows in, %d rows out",
        len(expanded_data), len(filtered)
    )
    return filtered

def filter_auth_failed(rows):
    """
    Return only rows where Status == 'auth_failed'.
    """
    logger.info("Filtering rows for 'auth_failed' status.")
    filtered = [row for row in rows if row["Status"] == "auth_failed"]
    logger.info(
        "filter_auth_failed: %d rows in, %d rows out",
        len(rows), len(filtered)
    )
    return filtered

def exclude_websites(rows, excluded_sites):
    """
    Exclude rows where row["WebsiteId"] is in the set/list of excluded_sites.
    e.g., excluded_sites = {"unumdentalpwp.skygenusasystems.com"}
    """
    logger.info("Excluding websites: %s", excluded_sites)
    filtered = [row for row in rows if row["WebsiteId"] not in excluded_sites]
    logger.info(
        "exclude_websites: %d rows in, %d rows out",
        len(rows), len(filtered)
    )
    return filtered

def regroup_and_merge_locations(rows):
    """
    Given a list of rows (each representing a single location for a connection),
    group them by the connection 'ID' and merge the locationIds.

    Each connection (ID) appears only once and the locationIds are concatenated.
    """
    logger.info("Regrouping and merging locationIds across %d rows.", len(rows))
    grouped = {}

    for row in rows:
        conn_id = row["ID"]
        if conn_id not in grouped:
            grouped[conn_id] = {
                "ID": row["ID"],
                "WebsiteId": row["WebsiteId"],
                "Username": row["Username"],
                "Status": row["Status"],
                "LastUpdated": row["LastUpdated"],
                "practiceGroupId": row["practiceGroupId"],
                "practiceGroupName": row["practiceGroupName"],
                "locationIds": []
            }
        # Append the locationId if it exists
        if row.get("locationId"):
            grouped[conn_id]["locationIds"].append(row["locationId"])

    merged_data = []
    for conn_id, agg in grouped.items():
        location_str = ", ".join(agg["locationIds"]) if agg["locationIds"] else ""
        merged_data.append({
            "ID": agg["ID"],
            "WebsiteId": agg["WebsiteId"],
            "Username": agg["Username"],
            "Status": agg["Status"],
            "LastUpdated": agg["LastUpdated"],
            "practiceGroupId": agg["practiceGroupId"],
            "practiceGroupName": agg["practiceGroupName"],
            "locationId": location_str
        })

    logger.info("Finished regroup_and_merge_locations: %d unique connections.", len(merged_data))
    return merged_data