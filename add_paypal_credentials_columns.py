#!/usr/bin/env python3
"""
Script per aggiungere colonne PayPal credentials alla tabella tenants
Permette a ogni tenant di avere le proprie credenziali PayPal
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

def add_paypal_credentials_columns():
    """Add PayPal credentials columns to tenants table."""
    conn = create_connection()
    if not conn:
        print("❌ Cannot connect to database")
        return False
    
    cursor = conn.cursor()
    
    print("=" * 60)
    print("AGGIUNTA COLONNE PAYPAL CREDENTIALS")
    print("=" * 60)
    print()
    
    # Check current structure
    print("📋 Struttura attuale della tabella tenants:")
    cursor.execute("PRAGMA table_info(tenants)")
    columns = cursor.fetchall()
    existing_columns = [col[1] for col in columns]
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
    print()
    
    # Columns to add
    columns_to_add = [
        ('paypal_client_id', 'TEXT NULL'),
        ('paypal_client_secret', 'TEXT NULL'),
        ('paypal_mode', 'TEXT DEFAULT "sandbox"')  # 'sandbox' or 'live'
    ]
    
    # Add missing columns
    added_columns = []
    for column_name, column_def in columns_to_add:
        if column_name not in existing_columns:
            try:
                print(f"➕ Aggiungo colonna: {column_name}...")
                cursor.execute(f'ALTER TABLE tenants ADD COLUMN {column_name} {column_def}')
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
    
    conn.close()
    return True

if __name__ == '__main__':
    success = add_paypal_credentials_columns()
    sys.exit(0 if success else 1)

