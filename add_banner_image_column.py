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

def add_banner_image_column():
    """Add banner_image column to tenants table."""
    conn = create_connection()
    if not conn:
        print("Error: Could not connect to database")
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute('ALTER TABLE tenants ADD COLUMN banner_image TEXT')
        conn.commit()
        print("Successfully added banner_image column to tenants table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("banner_image column already exists")
        else:
            print(f"Error adding column: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    add_banner_image_column()









