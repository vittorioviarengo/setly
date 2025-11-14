import sqlite3

def create_connection(db_file):
    """ create a database connection to the SQLite database specified by db_file """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Exception as e:
        print(e)
    return conn

def create_table(conn, create_table_sql):
    """ create a table from the create_table_sql statement """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Exception as e:
        print(e)

def main():
    database = "songs.db"

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

    sql_create_requests_table = """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            requester TEXT NOT NULL,
            request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(song_id) REFERENCES songs(id)
        );
    """

    sql_create_settings_table = """
        CREATE TABLE IF NOT EXISTS settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        );
    """

    conn = create_connection(database)

    # create tables
    if conn is not None:
        # create songs table
        create_table(conn, sql_create_songs_table)
        create_table(conn, sql_create_requests_table)
        create_table(conn, sql_create_settings_table)

        # Insert initial setting
        sql_insert = "INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)"
        values = ('max_requests_per_user', '3')

        cur = conn.cursor()

        try:
            cur.execute(sql_insert, values)
            conn.commit()
            print("Setting inserted successfully.")
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

        # Close the connection
        cur.close()
        conn.close()
    else:
        print("Error! cannot create the database connection.")

if __name__ == '__main__':
    main()
