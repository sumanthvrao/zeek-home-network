# Zeek Home Network Logs to SQLite

This project processes Zeek network monitoring logs from date-based directories and imports them into a SQLite database for analysis with Grafana.

## Requirements

- Python 3.6+
- SQLite3 (usually included with Python)
- Optional: `jq` for JSON parsing in bash (falls back to Python if not available)

## Installation

1. Clone this repository to your Raspberry Pi:
   ```bash
   git clone <repository-url> /path/to/zeek-home-network
   cd /path/to/zeek-home-network
   ```

2. Run the setup script (creates directories and sets permissions):
   ```bash
   chmod +x setup.sh fix-permissions.sh
   ./setup.sh
   ```
   
   If you encounter permission issues later, run:
   ```bash
   ./fix-permissions.sh
   ```
   
   Or manually:
   ```bash
   chmod +x zeek-to-sqlite.py zeek-to-sqlite-cron.sh setup.sh fix-permissions.sh
   sudo mkdir -p /var/log /var/lib/grafana/data
   sudo chown $USER:$USER /var/log /var/lib/grafana/data
   ```

3. Edit `config.json` to match your setup:
   ```json
   {
     "logs_directory": "/opt/zeek/logs",
     "database_path": "/var/lib/grafana/data/zeek_logs.db",
     "log_file": "/var/log/zeek-to-sqlite.log",
     "log_level": "INFO",
     "days_back": null,
     "cron_interval_hours": 6
   }
   ```

## Configuration

Edit `config.json` to customize:

- **logs_directory**: Base directory containing date-based Zeek log directories
- **database_path**: Full path to the SQLite database file
- **log_file**: Path to the application log file
- **log_level**: Logging level (DEBUG, INFO, WARNING, ERROR)
- **days_back**: Number of recent days to process (null = all days)
- **cron_interval_hours**: For reference only (actual schedule is in crontab)

## Usage

### Manual Execution

Process all date directories:
```bash
./zeek-to-sqlite.py
```

Process only the last 7 days:
```bash
./zeek-to-sqlite.py --days 7
```

Process a specific date directory:
```bash
./zeek-to-sqlite.py --logs-dir /opt/zeek/logs/2025-12-28
```

Custom database location:
```bash
./zeek-to-sqlite.py --database /path/to/custom.db
```

### Command Line Options

```
--logs-dir PATH      Base directory with date-based log directories (default: /opt/zeek/logs)
--database PATH      Output database path (default: /var/lib/grafana/data/zeek_logs.db)
--days N             Process only the last N days (default: all)
--log-file PATH      Log file path (default: /var/log/zeek-to-sqlite.log)
--log-level LEVEL    Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
```

## Cron Setup

1. Edit `crontab.example` and adjust the schedule and path:
   ```bash
   nano crontab.example
   ```

2. Install the crontab:
   ```bash
   # Edit the path in crontab.example first, then:
   crontab crontab.example
   ```

   Or manually add to crontab:
   ```bash
   crontab -e
   # Add this line (adjust path):
   0 */6 * * * /path/to/zeek-home-network/zeek-to-sqlite-cron.sh
   ```

3. Verify the crontab:
   ```bash
   crontab -l
   ```

The cron wrapper script (`zeek-to-sqlite-cron.sh`) provides:
- Lock file to prevent concurrent runs
- Automatic logging to `/var/log/zeek-to-sqlite-cron.log`
- Error handling and exit code reporting
- Configuration file parsing

## Log Files

- **Application logs**: `/var/log/zeek-to-sqlite.log` (configurable)
- **Cron execution logs**: `/var/log/zeek-to-sqlite-cron.log`

## How It Works

1. **Directory Discovery**: Scans the logs directory for date-based subdirectories (yyyy-mm-dd format)

2. **File Processing**: For each log file:
   - Checks if already processed (using file hash)
   - Parses Zeek TSV format
   - Creates SQLite tables based on log type
   - Imports data rows
   - Records processing in `_processed_files` table

3. **Duplicate Prevention**: Uses file hashing and a tracking table to avoid re-processing files

4. **Table Naming**: Log types (conn, dns, http, etc.) become table names, with special characters sanitized

## Database Schema

The script creates tables dynamically based on Zeek log types:
- `conn` - Connection logs
- `dns` - DNS queries
- `http` - HTTP requests
- `ssl` - SSL/TLS connections
- And any other log types present

A special `_processed_files` table tracks which files have been imported.

## Troubleshooting

### Permission Issues

If you get permission errors when creating the database:

**Option 1: Change ownership of the directory (Recommended)**
```bash
# Check current ownership
ls -ld /var/lib/grafana/data

# Change ownership to your user (replace 'youruser' with your username)
sudo chown youruser:youruser /var/lib/grafana/data

# Or if Grafana needs access, use a group:
sudo chown youruser:grafana /var/lib/grafana/data
sudo chmod 775 /var/lib/grafana/data
```

**Option 2: Add your user to the grafana group**
```bash
# Add your user to grafana group
sudo usermod -a -G grafana $USER

# Log out and back in for group changes to take effect
# Then set group permissions
sudo chmod 775 /var/lib/grafana/data
```

**Option 3: Use a different location (if you can't modify Grafana's directory)**
Edit `config.json` and change `database_path` to a location you own:
```json
{
  "database_path": "/home/youruser/zeek_logs.db"
}
```

**Verify permissions:**
```bash
# Test write access
touch /var/lib/grafana/data/zeek_logs.db

# Check Zeek logs access
ls -la /opt/zeek/logs
```

### Check Logs
```bash
# Application logs
tail -f /var/log/zeek-to-sqlite.log

# Cron execution logs
tail -f /var/log/zeek-to-sqlite-cron.log
```

### Verify Database
```bash
sqlite3 /var/lib/grafana/data/zeek_logs.db
.tables
SELECT COUNT(*) FROM conn;
```

### Test Run
```bash
# Run with DEBUG logging to see detailed output
./zeek-to-sqlite.py --log-level DEBUG --days 1
```

