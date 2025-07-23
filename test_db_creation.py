import os
import sqlite3
import sys

DATABASE_NAME = "ecommerce_test.db" # Use a new name to avoid conflicts
DATABASE_PATH = os.path.join(os.getcwd(), DATABASE_NAME)

print(f"DEBUG_TEST: Starting database creation test.")
print(f"DEBUG_TEST: Database path for test: {DATABASE_PATH}")

conn = None
try:
    # --- IMPORTANT: Delete existing test database file to ensure a fresh setup ---
    if os.path.exists(DATABASE_PATH):
        try:
            os.remove(DATABASE_PATH)
            print(f"DEBUG_TEST: Successfully deleted existing test database '{DATABASE_PATH}'.")
        except OSError as e:
            print(f"DEBUG_TEST: ERROR: Could not delete existing test database file '{DATABASE_PATH}': {e}")
            print("DEBUG_TEST: This might indicate the file is in use by another process. Please ensure no other programs are open.")
            sys.exit(1)
    else:
        print(f"DEBUG_TEST: No existing test database '{DATABASE_PATH}' found, proceeding to create new.")
    # --- End IMPORTANT ---

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    print(f"DEBUG_TEST: Connected to test database '{DATABASE_PATH}'.")

    print("DEBUG_TEST: Creating total_sales table in test DB...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS total_sales (
            id INTEGER PRIMARY KEY,
            order_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            amount REAL NOT NULL,
            sale_date TEXT NOT NULL
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO total_sales (id, order_id, product_name, amount, sale_date) VALUES (1, 'ORD001', 'Laptop', 1200.00, '2025-07-20')")
    conn.commit()
    print("DEBUG_TEST: Total_sales table created and data inserted in test DB.")
    
    # Verify table creation
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='total_sales';")
    if cursor.fetchone():
        print("DEBUG_TEST: Confirmed 'total_sales' table exists in test DB after setup.")
    else:
        print("DEBUG_TEST: FATAL_TEST_ERROR: 'total_sales' table DOES NOT exist in test DB after setup. Exiting.")
        sys.exit(1)

except sqlite3.Error as e:
    # Corrected the f-string syntax error here
    print(f"DEBUG_TEST: FATAL_TEST_ERROR during test database setup: {e}")
    sys.exit(1)
finally:
    if conn:
        conn.close()
    print(f"DEBUG_TEST: Finished database creation test.")
