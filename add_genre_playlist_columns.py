import sqlite3
import os

def create_connection():
    database_path = os.path.join(os.path.dirname(__file__), 'songs.db')
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
    return conn

def add_genre_playlist_columns():
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(songs)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add genre column if it doesn't exist
        if 'genre' not in columns:
            cursor.execute("ALTER TABLE songs ADD COLUMN genre TEXT")
            print("Added genre column to songs table")
        else:
            print("genre column already exists")
        
        # Add playlist column if it doesn't exist
        if 'playlist' not in columns:
            cursor.execute("ALTER TABLE songs ADD COLUMN playlist TEXT")
            print("Added playlist column to songs table")
        else:
            print("playlist column already exists")
        
        conn.commit()
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_genre_playlist_columns()









