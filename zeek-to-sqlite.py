#!/usr/bin/python3
import sqlite3
import os
import csv
import gzip
import argparse
import glob

# Handle both compressed and uncompressed logs
def get_file_handle(filepath):
    if filepath.endswith('.gz'):
        return gzip.open(filepath, 'rt', encoding='utf-8')
    return open(filepath, 'r', encoding='utf-8')

def extract_table_name(filename):
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

def create_table(cursor, table_name, columns):
    if not columns:
        raise ValueError(f"No columns for {table_name}")
    
    cols = ', '.join([f'"{c}" TEXT' for c in columns])
    sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols});'
    cursor.execute(sql)

def insert_data(cursor, table_name, columns, data):
    if not data:
        return
    
    placeholders = ', '.join(['?' for _ in columns])
    col_names = ', '.join([f'"{c}"' for c in columns])
    sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders});'
    cursor.executemany(sql, data)

def process_directory(conn, cursor, directory):
    processed = 0
    skipped = 0

    if not os.path.isdir(directory):
        print(f"Not a directory: {directory}")
        return processed, skipped

    files = sorted(os.listdir(directory))
    for filename in files:
        # skip non-log files
        if not (filename.endswith('.log') or filename.endswith('.log.gz') or '.' in filename):
            continue
        
        table_name = extract_table_name(filename)
        log_path = os.path.join(directory, filename)

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
                print(f"  No columns in {filename}, skipping")
                skipped += 1
                f.close()
                continue

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

            if data:
                insert_data(cursor, table_name, columns, data)
                print(f"  {filename}: {len(data)} rows -> {table_name}")
                processed += 1
            else:
                print(f"  {filename}: empty, table created")
                processed += 1
            
            f.close()

        except Exception as e:
            print(f"  Error with {filename}: {e}")
            skipped += 1
    
    return processed, skipped

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert Zeek logs to SQLite')
    parser.add_argument('directory', nargs='?', default='/opt/zeek/logs/current',
                        help='Directory with logs (supports wildcards)')
    parser.add_argument('database', nargs='?', default=None,
                        help='Output database name (optional, can use -d instead)')
    parser.add_argument('-d', '--database', dest='database_flag',
                        help='Output database name')
    
    args = parser.parse_args()
    
    # get database name from positional arg or flag, default if neither
    db_name = args.database_flag or args.database or 'zeek_logs.db'
    
    # expand wildcards
    dirs = glob.glob(args.directory)
    dirs = [d for d in dirs if os.path.isdir(d)]
    
    if not dirs:
        print(f"No directories found: {args.directory}")
        exit(1)
    
    dirs = sorted(dirs)
    print(f"Found {len(dirs)} directory(ies):")
    for d in dirs:
        print(f"  - {d}")
    print()
    
    # process all into one db
    conn = sqlite3.connect(args.database)
    cursor = conn.cursor()
    
    total_processed = 0
    total_skipped = 0
    
    for d in dirs:
        print(f"Processing: {d}")
        p, s = process_directory(conn, cursor, d)
        total_processed += p
        total_skipped += s
        print()
    
    conn.commit()
    conn.close()
    
    print(f"Done! Processed: {total_processed}, Skipped: {total_skipped}")
    print(f"Database: {args.database}")
