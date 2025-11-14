import sqlite3
import os

def create_connection():
    """Create a database connection to the SQLite database."""
    database_path = os.path.join(os.path.dirname(__file__), 'songs.db')
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
    return conn

def add_events_link_column(conn):
    """Add events_link column to tenants table"""
    try:
        conn.execute('''
        ALTER TABLE tenants 
        ADD COLUMN events_link TEXT
        ''')
        print("Added events_link column to tenants table")
    except sqlite3.OperationalError as e:
        print(f"events_link column might already exist: {e}")

def main():
    conn = create_connection()
    if conn is not None:
        add_events_link_column(conn)
        conn.commit()
        conn.close()
        print("Migration completed successfully")
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    main()









