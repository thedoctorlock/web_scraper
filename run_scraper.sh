#!/bin/bash
# Change directory to your project folder (new location)
cd /Users/jackgallagher/scripts/web_scraper

# (Optional) Activate your virtual environment
source env/bin/activate

# Run the Python script and log output
/usr/bin/env python3 main.py >> cron.log 2>&1