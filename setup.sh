#!/bin/bash
#
# Setup script for Zeek Logs to SQLite
# Creates necessary directories and sets permissions
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.json"

echo "Zeek Logs to SQLite - Setup"
echo "============================"
echo ""

# Check if running as root for system directories
if [ "$EUID" -ne 0 ]; then 
    echo "Note: Some operations may require sudo privileges"
    echo ""
fi

# Read config values
if command -v jq &> /dev/null; then
    DB_PATH=$(jq -r '.database_path' "$CONFIG_FILE")
    LOG_FILE=$(jq -r '.log_file' "$CONFIG_FILE")
else
    DB_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['database_path'])")
    LOG_FILE=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['log_file'])")
fi

DB_DIR=$(dirname "$DB_PATH")
LOG_DIR=$(dirname "$LOG_FILE")

echo "Creating directories..."
echo "  Database directory: $DB_DIR"
echo "  Log directory: $LOG_DIR"
echo ""

# Create directories
if [ ! -d "$DB_DIR" ]; then
    if [ "$EUID" -eq 0 ]; then
        mkdir -p "$DB_DIR"
    else
        sudo mkdir -p "$DB_DIR"
    fi
    echo "  ✓ Created $DB_DIR"
else
    echo "  ✓ $DB_DIR already exists"
fi

if [ ! -d "$LOG_DIR" ]; then
    if [ "$EUID" -eq 0 ]; then
        mkdir -p "$LOG_DIR"
    else
        sudo mkdir -p "$LOG_DIR"
    fi
    echo "  ✓ Created $LOG_DIR"
else
    echo "  ✓ $LOG_DIR already exists"
fi

# Set permissions (use current user if not root)
if [ "$EUID" -eq 0 ]; then
    USER=$(logname 2>/dev/null || echo "$SUDO_USER")
    if [ -n "$USER" ]; then
        chown "$USER:$USER" "$DB_DIR" "$LOG_DIR" 2>/dev/null || true
    fi
else
    USER=$(whoami)
    sudo chown "$USER:$USER" "$DB_DIR" "$LOG_DIR" 2>/dev/null || true
fi

echo ""
echo "Making scripts executable..."
chmod +x "${SCRIPT_DIR}/zeek-to-sqlite.py"
chmod +x "${SCRIPT_DIR}/zeek-to-sqlite-cron.sh"
chmod +x "${SCRIPT_DIR}/setup.sh"
echo "  ✓ Scripts are now executable"

echo ""
echo "Testing Python script..."
if python3 "${SCRIPT_DIR}/zeek-to-sqlite.py" --help > /dev/null 2>&1; then
    echo "  ✓ Python script is working"
else
    echo "  ✗ Python script test failed"
    exit 1
fi

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Review and edit config.json if needed"
echo "2. Test the script manually:"
echo "   ${SCRIPT_DIR}/zeek-to-sqlite.py --days 1"
echo "3. Set up cron (edit crontab.example first, then):"
echo "   crontab crontab.example"
echo ""

