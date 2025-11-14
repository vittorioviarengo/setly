import sqlite3
import os
from werkzeug.security import generate_password_hash

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

def create_superadmin_tables(conn):
    """Create the super admin related tables"""
    
    # Super admin table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS super_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # System settings table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Audit log table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        tenant_id INTEGER,
        user_id INTEGER,
        user_type TEXT,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Tenants table
    conn.execute('''
    CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        logo_image TEXT,
        active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paypal_enabled BOOLEAN DEFAULT false,
        paypal_link TEXT,
        venmo_enabled BOOLEAN DEFAULT false,
        venmo_link TEXT,
        invite_token TEXT UNIQUE,
        invite_expires_at TIMESTAMP
    )
    ''')

def add_tenant_id_to_existing_tables(conn):
    """Add tenant_id to existing tables"""
    try:
        # Add tenant_id to songs table
        conn.execute('''
        ALTER TABLE songs 
        ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)
        ''')
    except sqlite3.OperationalError:
        print("tenant_id column might already exist in songs table")

    try:
        # Add tenant_id to requests table
        conn.execute('''
        ALTER TABLE requests 
        ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)
        ''')
    except sqlite3.OperationalError:
        print("tenant_id column might already exist in requests table")

    try:
        # Add tenant_id to settings table
        conn.execute('''
        ALTER TABLE settings 
        ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)
        ''')
    except sqlite3.OperationalError:
        print("tenant_id column might already exist in settings table")

def create_default_superadmin(conn):
    """Create a default super admin account"""
    default_username = 'superadmin'
    default_password = 'admin123'  # This should be changed immediately after first login
    default_email = 'admin@example.com'

    # Check if super admin already exists
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM super_admins WHERE username = ?', (default_username,))
    if cursor.fetchone() is None:
        hashed_password = generate_password_hash(default_password, method='pbkdf2:sha256')
        conn.execute('''
        INSERT INTO super_admins (username, password, email)
        VALUES (?, ?, ?)
        ''', (default_username, hashed_password, default_email))
        print("Default super admin account created")
    else:
        print("Super admin account already exists")

def main():
    conn = create_connection()
    if conn is not None:
        create_superadmin_tables(conn)
        add_tenant_id_to_existing_tables(conn)
        create_default_superadmin(conn)
        conn.commit()
        conn.close()
        print("Database migration completed successfully")
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    main()
