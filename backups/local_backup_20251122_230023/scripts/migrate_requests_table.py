#!/usr/bin/env python3
"""
Script per migrare la tabella requests aggiungendo le colonne mancanti
Da eseguire su PythonAnywhere per aggiornare il database
"""
import sqlite3
import sys

def create_connection(db_file='songs.db'):
    """Create a database connection."""
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_requests_table(db_file='songs.db'):
    """Add missing columns to requests table."""
    conn = create_connection(db_file)
    if not conn:
        print("❌ Cannot connect to database")
        return False
    
    cursor = conn.cursor()
    
    print("=" * 60)
    print("MIGRAZIONE TABELLA REQUESTS")
    print("=" * 60)
    print()
    
    # Check current structure
    print("📋 Struttura attuale della tabella requests:")
    cursor.execute("PRAGMA table_info(requests)")
    columns = cursor.fetchall()
    existing_columns = [col[1] for col in columns]
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    print()
    
    # Columns to add
    columns_to_add = [
        ('session_id', 'TEXT'),
        ('status', 'TEXT DEFAULT "pending"'),
        ('played_at', 'TIMESTAMP NULL'),
        ('tip_amount', 'REAL DEFAULT 0.0')
    ]
    
    # Add missing columns
    added_columns = []
    for column_name, column_def in columns_to_add:
        if not check_column_exists(cursor, 'requests', column_name):
            try:
                print(f"➕ Aggiungo colonna: {column_name}...")
                cursor.execute(f'ALTER TABLE requests ADD COLUMN {column_name} {column_def}')
                added_columns.append(column_name)
                print(f"   ✅ Colonna {column_name} aggiunta")
            except sqlite3.Error as e:
                print(f"   ❌ Errore aggiungendo {column_name}: {e}")
        else:
            print(f"   ✓ Colonna {column_name} già esistente")
    
    if added_columns:
        conn.commit()
        print()
        print(f"✅ Migrazione completata! Colonne aggiunte: {', '.join(added_columns)}")
    else:
        print()
        print("✅ Nessuna migrazione necessaria - tutte le colonne esistono già")
    
    # Create indexes
    print()
    print("📊 Creo indici per performance...")
    indexes = [
        ('idx_requests_tenant_status', 'CREATE INDEX IF NOT EXISTS idx_requests_tenant_status ON requests(tenant_id, status)'),
        ('idx_requests_session', 'CREATE INDEX IF NOT EXISTS idx_requests_session ON requests(session_id)'),
        ('idx_requests_played_at', 'CREATE INDEX IF NOT EXISTS idx_requests_played_at ON requests(played_at)'),
        ('idx_requests_timestamp', 'CREATE INDEX IF NOT EXISTS idx_requests_timestamp ON requests(request_time)')
    ]
    
    for index_name, index_sql in indexes:
        try:
            cursor.execute(index_sql)
            print(f"   ✅ Indice {index_name} creato")
        except sqlite3.Error as e:
            print(f"   ⚠️  Errore creando {index_name}: {e}")
    
    conn.commit()
    
    # Update existing requests to have status 'pending' if NULL
    print()
    print("🔄 Aggiorno richieste esistenti...")
    try:
        cursor.execute("UPDATE requests SET status = 'pending' WHERE status IS NULL")
        updated = cursor.rowcount
        conn.commit()
        print(f"   ✅ {updated} richieste aggiornate con status 'pending'")
    except sqlite3.Error as e:
        print(f"   ⚠️  Errore aggiornando richieste: {e}")
    
    # Verify final structure
    print()
    print("📋 Struttura finale della tabella requests:")
    cursor.execute("PRAGMA table_info(requests)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    
    conn.close()
    print()
    print("=" * 60)
    print("✅ Migrazione completata con successo!")
    print("=" * 60)
    
    return True

if __name__ == '__main__':
    db_file = sys.argv[1] if len(sys.argv) > 1 else 'songs.db'
    print(f"📁 Database: {db_file}")
    print()
    migrate_requests_table(db_file)

