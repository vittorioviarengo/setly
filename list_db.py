import sqlite3

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print("Connection successful!")
    except Exception as e:
        print(e)
    return conn

def select_all_songs(conn):
    """Query all rows in the songs table"""
    cur = conn.cursor()
    cur.execute("SELECT * FROM songs WHERE queued >0")
    print("getting the cursor")

    rows = cur.fetchall()

    for row in rows:
        print(row)
        print()

def main():
    database = "songs.db"

    # create a database connection
    conn = create_connection(database)

    # select and display all songs
    if conn is not None:
        select_all_songs(conn)
        conn.close()
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    main()
