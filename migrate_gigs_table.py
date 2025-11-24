#!/usr/bin/env python3
"""
Migration script to create the 'gigs' table for managing active gigs.
This allows musicians to start/end gigs and prevents end users from requesting songs when no gig is active.
"""
import sqlite3
import sys
from datetime import datetime

def create_connection(db_file='songs.db'):
    """Create a database connection."""
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def check_table_exists(cursor, table_name):
    """Check if a table exists."""
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None

def migrate_gigs_table(db_file='songs.db'):
    """Create the gigs table if it doesn't exist."""
    conn = create_connection(db_file)
    if not conn:
        print("Failed to create database connection")
        return False
    
    cursor = conn.cursor()
    
    try:
        # Check if table already exists
        if check_table_exists(cursor, 'gigs'):
            print("Table 'gigs' already exists. Skipping migration.")
            conn.close()
            return True
        
        # Create gigs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gigs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                name TEXT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(tenant_id) REFERENCES tenants(id),
                CHECK(is_active IN (0, 1))
            )
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gigs_tenant_active 
            ON gigs(tenant_id, is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gigs_start_time 
            ON gigs(start_time)
        """)
        
        # Add gig_id column to requests table if it doesn't exist
        try:
            cursor.execute("ALTER TABLE requests ADD COLUMN gig_id INTEGER NULL")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_gig_id 
                ON requests(gig_id)
            """)
            print("Added gig_id column to requests table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("Column gig_id already exists in requests table")
            else:
                raise
        
        conn.commit()
        print("Successfully created 'gigs' table and indexes")
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Error creating gigs table: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == '__main__':
    db_file = sys.argv[1] if len(sys.argv) > 1 else 'songs.db'
    success = migrate_gigs_table(db_file)
    sys.exit(0 if success else 1)

