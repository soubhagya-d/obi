import sqlite3
import csv
import os

DB_PATH = 'inventory.db'
CSV_PATH = 'inventory.csv'  # Change if your file has a different name

# Step 1: Create DB and Tables
def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL,
        category TEXT,
        sku TEXT UNIQUE NOT NULL,
        mrp REAL NOT NULL,
        finalsp REAL NOT NULL,
        quantity INTEGER NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        mobile TEXT NOT NULL,
        sku TEXT NOT NULL,
        sp REAL NOT NULL,
        quantity INTEGER NOT NULL,
        total REAL NOT NULL,
        payment_mode TEXT NOT NULL
    )
    ''')

    conn.commit()

# Step 2: Import CSV into inventory
def import_inventory_from_csv(conn, csv_path):
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return

    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        inserted, skipped = 0, 0
        for row in reader:
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO inventory (brand, category, sku, mrp, finalsp, quantity)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    row['Brand'].strip(),
                    row['Category'].strip(),
                    row['SKU'].strip(),
                    float(row['MRP']),
                    float(row['FinalSP']),
                    int(row['Quantity'])
                ))
                inserted += 1
            except Exception as e:
                print(f"⚠️ Skipped row with SKU {row['SKU']}: {e}")
                skipped += 1

        conn.commit()
        print(f"✅ Imported {inserted} items. Skipped {skipped}.")

# Main Execution
if __name__ == '__main__':
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)
    import_inventory_from_csv(conn, CSV_PATH)
    conn.close()
