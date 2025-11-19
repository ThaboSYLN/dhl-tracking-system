import sqlite3

def display_sqlite_tables(db_file):
    
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Execute a query to get all table names from sqlite_master
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

        tables = cursor.fetchall()

        if tables:
            print(f"Tables in '{db_file}':")
            for table in tables:
                print(table[0])  # table[0] contains the table name
        else:
            print(f"No tables found in '{db_file}'.")

    except sqlite3.Error as e:
        print(f"Error connecting to or querying the database: {e}")
    finally:
        if conn:
            conn.close()



database_file = 'dhl_tracking.db'
display_sqlite_tables(database_file)