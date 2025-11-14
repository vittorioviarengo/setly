import sqlite3

# Connect to the database
conn = sqlite3.connect('songs.db')
cursor = conn.cursor()

try:
    # Add venue_name column to tenants
    cursor.execute('ALTER TABLE tenants ADD COLUMN venue_name TEXT DEFAULT "Music Venue"')
    print("Added venue_name column to tenants table")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("venue_name column already exists")
    else:
        print(f"Error adding venue_name: {e}")

try:
    # Add max_requests column to tenants
    cursor.execute('ALTER TABLE tenants ADD COLUMN max_requests INTEGER DEFAULT 3')
    print("Added max_requests column to tenants table")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("max_requests column already exists")
    else:
        print(f"Error adding max_requests: {e}")

conn.commit()
conn.close()
print("Migration completed!")









