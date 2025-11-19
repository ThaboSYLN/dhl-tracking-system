import sqlite3
import sys

DATABASE_FILE = 'dhl_tracking.db' 

def view_table_content(table_name):
   
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        query = f"SELECT * FROM {table_name}"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Get column headers
        headers = [description[0] for description in cursor.description]
        
        # Print results nicely
        print(f"\n--- Contents of table: '{table_name}' ---")
        print(headers)
        print("-" * len(str(headers)))
        
        if not rows:
            print(f"The table '{table_name}' is empty.")
        else:
            for row in rows:
                print(row)

    except sqlite3.Error as e:
        print(f"An SQLite error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # Ensure the database connection is closed
        if conn:
            conn.close()

if __name__ == "__main__":
    # Check if a table name was provided as a command-line argument
    if len(sys.argv) != 2:
        print("Usage: python view_table_content.py <table_name>")
        # Example if you knew table names:
        # print("Example: python view_table_content.py shipments")
        sys.exit(1)
    
    # Get the table name from the command-line argument
    table_name_to_view = sys.argv[1]
    view_table_content(table_name_to_view)
