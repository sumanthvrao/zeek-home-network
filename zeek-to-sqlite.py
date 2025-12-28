#!/usr/bin/python3
"""
Zeek Logs to SQLite Converter
Processes Zeek logs from date-based directories and imports them into SQLite.
Tracks processed files to avoid duplicates.
"""
import sqlite3
import os
import csv
import gzip
import argparse
import glob
import logging
import json
import hashlib
import re
from datetime import datetime
from pathlib import Path

# Setup logging
def setup_logging(log_file=None, log_level=logging.INFO):
    """Configure logging to both file and console."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    handlers = [logging.StreamHandler()]
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )
    return logging.getLogger(__name__)

# Handle both compressed and uncompressed logs
def get_file_handle(filepath):
    """Open a log file, handling both compressed and uncompressed formats."""
    if filepath.endswith('.gz'):
        return gzip.open(filepath, 'rt', encoding='utf-8')
    return open(filepath, 'r', encoding='utf-8')

def get_file_hash(filepath):
    """Generate a hash of the file for tracking purposes."""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logging.warning(f"Could not hash {filepath}: {e}")
        # Fallback: use filename and mtime
        stat = os.stat(filepath)
        return hashlib.md5(f"{filepath}:{stat.st_mtime}:{stat.st_size}".encode()).hexdigest()

def extract_table_name(filename):
    """Extract table name from Zeek log filename."""
    # strip extensions
    if filename.endswith('.log.gz'):
        base = filename[:-7]
    elif filename.endswith('.log'):
        base = filename[:-4]
    else:
        base = filename
    
    # get the log type (before timestamp)
    if '.' in base:
        table_name = base.split('.')[0]
    else:
        table_name = base
    
    # sqlite doesn't like hyphens
    return table_name.replace('-', '_')

def init_processed_files_table(cursor):
    """Create table to track processed files."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS _processed_files (
            filepath TEXT PRIMARY KEY,
            file_hash TEXT,
            processed_at TIMESTAMP,
            rows_imported INTEGER
        )
    ''')

def is_file_processed(cursor, filepath, file_hash):
    """Check if a file has already been processed."""
    cursor.execute(
        'SELECT file_hash FROM _processed_files WHERE filepath = ?',
        (filepath,)
    )
    result = cursor.fetchone()
    if result:
        return result[0] == file_hash
    return False

def mark_file_processed(cursor, filepath, file_hash, rows_imported):
    """Mark a file as processed."""
    cursor.execute('''
        INSERT OR REPLACE INTO _processed_files 
        (filepath, file_hash, processed_at, rows_imported)
        VALUES (?, ?, ?, ?)
    ''', (filepath, file_hash, datetime.now().isoformat(), rows_imported))

def create_table(cursor, table_name, columns):
    """Create a table if it doesn't exist."""
    if not columns:
        raise ValueError(f"No columns for {table_name}")
    
    cols = ', '.join([f'"{c}" TEXT' for c in columns])
    sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols});'
    cursor.execute(sql)

def insert_data(cursor, table_name, columns, data):
    """Insert data into a table."""
    if not data:
        return
    
    placeholders = ', '.join(['?' for _ in columns])
    col_names = ', '.join([f'"{c}"' for c in columns])
    sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders});'
    cursor.executemany(sql, data)

def process_file(conn, cursor, log_path, table_name):
    """Process a single log file and return number of rows imported."""
    file_hash = get_file_hash(log_path)
    
    # Check if already processed
    if is_file_processed(cursor, log_path, file_hash):
        logging.debug(f"Skipping already processed file: {log_path}")
        return 0
    
    try:
        f = get_file_handle(log_path)
        reader = csv.reader(f, delimiter='\t')
        
        # find #fields line
        columns = []
        for row in reader:
            if row and row[0].startswith('#fields'):
                columns = [col.replace('.', '_') for col in row[1:]]
                break

        if not columns:
            logging.warning(f"No columns found in {log_path}, skipping")
            f.close()
            return 0

        create_table(cursor, table_name, columns)

        # read data rows
        data = []
        for row in reader:
            if row and not row[0].startswith('#'):
                # pad or truncate to match column count
                if len(row) < len(columns):
                    row.extend([''] * (len(columns) - len(row)))
                elif len(row) > len(columns):
                    row = row[:len(columns)]
                data.append(row)

        rows_imported = 0
        if data:
            insert_data(cursor, table_name, columns, data)
            rows_imported = len(data)
            logging.info(f"{os.path.basename(log_path)}: {rows_imported} rows -> {table_name}")
        
        f.close()
        
        # Mark as processed
        mark_file_processed(cursor, log_path, file_hash, rows_imported)
        conn.commit()
        
        return rows_imported

    except Exception as e:
        logging.error(f"Error processing {log_path}: {e}", exc_info=True)
        return 0

def process_directory(conn, cursor, directory):
    """Process all log files in a directory."""
    processed = 0
    skipped = 0
    total_rows = 0

    if not os.path.isdir(directory):
        logging.warning(f"Not a directory: {directory}")
        return processed, skipped, total_rows

    files = sorted(os.listdir(directory))
    for filename in files:
        # skip non-log files
        if not (filename.endswith('.log') or filename.endswith('.log.gz')):
            continue
        
        table_name = extract_table_name(filename)
        log_path = os.path.join(directory, filename)
        
        rows = process_file(conn, cursor, log_path, table_name)
        if rows > 0:
            processed += 1
            total_rows += rows
        else:
            skipped += 1
    
    return processed, skipped, total_rows

def find_date_directories(logs_base_dir, days_back=None):
    """Find date-based directories (yyyy-mm-dd format) in the logs directory."""
    date_dirs = []
    
    if not os.path.isdir(logs_base_dir):
        logging.error(f"Logs base directory does not exist: {logs_base_dir}")
        return date_dirs
    
    for item in os.listdir(logs_base_dir):
        item_path = os.path.join(logs_base_dir, item)
        if os.path.isdir(item_path):
            # Check if it matches yyyy-mm-dd format
            try:
                datetime.strptime(item, '%Y-%m-%d')
                date_dirs.append(item_path)
            except ValueError:
                # Not a date directory, skip
                continue
    
    # Sort by date (newest first)
    date_dirs.sort(reverse=True)
    
    # Limit to last N days if specified
    if days_back:
        date_dirs = date_dirs[:days_back]
    
    return date_dirs

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Convert Zeek logs to SQLite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Process all date directories
  %(prog)s --logs-dir /opt/zeek/logs --database /var/lib/grafana/data/zeek_logs.db
  
  # Process only last 7 days
  %(prog)s --logs-dir /opt/zeek/logs --database /var/lib/grafana/data/zeek_logs.db --days 7
  
  # Process specific directory
  %(prog)s --logs-dir /opt/zeek/logs/2025-12-28 --database /var/lib/grafana/data/zeek_logs.db
        '''
    )
    parser.add_argument('--logs-dir', default='/opt/zeek/logs',
                        help='Base directory containing date-based log directories (default: /opt/zeek/logs)')
    parser.add_argument('--database', default='/var/lib/grafana/data/zeek_logs.db',
                        help='Output database path (default: /var/lib/grafana/data/zeek_logs.db)')
    parser.add_argument('--days', type=int, default=None,
                        help='Process only the last N days (default: all)')
    parser.add_argument('--log-file', default='/var/log/zeek-to-sqlite.log',
                        help='Log file path (default: /var/log/zeek-to-sqlite.log)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        default='INFO', help='Logging level (default: INFO)')
    parser.add_argument('--directory', help='DEPRECATED: Use --logs-dir instead')
    
    args = parser.parse_args()
    
    # Handle deprecated --directory argument
    if args.directory:
        logging.warning("--directory is deprecated, use --logs-dir instead")
        args.logs_dir = args.directory
    
    # Setup logging
    log_level = getattr(logging, args.log_level)
    logger = setup_logging(args.log_file, log_level)
    
    logger.info("=" * 60)
    logger.info("Zeek Logs to SQLite Converter - Starting")
    logger.info("=" * 60)
    
    # Ensure database directory exists
    db_dir = os.path.dirname(args.database)
    if db_dir and not os.path.exists(db_dir):
        logger.info(f"Creating database directory: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)
    
    # Find directories to process
    # Check if the logs_dir itself is a date directory (yyyy-mm-dd format)
    basename = os.path.basename(args.logs_dir)
    if re.match(r'^\d{4}-\d{2}-\d{2}$', basename):
        # Direct date directory specified
        dirs = [args.logs_dir] if os.path.isdir(args.logs_dir) else []
    else:
        # Find date directories
        dirs = find_date_directories(args.logs_dir, args.days)
    
    if not dirs:
        logger.error(f"No date directories found in: {args.logs_dir}")
        exit(1)
    
    logger.info(f"Found {len(dirs)} directory(ies) to process:")
    for d in dirs:
        logger.info(f"  - {d}")
    
    # Connect to database
    try:
        conn = sqlite3.connect(args.database)
        cursor = conn.cursor()
        
        # Initialize processed files tracking
        init_processed_files_table(cursor)
        conn.commit()
        
        total_processed = 0
        total_skipped = 0
        total_rows = 0
        
        # Process each directory
        for d in dirs:
            logger.info(f"Processing directory: {d}")
            p, s, r = process_directory(conn, cursor, d)
            total_processed += p
            total_skipped += s
            total_rows += r
            logger.info(f"  Processed: {p} files, Skipped: {s} files, Rows: {r}")
        
        conn.close()
        
        logger.info("=" * 60)
        logger.info(f"Processing complete!")
        logger.info(f"  Total files processed: {total_processed}")
        logger.info(f"  Total files skipped: {total_skipped}")
        logger.info(f"  Total rows imported: {total_rows}")
        logger.info(f"  Database: {args.database}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)
