#!/bin/bash
#
# Cron wrapper script for zeek-to-sqlite.py
# This script handles logging, error reporting, and ensures only one instance runs at a time
#

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.json"
LOCK_FILE="/var/run/zeek-to-sqlite.lock"
LOG_FILE="/var/log/zeek-to-sqlite-cron.log"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to cleanup on exit
cleanup() {
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
        log_message "Lock file removed"
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Check if another instance is running
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log_message "ERROR: Another instance is already running (PID: $PID)"
        exit 1
    else
        log_message "WARNING: Stale lock file found, removing it"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
echo $$ > "$LOCK_FILE"
log_message "Starting zeek-to-sqlite processing (PID: $$)"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    log_message "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Extract configuration values (requires jq or use Python)
if command -v jq &> /dev/null; then
    LOGS_DIR=$(jq -r '.logs_directory' "$CONFIG_FILE")
    DB_PATH=$(jq -r '.database_path' "$CONFIG_FILE")
    LOG_FILE_PYTHON=$(jq -r '.log_file' "$CONFIG_FILE")
    LOG_LEVEL=$(jq -r '.log_level' "$CONFIG_FILE")
    DAYS_BACK=$(jq -r '.days_back // empty' "$CONFIG_FILE")
else
    # Fallback: use Python to parse JSON
    LOGS_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['logs_directory'])")
    DB_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['database_path'])")
    LOG_FILE_PYTHON=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['log_file'])")
    LOG_LEVEL=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['log_level'])")
    DAYS_BACK=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c.get('days_back') or '')")
fi

# Build command
CMD="${SCRIPT_DIR}/zeek-to-sqlite.py"
CMD="${CMD} --logs-dir \"${LOGS_DIR}\""
CMD="${CMD} --database \"${DB_PATH}\""
CMD="${CMD} --log-file \"${LOG_FILE_PYTHON}\""
CMD="${CMD} --log-level ${LOG_LEVEL}"

if [ -n "$DAYS_BACK" ] && [ "$DAYS_BACK" != "null" ]; then
    CMD="${CMD} --days ${DAYS_BACK}"
fi

# Execute the Python script
log_message "Executing: $CMD"
eval "$CMD" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log_message "Processing completed successfully"
else
    log_message "ERROR: Processing failed with exit code $EXIT_CODE"
    # Optionally send email notification here
fi

exit $EXIT_CODE

