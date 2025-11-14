import sqlite3
import csv

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print("Connection successful!")
    except Exception as e:
        print(e)
    return conn

def create_table(conn):
    """Create a table if it does not exist already."""
    try:
        sql_create_songs_table = """
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            language TEXT NOT NULL,
            image TEXT NOT NULL,
            requests INTEGER DEFAULT 0,
            popularity INTEGER DEFAULT 0
        );
        """
        c = conn.cursor()
        c.execute(sql_create_songs_table)
    except Exception as e:
        print(e)

def insert_song(conn, song):
    """
    Create a new song entry in the songs table.
    """
    sql = '''INSERT INTO songs(title, author, language, image, requests, popularity)
             VALUES(?,?,?,?,?,?)'''
    cur = conn.cursor()
    cur.execute(sql, song)
    conn.commit()
    return cur.lastrowid

def main():
    database = "songs.db"

    # Create a database connection
    conn = create_connection(database)

    if conn is not None:
        create_table(conn)  # Create the songs table if not already present

        # Read songs from CSV file
        with open('songs.csv', 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                song = (row[0], row[1], row[2], row[3], row[4], row[5])  # Extract title, author, language, image, requests, queued from each row
                insert_song(conn, song)
                print(song)

        conn.close()  # Close the connection
        print("Songs database populated successfully!")
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    main()




