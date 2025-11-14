import sqlite3

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print("Connected to database successfully.")
    except Exception as e:
        print(f"Failed to connect to the database: {e}")
    return conn

def empty_table(conn):
    """Delete all rows in the songs table."""
    try:
        sql = 'DELETE FROM songs;'
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        print("All songs have been deleted from the table.")
    except Exception as e:
        print(f"Failed to delete songs: {e}")

def main():
    database = "songs.db"

    # Create a database connection
    conn = create_connection(database)

    if conn is not None:
        empty_table(conn)
        conn.close()
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    main()
