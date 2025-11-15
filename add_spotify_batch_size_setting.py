#!/usr/bin/env python3
"""
Add spotify_batch_size setting to system_settings table
"""
import sqlite3

def create_connection():
    """Create a database connection"""
    conn = None
    try:
        conn = sqlite3.connect('songs.db')
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def add_spotify_batch_size_setting():
    """Add the spotify_batch_size setting if it doesn't exist"""
    conn = create_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Check if setting already exists
        cursor.execute("SELECT * FROM system_settings WHERE key = 'spotify_batch_size'")
        existing = cursor.fetchone()
        
        if existing:
            print("✅ spotify_batch_size setting already exists")
            print(f"   Current value: {existing['value']}")
            return True
        
        # Add the setting with default value of 50
        cursor.execute('''
            INSERT INTO system_settings (key, value, description)
            VALUES (?, ?, ?)
        ''', (
            'spotify_batch_size',
            '50',
            'Number of songs to process per batch when fetching Spotify data. Lower values (30-50) are more reliable on shared hosting.'
        ))
        
        conn.commit()
        print("✅ Added spotify_batch_size setting (default: 50)")
        return True
        
    except Exception as e:
        print(f"❌ Error adding setting: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("🔧 Adding spotify_batch_size setting to system_settings...")
    print()
    success = add_spotify_batch_size_setting()
    print()
    if success:
        print("✅ Done! You can now configure batch size in Super Admin > Settings")
    else:
        print("❌ Failed to add setting")

