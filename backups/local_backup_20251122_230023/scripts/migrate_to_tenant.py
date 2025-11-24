import sqlite3
import os
from werkzeug.security import generate_password_hash

def create_connection():
    """Create a database connection to the SQLite database."""
    database_path = os.path.join(os.path.dirname(__file__), 'songs.db')
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
    return conn

def migrate_to_tenant():
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        # Create Sergio's tenant
        cursor.execute('''
            INSERT INTO tenants (
                name, slug, email, password, active, 
                created_at, logo_image
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (
            'Sergio Chiappa',
            'sergio',
            'info@sergiochiappa.com',
            generate_password_hash('cottonclub', method='pbkdf2:sha256'),  # Using same password as admin for now
            True,
            'Sergio-Chiappa-Head-Square.png'
        ))
        
        tenant_id = cursor.lastrowid
        print(f"Created tenant with ID: {tenant_id}")

        # Update all existing songs to belong to this tenant
        cursor.execute('UPDATE songs SET tenant_id = ?', (tenant_id,))
        songs_count = cursor.rowcount
        print(f"Associated {songs_count} songs with the tenant")

        # Update all existing requests to belong to this tenant
        cursor.execute('UPDATE requests SET tenant_id = ?', (tenant_id,))
        requests_count = cursor.rowcount
        print(f"Associated {requests_count} requests with the tenant")

        # Copy logo to tenant_logos directory if it doesn't exist
        source_logo = os.path.join('static', 'img', 'Sergio-Chiappa-Head-Square.png')
        dest_logo = os.path.join('static', 'tenant_logos', 'Sergio-Chiappa-Head-Square.png')
        if os.path.exists(source_logo) and not os.path.exists(dest_logo):
            import shutil
            os.makedirs(os.path.dirname(dest_logo), exist_ok=True)
            shutil.copy2(source_logo, dest_logo)
            print("Copied logo to tenant_logos directory")

        conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_to_tenant()
