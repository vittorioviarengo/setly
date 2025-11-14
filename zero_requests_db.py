import sqlite3

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Exception as e:
        print(f"An error occurred: {e}")
    return None

def reset_requests(db_file):
    """Reset the requests count for all songs in the database."""
    conn = create_connection(db_file)
    if conn is not None:
        try:
            cursor = conn.cursor()
            # SQL command to update the requests field to 0
            update_query = "UPDATE songs SET requests = 0"
            cursor.execute(update_query)
            conn.commit()  # Commit the changes
            print("All song requests have been reset to 0.")
        except Exception as e:
            print(f"An error occurred while updating the database: {e}")
        finally:
            conn.close()  # Close the database connection
    else:
        print("Error! Cannot connect to the database.")

# Specify the path to your database
database_path = 'songs.db'  # Update this path to your database file
reset_requests(database_path)
