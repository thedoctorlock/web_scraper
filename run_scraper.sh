#!/bin/bash
#
# run_scraper.sh
#
# Universal script to:
# 1. Move into the script's own directory
# 2. Activate the local Python virtual environment if available
# 3. Run main.py with logging

# --- 1) Move to the script's directory ---
# This ensures relative paths are consistent
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# --- 2) (Optional) Activate a virtual env if it exists ---
# We'll check if env/bin/activate is present before sourcing.
if [ -f "$SCRIPT_DIR/env/bin/activate" ]; then
    source "$SCRIPT_DIR/env/bin/activate"
fi

# --- 3) Log a quick timestamp and run the script ---
echo "run_scraper.sh triggered at $(date)" >> "$SCRIPT_DIR/cron.log"

# We'll pick a Python interpreter:
#  - If the virtual env’s python exists, use it.
#  - Otherwise fall back to system python3.
if [ -x "$SCRIPT_DIR/env/bin/python" ]; then
    PY_EXE="$SCRIPT_DIR/env/bin/python"
else
    PY_EXE="python3"
fi

# Now run main.py, appending all output to cron.log
"$PY_EXE" main.py >> "$SCRIPT_DIR/cron.log" 2>&1